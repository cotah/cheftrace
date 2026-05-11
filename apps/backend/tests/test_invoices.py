"""Phase 2 Sprint 5 + 6 — invoices model, providers, and /process orchestration.

We cover:
  - FakeStorageProvider contract
  - FakeOCRProvider contract + custom response injection
  - Invoice / InvoiceLineItem ORM round-trip
  - Cross-tenant invoice not visible
  - InvoiceRead Pydantic validates ORM-shaped row (regression for the
    str-vs-datetime drift class)
  - process_invoice happy path (uploaded → needs_review, line items created)
  - process_invoice rejects wrong status (409)
  - process_invoice cross-tenant returns 404
  - process_invoice rolls back to 'uploaded' if OCR fails
"""

import os
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401
from app.api.v1.endpoints.invoices import process_invoice
from app.core.exceptions import ConflictError, NotFoundError
from app.integrations.ocr.base import ExtractedInvoice, ExtractedLineItem, OCRProvider
from app.integrations.ocr.fake_provider import FakeOCRProvider
from app.integrations.storage.fake_storage import FakeStorageProvider
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.membership import RestaurantMembership
from app.models.product import Product
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.invoice import InvoiceLineItemRead, InvoiceRead


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
    user = User(email=f"inv_{uuid4()}@test.com")
    session.add(user)
    restaurant_a = Restaurant(name="Test Restaurant A", country="IE")
    session.add(restaurant_a)
    restaurant_b = Restaurant(name="Test Restaurant B", country="IE")
    session.add(restaurant_b)
    await session.flush()
    return {
        "user": user.id,
        "restaurant": restaurant_a.id,
        "restaurant_b": restaurant_b.id,
    }


@pytest.mark.asyncio
async def test_fake_storage_returns_deterministic_urls():
    s = FakeStorageProvider()
    upload = await s.generate_upload_url("invoices", "rid/iid.pdf", expires_in=300)
    download = await s.generate_download_url("invoices", "rid/iid.pdf", expires_in=600)
    assert "fake.storage/upload/invoices/rid/iid.pdf" in upload
    assert "fake.storage/download/invoices/rid/iid.pdf" in download
    assert s.upload_urls == [("invoices", "rid/iid.pdf", 300)]
    assert s.download_urls == [("invoices", "rid/iid.pdf", 600)]


@pytest.mark.asyncio
async def test_fake_ocr_default_response():
    p = FakeOCRProvider()
    extracted = await p.extract("https://fake.storage/x.pdf")
    assert extracted.supplier_name == "Fresh Foods Ltd"
    assert extracted.invoice_number == "INV-2026-001"
    assert len(extracted.line_items) == 2
    assert p.calls == ["https://fake.storage/x.pdf"]


@pytest.mark.asyncio
async def test_fake_ocr_set_response():
    p = FakeOCRProvider()
    custom = ExtractedInvoice(
        supplier_name="Other Co",
        line_items=[
            ExtractedLineItem(line_number=1, raw_text="Olive oil 1L", quantity=Decimal("1"))
        ],
    )
    p.set_response(custom)
    result = await p.extract("ignored")
    assert result.supplier_name == "Other Co"
    assert len(result.line_items) == 1


@pytest.mark.asyncio
async def test_invoice_orm_roundtrip(session, test_data):
    invoice = Invoice(
        restaurant_id=test_data["restaurant"],
        file_path=f"{test_data['restaurant']}/abc.pdf",
        status="uploaded",
        uploaded_by_user_id=test_data["user"],
    )
    session.add(invoice)
    await session.flush()

    item = InvoiceLineItem(
        restaurant_id=test_data["restaurant"],
        invoice_id=invoice.id,
        line_number=1,
        raw_text="Tomatoes 500g",
        quantity=Decimal("2.000"),
        unit="kg",
        unit_cost=Decimal("3.5000"),
        total_cost=Decimal("7.00"),
        status="suggested",
    )
    session.add(item)
    await session.flush()

    fetched = await session.exec(
        select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id)
    )
    items = list(fetched.all())
    assert len(items) == 1
    assert items[0].quantity == Decimal("2.000")
    assert items[0].status == "suggested"


@pytest.mark.asyncio
async def test_invoice_cross_tenant_not_visible(session, test_data):
    other = Invoice(
        restaurant_id=test_data["restaurant_b"],
        file_path=f"{test_data['restaurant_b']}/x.pdf",
        status="uploaded",
        uploaded_by_user_id=test_data["user"],
    )
    session.add(other)
    await session.flush()

    # Query as restaurant A — should see zero invoices
    result = await session.exec(
        select(Invoice).where(Invoice.restaurant_id == test_data["restaurant"])
    )
    assert list(result.all()) == []


@pytest.mark.asyncio
async def test_invoice_read_validates_orm_shape(session, test_data):
    """Regression guard against str-vs-datetime drift (BUG-05 family)."""
    invoice = Invoice(
        restaurant_id=test_data["restaurant"],
        file_path=f"{test_data['restaurant']}/y.pdf",
        status="confirmed",
        uploaded_by_user_id=test_data["user"],
        processed_at=datetime.now(),
        confirmed_at=datetime.now(),
        invoice_date=date.today(),
        total_amount=Decimal("123.45"),
    )
    session.add(invoice)
    await session.flush()
    await session.refresh(invoice)

    read = InvoiceRead.model_validate(invoice)
    assert read.status == "confirmed"
    assert isinstance(read.processed_at, datetime)
    assert isinstance(read.confirmed_at, datetime)
    assert read.invoice_date == date.today()
    assert read.total_amount == Decimal("123.45")


