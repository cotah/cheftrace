"""PDF service tests.

Skipped on Windows because WeasyPrint requires native GTK libs that
are not installed there. CI runs on Linux Docker with the libs present.
"""

import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# WeasyPrint imports cleanly on Linux but raises OSError on Windows because
# native GTK libs (cairo, pango, gobject) are not bundled. Skip module-wide
# when the native libs are missing — CI runs on Linux Docker with libs.
try:
    import weasyprint  # noqa: F401

    _WEASYPRINT_OK = True
except (ImportError, OSError):
    _WEASYPRINT_OK = False

pytestmark = pytest.mark.skipif(
    not _WEASYPRINT_OK,
    reason="WeasyPrint native libs not available (Windows without GTK)",
)

import app.models  # noqa: F401, E402
from app.core.exceptions import NotFoundError  # noqa: E402
from app.models.equipment import Equipment  # noqa: E402
from app.models.haccp_answer import HACCPChecklistAnswer  # noqa: E402
from app.models.haccp_item_template import HACCPChecklistItemTemplate  # noqa: E402
from app.models.haccp_run import HACCPChecklistRun  # noqa: E402
from app.models.haccp_template import HACCPChecklistTemplate  # noqa: E402
from app.models.restaurant import Restaurant  # noqa: E402
from app.models.temperature_log import TemperatureLog  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.pdf_service import PDFService  # noqa: E402


@pytest.fixture
async def db_engine():
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5433/test",
    )
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(db_engine):
    factory = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest.fixture
async def test_data(session):
    user = User(email=f"pdf_{uuid4()}@test.com")
    session.add(user)
    restaurant = Restaurant(name="The Grand Café", country="IE", city="Dublin")
    session.add(restaurant)
    await session.flush()

    equipment = Equipment(
        restaurant_id=restaurant.id,
        name="Main Fridge",
        equipment_type="fridge",
        min_temp=Decimal("0"),
        max_temp=Decimal("5"),
        location="Kitchen",
    )
    session.add(equipment)
    await session.flush()

    return {
        "user": user.id,
        "restaurant": restaurant.id,
        "equipment": equipment.id,
    }


def _is_pdf(content: bytes) -> bool:
    return content.startswith(b"%PDF-") and b"%%EOF" in content[-1024:]


@pytest.mark.asyncio
async def test_temperature_log_pdf_empty_period(session, test_data):
    svc = PDFService(session)
    today = date.today()
    pdf_bytes = await svc.generate_temperature_log(
        restaurant_id=test_data["restaurant"],
        date_from=today - timedelta(days=7),
        date_to=today,
    )
    assert _is_pdf(pdf_bytes)
    assert len(pdf_bytes) > 1000  # not empty


@pytest.mark.asyncio
async def test_temperature_log_pdf_with_readings(session, test_data):
    now = datetime.now(UTC).replace(tzinfo=None)
    log_ok = TemperatureLog(
        restaurant_id=test_data["restaurant"],
        equipment_id=test_data["equipment"],
        temperature=Decimal("3.5"),
        is_out_of_range=False,
        recorded_by_user_id=test_data["user"],
        recorded_at=now - timedelta(hours=4),
    )
    log_oor = TemperatureLog(
        restaurant_id=test_data["restaurant"],
        equipment_id=test_data["equipment"],
        temperature=Decimal("8.2"),
        is_out_of_range=True,
        recorded_by_user_id=test_data["user"],
        recorded_at=now - timedelta(hours=2),
    )
    session.add(log_ok)
    session.add(log_oor)
    await session.flush()

    svc = PDFService(session)
    today = date.today()
    pdf_bytes = await svc.generate_temperature_log(
        restaurant_id=test_data["restaurant"],
        date_from=today - timedelta(days=1),
        date_to=today,
    )
    assert _is_pdf(pdf_bytes)


@pytest.mark.asyncio
async def test_temperature_log_pdf_filter_by_equipment(session, test_data):
    other_eq = Equipment(
        restaurant_id=test_data["restaurant"],
        name="Freezer",
        equipment_type="freezer",
        min_temp=Decimal("-25"),
        max_temp=Decimal("-18"),
    )
    session.add(other_eq)
    await session.flush()

    svc = PDFService(session)
    today = date.today()
    pdf_bytes = await svc.generate_temperature_log(
        restaurant_id=test_data["restaurant"],
        date_from=today - timedelta(days=7),
        date_to=today,
        equipment_id=test_data["equipment"],
    )
    assert _is_pdf(pdf_bytes)


@pytest.mark.asyncio
async def test_temperature_log_pdf_unknown_restaurant_raises(session):
    svc = PDFService(session)
    today = date.today()
    with pytest.raises(NotFoundError):
        await svc.generate_temperature_log(
            restaurant_id=uuid4(),
            date_from=today - timedelta(days=1),
            date_to=today,
        )


