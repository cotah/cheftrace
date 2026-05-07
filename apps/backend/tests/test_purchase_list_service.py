"""Purchase list service tests — coverage target >= 85%."""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- register all models with SQLModel.metadata
from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import (
    PurchaseListItemStatus,
    PurchaseListStatus,
    PurchaseListType,
)
from app.models.product import Product
from app.models.purchase_list_item import PurchaseListItem
from app.models.restaurant import Restaurant
from app.models.stock_lot import StockLot
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.schemas.purchase_list import (
    PurchaseListItemCreate,
    PurchaseListItemUpdate,
    ReceiveItemInput,
)
from app.services.purchase_list_service import PurchaseListService


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
    user = User(email=f"pl_{uuid4()}@test.com")
    session.add(user)
    restaurant_a = Restaurant(name="Restaurant A", country="IE")
    session.add(restaurant_a)
    restaurant_b = Restaurant(name="Restaurant B", country="IE")
    session.add(restaurant_b)
    await session.flush()

    product_a = Product(
        restaurant_id=restaurant_a.id,
        name="Tomatoes",
        unit="kg",
        expiry_required=True,
    )
    product_b = Product(
        restaurant_id=restaurant_b.id,
        name="Other Resto Product",
        unit="kg",
        expiry_required=False,
    )
    session.add(product_a)
    session.add(product_b)
    await session.flush()

    return {
        "user": user.id,
        "restaurant": restaurant_a.id,
        "restaurant_b": restaurant_b.id,
        "product": product_a.id,
        "product_b": product_b.id,
    }


async def _make_draft_list(svc, test_data, item_data=None):
    pl = await svc.create_list(
        test_data["restaurant"],
        list_type=PurchaseListType.FOOD,
        notes=None,
        created_by_user_id=test_data["user"],
    )
    if item_data is None:
        item_data = PurchaseListItemCreate(
            product_id=test_data["product"],
            quantity_ordered=Decimal("10"),
            unit="kg",
        )
    item = await svc.add_item(test_data["restaurant"], pl.id, item_data)
    return pl, item


@pytest.mark.asyncio
async def test_create_list_default_status_draft(session, test_data):
    svc = PurchaseListService(session)
    pl = await svc.create_list(
        test_data["restaurant"],
        list_type=PurchaseListType.FOOD,
        notes="weekly order",
        created_by_user_id=test_data["user"],
    )
    assert pl.status == PurchaseListStatus.DRAFT
    assert pl.notes == "weekly order"
    assert pl.sent_at is None


@pytest.mark.asyncio
async def test_add_item_to_draft_list(session, test_data):
    svc = PurchaseListService(session)
    pl, item = await _make_draft_list(svc, test_data)
    assert item.status == PurchaseListItemStatus.PENDING
    assert item.quantity_ordered == Decimal("10")
    assert item.purchase_list_id == pl.id


@pytest.mark.asyncio
async def test_add_item_product_from_other_restaurant_fails(session, test_data):
    svc = PurchaseListService(session)
    pl = await svc.create_list(
        test_data["restaurant"],
        list_type=PurchaseListType.FOOD,
        notes=None,
        created_by_user_id=test_data["user"],
    )
    bad_item = PurchaseListItemCreate(
        product_id=test_data["product_b"],
        quantity_ordered=Decimal("5"),
        unit="kg",
    )
    with pytest.raises(NotFoundError):
        await svc.add_item(test_data["restaurant"], pl.id, bad_item)


@pytest.mark.asyncio
async def test_add_item_to_nonexistent_list_fails(session, test_data):
    svc = PurchaseListService(session)
    bad_data = PurchaseListItemCreate(
        product_id=test_data["product"],
        quantity_ordered=Decimal("5"),
        unit="kg",
    )
    with pytest.raises(NotFoundError):
        await svc.add_item(test_data["restaurant"], uuid4(), bad_data)