@pytest.mark.asyncio
async def test_invoice_line_item_read_validates_orm_shape(session, test_data):
    inv = Invoice(
        restaurant_id=test_data["restaurant"],
        file_path=f"{test_data['restaurant']}/z.pdf",
        status="needs_review",
        uploaded_by_user_id=test_data["user"],
    )
    session.add(inv)
    await session.flush()

    item = InvoiceLineItem(
        restaurant_id=test_data["restaurant"],
        invoice_id=inv.id,
        line_number=1,
        raw_text="Sample",
        quantity=Decimal("1"),
        status="suggested",
    )
    session.add(item)
    await session.flush()
    await session.refresh(item)

    read = InvoiceLineItemRead.model_validate(item)
    assert read.line_number == 1
    assert read.status == "suggested"


# --------- Sprint 6: process_invoice orchestration --------- #


async def _make_membership(session, test_data) -> RestaurantMembership:
    """Manager membership for test_data['restaurant']."""
    m = RestaurantMembership(
        restaurant_id=test_data["restaurant"],
        user_id=test_data["user"],
        role="manager",
        is_active=True,
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


async def _make_uploaded_invoice(session, test_data) -> Invoice:
    inv = Invoice(
        restaurant_id=test_data["restaurant"],
        file_path=f"{test_data['restaurant']}/proc.pdf",
        status="uploaded",
        uploaded_by_user_id=test_data["user"],
    )
    session.add(inv)
    await session.commit()
    await session.refresh(inv)
    return inv


@pytest.mark.asyncio
async def test_process_uploaded_invoice_creates_line_items_and_marks_needs_review(
    session, test_data
):
    membership = await _make_membership(session, test_data)
    invoice = await _make_uploaded_invoice(session, test_data)
    # Seed a product so the normalizer produces at least one match.
    session.add(
        Product(
            restaurant_id=test_data["restaurant"],
            name="Tomatoes Cherry",
            unit="kg",
        )
    )
    await session.commit()

    storage = FakeStorageProvider()
    ocr = FakeOCRProvider()  # default canned response: 2 line items

    result = await process_invoice(
        invoice_id=invoice.id,
        membership=membership,
        storage=storage,
        ocr=ocr,
        session=session,
    )

    assert result.status == "needs_review"
    assert result.processed_at is not None
    assert result.supplier_name_raw == "Fresh Foods Ltd"
    assert len(result.items) == 2
    # The cherry tomatoes line should be matched to our seeded product.
    cherry = next(it for it in result.items if "Cherry" in (it.raw_text or ""))
    assert cherry.suggested_product_id is not None

    # OCR was called with the signed download URL produced by FakeStorageProvider.
    assert ocr.calls and "fake.storage/download/invoices/" in ocr.calls[0]
    # The invoice row in DB now reflects the new status.
    db_inv = (await session.exec(select(Invoice).where(Invoice.id == invoice.id))).first()
    assert db_inv is not None
    assert db_inv.status == "needs_review"


@pytest.mark.asyncio
async def test_process_invoice_in_wrong_status_returns_409(session, test_data):
    membership = await _make_membership(session, test_data)
    invoice = await _make_uploaded_invoice(session, test_data)
    invoice.status = "needs_review"
    session.add(invoice)
    await session.commit()

    with pytest.raises(ConflictError):
        await process_invoice(
            invoice_id=invoice.id,
            membership=membership,
            storage=FakeStorageProvider(),
            ocr=FakeOCRProvider(),
            session=session,
        )


@pytest.mark.asyncio
async def test_process_invoice_unknown_returns_404(session, test_data):
    membership = await _make_membership(session, test_data)

    with pytest.raises(NotFoundError):
        await process_invoice(
            invoice_id=uuid4(),
            membership=membership,
            storage=FakeStorageProvider(),
            ocr=FakeOCRProvider(),
            session=session,
        )


@pytest.mark.asyncio
async def test_process_invoice_other_tenant_returns_404(session, test_data):
    membership = await _make_membership(session, test_data)
    # Invoice belongs to restaurant B, membership is for restaurant A.
    other = Invoice(
        restaurant_id=test_data["restaurant_b"],
        file_path=f"{test_data['restaurant_b']}/x.pdf",
        status="uploaded",
        uploaded_by_user_id=test_data["user"],
    )
    session.add(other)
    await session.commit()
    await session.refresh(other)

    with pytest.raises(NotFoundError):
        await process_invoice(
            invoice_id=other.id,
            membership=membership,
            storage=FakeStorageProvider(),
            ocr=FakeOCRProvider(),
            session=session,
        )


class _FailingOCR(OCRProvider):
    async def extract(self, file_url: str) -> ExtractedInvoice:
        raise RuntimeError("upstream OCR exploded")


@pytest.mark.asyncio
async def test_process_invoice_ocr_failure_rolls_back_to_uploaded(session, test_data):
    membership = await _make_membership(session, test_data)
    invoice = await _make_uploaded_invoice(session, test_data)

    with pytest.raises(ConflictError):
        await process_invoice(
            invoice_id=invoice.id,
            membership=membership,
            storage=FakeStorageProvider(),
            ocr=_FailingOCR(),
            session=session,
        )

    db_inv = (await session.exec(select(Invoice).where(Invoice.id == invoice.id))).first()
    assert db_inv is not None
    assert db_inv.status == "uploaded"
    # No line items were persisted on failure.
    items = (
        await session.exec(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id))
    ).all()
    assert list(items) == []
