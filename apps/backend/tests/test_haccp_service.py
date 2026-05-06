"""HACCP service tests — seed templates, run management."""

import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- register all models with SQLModel.metadata
from app.core.exceptions import ConflictError, NotFoundError
from app.models.equipment import Equipment
from app.models.haccp_template import HACCPChecklistTemplate
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.haccp import HACCPAnswerCreate
from app.services.haccp_service import HACCPService

TODAY = date.today()


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
    user = User(email=f"test_{uuid4()}@test.com")
    session.add(user)
    restaurant = Restaurant(name="Test Restaurant", country="IE")
    session.add(restaurant)
    await session.flush()
    return {"user": user.id, "restaurant": restaurant.id}


@pytest.fixture
async def template(session, test_data):
    t = HACCPChecklistTemplate(
        restaurant_id=test_data["restaurant"],
        name="Test Template",
        frequency="daily",
        is_equipment_dynamic=False,
        created_by_user_id=test_data["user"],
    )
    session.add(t)
    await session.flush()
    return t


@pytest.fixture
async def dynamic_template(session, test_data):
    t = HACCPChecklistTemplate(
        restaurant_id=test_data["restaurant"],
        name="Temperature Log",
        frequency="shift",
        shifts_per_day=2,
        is_equipment_dynamic=True,
        created_by_user_id=test_data["user"],
    )
    session.add(t)
    await session.flush()
    return t


@pytest.fixture
async def equipment_item(session, test_data):
    eq = Equipment(
        restaurant_id=test_data["restaurant"],
        name="Fridge Main",
        equipment_type="fridge",
        min_temp=0,
        max_temp=5,
    )
    session.add(eq)
    await session.flush()
    return eq


@pytest.mark.asyncio
async def test_seed_templates_creates_six(session, test_data):
    svc = HACCPService(session)
    await svc.create_seed_templates(test_data["restaurant"], test_data["user"])
    result = await session.exec(
        select(HACCPChecklistTemplate).where(
            HACCPChecklistTemplate.restaurant_id == test_data["restaurant"]
        )
    )
    templates = list(result.all())
    assert len(templates) == 6


@pytest.mark.asyncio
async def test_seed_templates_names(session, test_data):
    svc = HACCPService(session)
    await svc.create_seed_templates(test_data["restaurant"], test_data["user"])
    result = await session.exec(
        select(HACCPChecklistTemplate).where(
            HACCPChecklistTemplate.restaurant_id == test_data["restaurant"]
        )
    )
    names = {t.name for t in result.all()}
    assert "Opening Check" in names
    assert "Closing Check" in names
    assert "Temperature Log" in names
    assert "Delivery Check" in names
    assert "Cleaning Log" in names
    assert "Weekly Deep Clean" in names


@pytest.mark.asyncio
async def test_seed_temperature_log_is_dynamic(session, test_data):
    svc = HACCPService(session)
    await svc.create_seed_templates(test_data["restaurant"], test_data["user"])
    result = await session.exec(
        select(HACCPChecklistTemplate).where(
            HACCPChecklistTemplate.restaurant_id == test_data["restaurant"],
            HACCPChecklistTemplate.name == "Temperature Log",
        )
    )
    t = result.first()
    assert t is not None
    assert t.is_equipment_dynamic is True
    assert t.shifts_per_day == 2


@pytest.mark.asyncio
async def test_start_run_static(session, test_data, template):
    svc = HACCPService(session)
    run = await svc.start_run(
        restaurant_id=test_data["restaurant"],
        template_id=template.id,
        run_date=TODAY,
        created_by_user_id=test_data["user"],
    )
    assert run.status == "in_progress"
    assert run.run_date == TODAY
    assert run.equipment_snapshot_json is None


@pytest.mark.asyncio
async def test_start_run_not_found(session, test_data):
    svc = HACCPService(session)
    with pytest.raises(NotFoundError):
        await svc.start_run(
            restaurant_id=test_data["restaurant"],
            template_id=uuid4(),
            run_date=TODAY,
            created_by_user_id=test_data["user"],
        )