@pytest.mark.asyncio
async def test_update_item_in_draft(session, test_data):
    svc = PurchaseListService(session)
    _pl, item = await _make_draft_list(svc, test_data)
    updated = await svc.update_item(
        test_data["restaurant"],
        item.id,
        PurchaseListItemUpdate(quantity_ordered=Decimal("15")),
    )
    assert updated.quantity_ordered == Decimal("15")


@pytest.mark.asyncio
async def test_delete_item_from_draft(session, test_data):
    svc = PurchaseListService(session)
    _pl, item = await _make_draft_list(svc, test_data)
    await svc.delete_item(test_data["restaurant"], item.id)
    result = await session.exec(select(PurchaseListItem).where(PurchaseListItem.id == item.id))
    assert result.first() is None


@pytest.mark.asyncio
async def test_mark_sent_from_draft(session, test_data):
    svc = PurchaseListService(session)
    pl, _item = await _make_draft_list(svc, test_data)
    sent = await svc.mark_sent(test_data["restaurant"], pl.id)
    assert sent.status == PurchaseListStatus.SENT
    assert sent.sent_at is not None


@pytest.mark.asyncio
async def test_mark_sent_already_sent_fails(session, test_data):
    svc = PurchaseListService(session)
    pl, _item = await _make_draft_list(svc, test_data)
    await svc.mark_sent(test_data["restaurant"], pl.id)
    with pytest.raises(ConflictError):
        await svc.mark_sent(test_data["restaurant"], pl.id)


@pytest.mark.asyncio
async def test_mark_sent_empty_list_fails(session, test_data):
    svc = PurchaseListService(session)
    pl = await svc.create_list(
        test_data["restaurant"],
        list_type=PurchaseListType.FOOD,
        notes=None,
        created_by_user_id=test_data["user"],
    )
    with pytest.raises(ConflictError):
        await svc.mark_sent(test_data["restaurant"], pl.id)


@pytest.mark.asyncio
async def test_add_item_to_sent_list_fails(session, test_data):
    svc = PurchaseListService(session)
    pl, _item = await _make_draft_list(svc, test_data)
    await svc.mark_sent(test_data["restaurant"], pl.id)
    extra = PurchaseListItemCreate(
        product_id=test_data["product"],
        quantity_ordered=Decimal("3"),
        unit="kg",
    )
    with pytest.raises(ConflictError):
        await svc.add_item(test_data["restaurant"], pl.id, extra)


@pytest.mark.asyncio
async def test_update_item_in_sent_list_fails(session, test_data):
    svc = PurchaseListService(session)
    pl, item = await _make_draft_list(svc, test_data)
    await svc.mark_sent(test_data["restaurant"], pl.id)
    with pytest.raises(ConflictError):
        await svc.update_item(
            test_data["restaurant"],
            item.id,
            PurchaseListItemUpdate(quantity_ordered=Decimal("99")),
        )


@pytest.mark.asyncio
async def test_delete_item_from_sent_list_fails(session, test_data):
    svc = PurchaseListService(session)
    pl, item = await _make_draft_list(svc, test_data)
    await svc.mark_sent(test_data["restaurant"], pl.id)
    with pytest.raises(ConflictError):
        await svc.delete_item(test_data["restaurant"], item.id)


@pytest.mark.asyncio
async def test_receive_item_full_quantity_marks_received(session, test_data):
    svc = PurchaseListService(session)
    pl, item = await _make_draft_list(svc, test_data)
    await svc.mark_sent(test_data["restaurant"], pl.id)

    received = await svc.receive_item(
        test_data["restaurant"],
        item.id,
        ReceiveItemInput(
            quantity_received=Decimal("10"),
            expiry_date=None,
            unit_cost=Decimal("2.50"),
        ),
        received_by_user_id=test_data["user"],
    )
    assert received.status == PurchaseListItemStatus.RECEIVED
    assert received.quantity_received == Decimal("10")

    await session.refresh(pl)
    assert pl.status == PurchaseListStatus.RECEIVED