@pytest.mark.asyncio
async def test_daily_checklist_pdf(session, test_data):
    template = HACCPChecklistTemplate(
        restaurant_id=test_data["restaurant"],
        name="Opening Check",
        frequency="daily",
        is_equipment_dynamic=False,
        created_by_user_id=test_data["user"],
    )
    session.add(template)
    await session.flush()

    item = HACCPChecklistItemTemplate(
        restaurant_id=test_data["restaurant"],
        template_id=template.id,
        order_index=1,
        question="Are all fridges within temperature range?",
        item_type="yes_no",
        is_required=True,
    )
    session.add(item)
    await session.flush()

    run = HACCPChecklistRun(
        restaurant_id=test_data["restaurant"],
        template_id=template.id,
        status="completed",
        run_date=date.today(),
        completed_by_user_id=test_data["user"],
        completed_at=datetime.now(UTC).replace(tzinfo=None),
        created_by_user_id=test_data["user"],
    )
    session.add(run)
    await session.flush()

    answer = HACCPChecklistAnswer(
        restaurant_id=test_data["restaurant"],
        run_id=run.id,
        item_template_id=item.id,
        answer_bool=True,
        is_out_of_range=False,
        answered_by_user_id=test_data["user"],
    )
    session.add(answer)
    await session.flush()

    svc = PDFService(session)
    pdf_bytes = await svc.generate_daily_checklist(
        restaurant_id=test_data["restaurant"], run_id=run.id
    )
    assert _is_pdf(pdf_bytes)


@pytest.mark.asyncio
async def test_daily_checklist_pdf_run_not_found(session, test_data):
    svc = PDFService(session)
    with pytest.raises(NotFoundError):
        await svc.generate_daily_checklist(restaurant_id=test_data["restaurant"], run_id=uuid4())


@pytest.mark.asyncio
async def test_daily_checklist_pdf_cross_tenant_404(session, test_data):
    other = Restaurant(name="Other", country="IE")
    session.add(other)
    await session.flush()

    template = HACCPChecklistTemplate(
        restaurant_id=other.id,
        name="Other resto template",
        frequency="daily",
        is_equipment_dynamic=False,
        created_by_user_id=test_data["user"],
    )
    session.add(template)
    await session.flush()
    run = HACCPChecklistRun(
        restaurant_id=other.id,
        template_id=template.id,
        status="completed",
        run_date=date.today(),
        created_by_user_id=test_data["user"],
    )
    session.add(run)
    await session.flush()

    svc = PDFService(session)
    with pytest.raises(NotFoundError):
        await svc.generate_daily_checklist(
            restaurant_id=test_data["restaurant"],
            run_id=run.id,
        )


@pytest.mark.asyncio
async def test_monthly_haccp_pdf_empty_month(session, test_data):
    svc = PDFService(session)
    pdf_bytes = await svc.generate_monthly_haccp_summary(
        restaurant_id=test_data["restaurant"], year=2026, month=5
    )
    assert _is_pdf(pdf_bytes)


@pytest.mark.asyncio
async def test_monthly_haccp_pdf_with_runs(session, test_data):
    template = HACCPChecklistTemplate(
        restaurant_id=test_data["restaurant"],
        name="Daily Check",
        frequency="daily",
        is_equipment_dynamic=False,
        created_by_user_id=test_data["user"],
    )
    session.add(template)
    await session.flush()

    run = HACCPChecklistRun(
        restaurant_id=test_data["restaurant"],
        template_id=template.id,
        status="completed",
        run_date=date(2026, 5, 3),
        completed_by_user_id=test_data["user"],
        completed_at=datetime(2026, 5, 3, 9, 0),
        created_by_user_id=test_data["user"],
    )
    session.add(run)
    await session.flush()

    svc = PDFService(session)
    pdf_bytes = await svc.generate_monthly_haccp_summary(
        restaurant_id=test_data["restaurant"], year=2026, month=5
    )
    assert _is_pdf(pdf_bytes)


@pytest.mark.asyncio
async def test_monthly_haccp_pdf_unknown_restaurant_raises(session):
    svc = PDFService(session)
    with pytest.raises(NotFoundError):
        await svc.generate_monthly_haccp_summary(restaurant_id=uuid4(), year=2026, month=5)


@pytest.mark.asyncio
async def test_monthly_haccp_pdf_december_year_rollover(session, test_data):
    svc = PDFService(session)
    pdf_bytes = await svc.generate_monthly_haccp_summary(
        restaurant_id=test_data["restaurant"], year=2026, month=12
    )
    assert _is_pdf(pdf_bytes)