@pytest.mark.asyncio
async def test_start_run_dynamic_creates_snapshot(
    session, test_data, dynamic_template, equipment_item
):
    svc = HACCPService(session)
    run = await svc.start_run(
        restaurant_id=test_data["restaurant"],
        template_id=dynamic_template.id,
        run_date=TODAY,
        created_by_user_id=test_data["user"],
        shift_number=1,
    )
    assert run.equipment_snapshot_json is not None
    assert len(run.equipment_snapshot_json) == 1
    assert run.equipment_snapshot_json[0]["name"] == "Fridge Main"


@pytest.mark.asyncio
async def test_start_run_dynamic_empty_equipment(session, test_data, dynamic_template):
    svc = HACCPService(session)
    run = await svc.start_run(
        restaurant_id=test_data["restaurant"],
        template_id=dynamic_template.id,
        run_date=TODAY,
        created_by_user_id=test_data["user"],
    )
    assert run.equipment_snapshot_json == []


@pytest.mark.asyncio
async def test_submit_answer_yes_no(session, test_data, template):
    svc = HACCPService(session)
    run = await svc.start_run(test_data["restaurant"], template.id, TODAY, test_data["user"])
    answer = await svc.submit_answer(
        restaurant_id=test_data["restaurant"],
        run_id=run.id,
        data=HACCPAnswerCreate(answer_bool=True),
        answered_by_user_id=test_data["user"],
    )
    assert answer.answer_bool is True
    assert answer.skip_reason is None


@pytest.mark.asyncio
async def test_submit_answer_temperature_out_of_range(session, test_data, template, equipment_item):
    svc = HACCPService(session)
    run = await svc.start_run(test_data["restaurant"], template.id, TODAY, test_data["user"])
    answer = await svc.submit_answer(
        restaurant_id=test_data["restaurant"],
        run_id=run.id,
        data=HACCPAnswerCreate(
            answer_numeric=8.5,
            equipment_id=equipment_item.id,
        ),
        answered_by_user_id=test_data["user"],
    )
    assert answer.is_out_of_range is True


@pytest.mark.asyncio
async def test_submit_answer_with_skip_reason(session, test_data, template):
    svc = HACCPService(session)
    run = await svc.start_run(test_data["restaurant"], template.id, TODAY, test_data["user"])
    answer = await svc.submit_answer(
        restaurant_id=test_data["restaurant"],
        run_id=run.id,
        data=HACCPAnswerCreate(skip_reason="under_maintenance"),
        answered_by_user_id=test_data["user"],
    )
    assert answer.skip_reason == "under_maintenance"
    assert answer.answer_bool is None


@pytest.mark.asyncio
async def test_submit_answer_to_completed_run_fails(session, test_data, template):
    svc = HACCPService(session)
    run = await svc.start_run(test_data["restaurant"], template.id, TODAY, test_data["user"])
    run.status = "completed"
    session.add(run)
    await session.flush()
    with pytest.raises(ConflictError):
        await svc.submit_answer(
            restaurant_id=test_data["restaurant"],
            run_id=run.id,
            data=HACCPAnswerCreate(answer_bool=True),
            answered_by_user_id=test_data["user"],
        )


@pytest.mark.asyncio
async def test_complete_run_no_required_items(session, test_data, template):
    svc = HACCPService(session)
    run = await svc.start_run(test_data["restaurant"], template.id, TODAY, test_data["user"])
    completed = await svc.complete_run(test_data["restaurant"], run.id, test_data["user"])
    assert completed.status == "completed"
    assert completed.completed_by_user_id == test_data["user"]


@pytest.mark.asyncio
async def test_complete_run_already_completed_fails(session, test_data, template):
    svc = HACCPService(session)
    run = await svc.start_run(test_data["restaurant"], template.id, TODAY, test_data["user"])
    await svc.complete_run(test_data["restaurant"], run.id, test_data["user"])
    with pytest.raises(ConflictError):
        await svc.complete_run(test_data["restaurant"], run.id, test_data["user"])


@pytest.mark.asyncio
async def test_complete_dynamic_run_missing_equipment_fails(
    session, test_data, dynamic_template, equipment_item
):
    svc = HACCPService(session)
    run = await svc.start_run(
        test_data["restaurant"],
        dynamic_template.id,
        TODAY,
        test_data["user"],
        shift_number=1,
    )
    with pytest.raises(ConflictError):
        await svc.complete_run(test_data["restaurant"], run.id, test_data["user"])