@pytest.mark.asyncio
async def test_receive_item_partial_quantity_marks_partial(session, test_data):
    svc = PurchaseListService(session)
    pl, item = await _make_draft_list(svc, test_data)
    await svc.mark_sent(test_data["restaurant"], pl.id)

    received = await svc.receive_item(
        test_data["restaurant"],
        item.id,
        ReceiveItemInput(quantity_received=Decimal("4")),
        received_by_user_id=test_data["user"],
    )
    assert received.status == PurchaseListItemStatus.PARTIAL
    assert received.quantity_received == Decimal("4")

    await session.refresh(pl)
    assert pl.status == PurchaseListStatus.PARTIALLY_RECEIVED


@pytest.mark.asyncio
async def test_receive_item_multi_step_completes(session, test_data):
    svc = PurchaseListService(session)
    pl, item = await _make_draft_list(svc, test_data)
    await svc.mark_sent(test_data["restaurant"], pl.id)

    await svc.receive_item(
        test_data["restaurant"],
        item.id,
        ReceiveItemInput(quantity_received=Decimal("4")),
        received_by_user_id=test_data["user"],
    )
    received = await svc.receive_item(
        test_data["restaurant"],
        item.id,
        ReceiveItemInput(quantity_received=Decimal("6")),
        received_by_user_id=test_data["user"],
    )
    assert received.status == PurchaseListItemStatus.RECEIVED
    assert received.quantity_received == Decimal("10")

    await session.refresh(pl)
    assert pl.status == PurchaseListStatus.RECEIVED


@pytest.mark.asyncio
async def test_receive_creates_stock_lot_and_movement(session, test_data):
    svc = PurchaseListService(session)
    pl, item = await _make_draft_list(svc, test_data)
    await svc.mark_sent(test_data["restaurant"], pl.id)

    await svc.receive_item(
        test_data["restaurant"],
        item.id,
        ReceiveItemInput(
            quantity_received=Decimal("10"),
            unit_cost=Decimal("2.50"),
        ),
        received_by_user_id=test_data["user"],
    )

    lot_result = await session.exec(
        select(StockLot).where(
            StockLot.restaurant_id == test_data["restaurant"],
            StockLot.product_id == test_data["product"],
        )
    )
    lots = list(lot_result.all())
    assert len(lots) == 1
    assert lots[0].quantity_remaining == Decimal("10")
    assert lots[0].unit_cost == Decimal("2.5000")

    move_result = await session.exec(
        select(StockMovement).where(StockMovement.lot_id == lots[0].id)
    )
    movements = list(move_result.all())
    assert len(movements) == 1
    assert movements[0].kind == "receive"


@pytest.mark.asyncio
async def test_receive_item_uses_estimate_when_no_actual_cost(session, test_data):
    svc = PurchaseListService(session)
    pl = await svc.create_list(
        test_data["restaurant"],
        list_type=PurchaseListType.FOOD,
        notes=None,
        created_by_user_id=test_data["user"],
    )
    item = await svc.add_item(
        test_data["restaurant"],
        pl.id,
        PurchaseListItemCreate(
            product_id=test_data["product"],
            quantity_ordered=Decimal("5"),
            unit="kg",
            unit_cost_estimate=Decimal("3.10"),
        ),
    )
    await svc.mark_sent(test_data["restaurant"], pl.id)
    await svc.receive_item(
        test_data["restaurant"],
        item.id,
        ReceiveItemInput(quantity_received=Decimal("5")),
        received_by_user_id=test_data["user"],
    )
    lot_result = await session.exec(
        select(StockLot).where(StockLot.restaurant_id == test_data["restaurant"])
    )
    lot = lot_result.first()
    assert lot is not None
    assert lot.unit_cost == Decimal("3.1000")


@pytest.mark.asyncio
async def test_receive_item_with_expiry_passes_to_lot(session, test_data):
    from datetime import date, timedelta

    svc = PurchaseListService(session)
    pl, item = await _make_draft_list(svc, test_data)
    await svc.mark_sent(test_data["restaurant"], pl.id)
    target_date = date.today() + timedelta(days=14)

    await svc.receive_item(
        test_data["restaurant"],
        item.id,
        ReceiveItemInput(
            quantity_received=Decimal("10"),
            expiry_date=target_date,
        ),
        received_by_user_id=test_data["user"],
    )
    lot_result = await session.exec(
        select(StockLot).where(StockLot.restaurant_id == test_data["restaurant"])
    )
    lot = lot_result.first()
    assert lot is not None
    assert lot.expiry_date == target_date


@pytest.mark.asyncio
async def test_receive_item_already_received_fails(session, test_data):
    svc = PurchaseListService(session)
    pl, item = await _make_draft_list(svc, test_data)
    await svc.mark_sent(test_data["restaurant"], pl.id)
    await svc.receive_item(
        test_data["restaurant"],
        item.id,
        ReceiveItemInput(quantity_received=Decimal("10")),
        received_by_user_id=test_data["user"],
    )
    with pytest.raises(ConflictError):
        await svc.receive_item(
            test_data["restaurant"],
            item.id,
            ReceiveItemInput(quantity_received=Decimal("1")),
            received_by_user_id=test_data["user"],
        )


@pytest.mark.asyncio
async def test_receive_item_in_draft_list_fails(session, test_data):
    svc = PurchaseListService(session)
    _pl, item = await _make_draft_list(svc, test_data)
    with pytest.raises(ConflictError):
        await svc.receive_item(
            test_data["restaurant"],
            item.id,
            ReceiveItemInput(quantity_received=Decimal("5")),
            received_by_user_id=test_data["user"],
        )


@pytest.mark.asyncio
async def test_receive_item_zero_quantity_fails(session, test_data):
    svc = PurchaseListService(session)
    pl, item = await _make_draft_list(svc, test_data)
    await svc.mark_sent(test_data["restaurant"], pl.id)
    with pytest.raises(ConflictError):
        await svc.receive_item(
            test_data["restaurant"],
            item.id,
            ReceiveItemInput(quantity_received=Decimal("0")),
            received_by_user_id=test_data["user"],
        )


@pytest.mark.asyncio
async def test_receive_item_cross_tenant_fails(session, test_data):
    svc = PurchaseListService(session)
    _pl, item = await _make_draft_list(svc, test_data)
    with pytest.raises(NotFoundError):
        await svc.receive_item(
            test_data["restaurant_b"],
            item.id,
            ReceiveItemInput(quantity_received=Decimal("1")),
            received_by_user_id=test_data["user"],
        )


@pytest.mark.asyncio
async def test_get_list_cross_tenant_returns_404(session, test_data):
    svc = PurchaseListService(session)
    pl, _item = await _make_draft_list(svc, test_data)
    with pytest.raises(NotFoundError):
        await svc._get_list(test_data["restaurant_b"], pl.id)


@pytest.mark.asyncio
async def test_two_items_one_received_one_pending_marks_partial(session, test_data):
    svc = PurchaseListService(session)
    pl = await svc.create_list(
        test_data["restaurant"],
        list_type=PurchaseListType.FOOD,
        notes=None,
        created_by_user_id=test_data["user"],
    )
    item1 = await svc.add_item(
        test_data["restaurant"],
        pl.id,
        PurchaseListItemCreate(
            product_id=test_data["product"],
            quantity_ordered=Decimal("5"),
            unit="kg",
        ),
    )
    await svc.add_item(
        test_data["restaurant"],
        pl.id,
        PurchaseListItemCreate(
            product_id=test_data["product"],
            quantity_ordered=Decimal("3"),
            unit="kg",
        ),
    )
    await svc.mark_sent(test_data["restaurant"], pl.id)

    await svc.receive_item(
        test_data["restaurant"],
        item1.id,
        ReceiveItemInput(quantity_received=Decimal("5")),
        received_by_user_id=test_data["user"],
    )
    await session.refresh(pl)
    assert pl.status == PurchaseListStatus.PARTIALLY_RECEIVED
