"""
FEFO regression tests for StockService.
All 10 mandatory scenarios from PHASE-1-BRIEF.md.
Coverage target: stock_service.py >= 90%.
"""

import os
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- register all models with SQLModel.metadata
from app.models.enums import LotStatus, MovementKind
from app.models.stock_lot import StockLot
from app.services.stock_service import InsufficientStockError, StockService

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
NEXT_WEEK = TODAY + timedelta(days=7)
NEXT_MONTH = TODAY + timedelta(days=30)


async def make_lot(
    session: AsyncSession,
    restaurant_id: UUID,
    product_id: UUID,
    quantity: Decimal,
    expiry_date: date | None = None,
    received_date: date | None = None,
    status: LotStatus = LotStatus.ACTIVE,
) -> StockLot:
    from app.models.user import User

    creator = User(email=f"lot_creator_{uuid4()}@test.com", preferred_lang="pt-BR")
    session.add(creator)
    await session.flush()

    lot = StockLot(
        restaurant_id=restaurant_id,
        product_id=product_id,
        supplier_id=None,
        quantity_received=quantity,
        quantity_remaining=quantity,
        unit="unit",
        expiry_date=expiry_date,
        received_date=received_date or TODAY,
        status=status,
        created_by_user_id=creator.id,
    )
    session.add(lot)
    await session.flush()
    return lot


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
    """Create real parent records to satisfy FK constraints."""
    from app.models.product import Product
    from app.models.restaurant import Restaurant
    from app.models.user import User

    user = User(email=f"test_{uuid4()}@test.com", preferred_lang="pt-BR")
    session.add(user)

    restaurant = Restaurant(name="Test Restaurant", country="IE")
    session.add(restaurant)

    restaurant_b = Restaurant(name="Other Restaurant", country="IE")
    session.add(restaurant_b)

    await session.flush()

    product = Product(
        restaurant_id=restaurant.id,
        name="Test Product",
        unit="unit",
        expiry_required=False,
    )
    session.add(product)

    await session.flush()

    return {
        "user": user.id,
        "restaurant": restaurant.id,
        "restaurant_b": restaurant_b.id,
        "product": product.id,
    }


@pytest.mark.asyncio
async def test_fefo_single_lot_covers_all(session, test_data):
    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("10"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    movements = await svc.consume(
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        "unit",
        test_data["user"],
    )
    assert len(movements) == 1
    assert movements[0].quantity == Decimal("-5")
    assert movements[0].lot_id == lot.id
    await session.refresh(lot)
    assert lot.quantity_remaining == Decimal("5")
    assert lot.status == LotStatus.ACTIVE


@pytest.mark.asyncio
async def test_fefo_two_lots_first_exhausted(session, test_data):
    lot1 = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("3"),
        expiry_date=TOMORROW,
    )
    lot2 = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("10"),
        expiry_date=NEXT_MONTH,
    )
    svc = StockService(session)
    movements = await svc.consume(
        test_data["restaurant"],
        test_data["product"],
        Decimal("8"),
        "unit",
        test_data["user"],
    )
    assert len(movements) == 2
    await session.refresh(lot1)
    await session.refresh(lot2)
    assert lot1.quantity_remaining == Decimal("0")
    assert lot1.status == LotStatus.DEPLETED
    assert lot2.quantity_remaining == Decimal("5")


@pytest.mark.asyncio
async def test_fefo_null_expiry_consumed_last(session, test_data):
    await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("10"),
        expiry_date=None,
    )
    lot_dated = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("10"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    movements = await svc.consume(
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        "unit",
        test_data["user"],
    )
    assert len(movements) == 1
    assert movements[0].lot_id == lot_dated.id


@pytest.mark.asyncio
async def test_fefo_tiebreak_received_date(session, test_data):
    lot_older = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=NEXT_WEEK,
        received_date=TODAY - timedelta(days=3),
    )
    await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=NEXT_WEEK,
        received_date=TODAY,
    )
    svc = StockService(session)
    movements = await svc.consume(
        test_data["restaurant"],
        test_data["product"],
        Decimal("3"),
        "unit",
        test_data["user"],
    )
    assert movements[0].lot_id == lot_older.id


@pytest.mark.asyncio
async def test_fefo_tiebreak_created_at(session, test_data):
    lot_first = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=NEXT_WEEK,
        received_date=TODAY,
    )
    await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=NEXT_WEEK,
        received_date=TODAY,
    )
    svc = StockService(session)
    movements = await svc.consume(
        test_data["restaurant"],
        test_data["product"],
        Decimal("3"),
        "unit",
        test_data["user"],
    )
    assert movements[0].lot_id == lot_first.id


@pytest.mark.asyncio
async def test_fefo_insufficient_stock_no_side_effects(session, test_data):
    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("2"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    with pytest.raises(InsufficientStockError) as exc_info:
        await svc.consume(
            test_data["restaurant"],
            test_data["product"],
            Decimal("5"),
            "unit",
            test_data["user"],
        )
    assert exc_info.value.requested == Decimal("5")
    assert exc_info.value.available == Decimal("2")
    await session.refresh(lot)
    assert lot.quantity_remaining == Decimal("2")


@pytest.mark.asyncio
async def test_fefo_depleted_lot_ignored(session, test_data):
    await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=TOMORROW,
        status=LotStatus.DEPLETED,
    )
    lot_active = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    movements = await svc.consume(
        test_data["restaurant"],
        test_data["product"],
        Decimal("3"),
        "unit",
        test_data["user"],
    )
    assert len(movements) == 1
    assert movements[0].lot_id == lot_active.id


@pytest.mark.asyncio
async def test_fefo_expired_lot_ignored(session, test_data):
    await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=TODAY - timedelta(days=1),
        status=LotStatus.EXPIRED,
    )
    lot_active = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    movements = await svc.consume(
        test_data["restaurant"],
        test_data["product"],
        Decimal("3"),
        "unit",
        test_data["user"],
    )
    assert movements[0].lot_id == lot_active.id


@pytest.mark.asyncio
async def test_fefo_other_restaurant_lot_invisible(session, test_data):
    await make_lot(
        session,
        test_data["restaurant_b"],
        test_data["product"],
        Decimal("100"),
        expiry_date=TOMORROW,
    )
    await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    movements = await svc.consume(
        test_data["restaurant"],
        test_data["product"],
        Decimal("3"),
        "unit",
        test_data["user"],
    )
    for m in movements:
        result = await session.get(StockLot, m.lot_id)
        assert result is not None
        assert result.restaurant_id == test_data["restaurant"]


@pytest.mark.asyncio
async def test_fefo_partial_consume_marks_depleted(session, test_data):
    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    await svc.consume(
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        "unit",
        test_data["user"],
    )
    await session.refresh(lot)
    assert lot.quantity_remaining == Decimal("0")
    assert lot.status == LotStatus.DEPLETED


@pytest.mark.asyncio
async def test_manual_out_specific_lot(session, test_data):
    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("10"),
        expiry_date=NEXT_MONTH,
    )
    svc = StockService(session)
    movements = await svc.manual_out(
        test_data["restaurant"],
        test_data["product"],
        Decimal("3"),
        "unit",
        test_data["user"],
        lot_id=lot.id,
        reason="damaged",
    )
    assert len(movements) == 1
    assert movements[0].kind == MovementKind.MANUAL_OUT
    await session.refresh(lot)
    assert lot.quantity_remaining == Decimal("7")


@pytest.mark.asyncio
async def test_edit_lot_expiry_creates_audit_log(session, test_data):
    from app.models.audit_log import AuditLog

    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    new_date = NEXT_MONTH
    await svc.edit_lot_expiry(
        test_data["restaurant"],
        lot.id,
        new_expiry_date=new_date,
        reason="supplier_error",
        changed_by_user_id=test_data["user"],
    )
    result = await session.exec(select(AuditLog).where(AuditLog.entity_id == lot.id))
    audit = result.first()
    assert audit is not None
    assert audit.action == "expiry_edit"
    assert audit.reason == "supplier_error"
    assert audit.after_value == {"expiry_date": str(new_date)}


@pytest.mark.asyncio
async def test_receive_creates_lot_and_movement(session, test_data):
    from app.models.stock_movement import StockMovement

    svc = StockService(session)
    lot = await svc.receive(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        supplier_id=None,
        quantity=Decimal("20"),
        unit="unit",
        created_by_user_id=test_data["user"],
        expiry_date=NEXT_WEEK,
    )
    assert lot.quantity_received == Decimal("20")
    assert lot.quantity_remaining == Decimal("20")
    assert lot.status == LotStatus.ACTIVE

    result = await session.exec(select(StockMovement).where(StockMovement.lot_id == lot.id))
    movement = result.first()
    assert movement is not None
    assert movement.kind == MovementKind.RECEIVE
    assert movement.quantity == Decimal("20")


@pytest.mark.asyncio
async def test_receive_with_unit_cost(session, test_data):
    svc = StockService(session)
    lot = await svc.receive(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        supplier_id=None,
        quantity=Decimal("5"),
        unit="kg",
        created_by_user_id=test_data["user"],
        unit_cost=Decimal("2.5000"),
        received_date=TODAY,
    )
    assert lot.unit_cost == Decimal("2.5000")
    assert lot.unit == "kg"


@pytest.mark.asyncio
async def test_manual_in_increases_remaining(session, test_data):
    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    movement = await svc.manual_in(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        lot_id=lot.id,
        quantity=Decimal("3"),
        unit="unit",
        created_by_user_id=test_data["user"],
        reason="recount",
    )
    assert movement.kind == MovementKind.MANUAL_IN
    assert movement.quantity == Decimal("3")
    await session.refresh(lot)
    assert lot.quantity_remaining == Decimal("8")


@pytest.mark.asyncio
async def test_manual_in_reactivates_depleted_lot(session, test_data):
    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("0"),
        expiry_date=NEXT_WEEK,
        status=LotStatus.DEPLETED,
    )
    svc = StockService(session)
    await svc.manual_in(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        lot_id=lot.id,
        quantity=Decimal("5"),
        unit="unit",
        created_by_user_id=test_data["user"],
    )
    await session.refresh(lot)
    assert lot.status == LotStatus.ACTIVE
    assert lot.quantity_remaining == Decimal("5")


@pytest.mark.asyncio
async def test_manual_in_lot_not_found(session, test_data):
    from app.core.exceptions import NotFoundError

    svc = StockService(session)
    with pytest.raises(NotFoundError):
        await svc.manual_in(
            restaurant_id=test_data["restaurant"],
            product_id=test_data["product"],
            lot_id=uuid4(),
            quantity=Decimal("1"),
            unit="unit",
            created_by_user_id=test_data["user"],
        )


@pytest.mark.asyncio
async def test_manual_out_fefo_no_lot_id(session, test_data):
    lot1 = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("4"),
        expiry_date=TOMORROW,
    )
    lot2 = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("10"),
        expiry_date=NEXT_MONTH,
    )
    svc = StockService(session)
    movements = await svc.manual_out(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        quantity=Decimal("6"),
        unit="unit",
        created_by_user_id=test_data["user"],
        reason="spoiled",
    )
    assert len(movements) == 2
    await session.refresh(lot1)
    await session.refresh(lot2)
    assert lot1.status == LotStatus.DEPLETED
    assert lot2.quantity_remaining == Decimal("8")


@pytest.mark.asyncio
async def test_manual_out_specific_lot_insufficient(session, test_data):
    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("2"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    with pytest.raises(InsufficientStockError):
        await svc.manual_out(
            restaurant_id=test_data["restaurant"],
            product_id=test_data["product"],
            quantity=Decimal("5"),
            unit="unit",
            created_by_user_id=test_data["user"],
            lot_id=lot.id,
        )


@pytest.mark.asyncio
async def test_adjustment_positive_increases_remaining(session, test_data):
    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("10"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    movement = await svc.adjustment(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        quantity=Decimal("5"),
        unit="unit",
        reason="recount",
        created_by_user_id=test_data["user"],
        lot_id=lot.id,
    )
    assert movement.kind == MovementKind.ADJUSTMENT
    assert movement.quantity == Decimal("5")
    await session.refresh(lot)
    assert lot.quantity_remaining == Decimal("15")


@pytest.mark.asyncio
async def test_adjustment_negative_decreases_remaining(session, test_data):
    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("10"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    await svc.adjustment(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        quantity=Decimal("-3"),
        unit="unit",
        reason="recount",
        created_by_user_id=test_data["user"],
        lot_id=lot.id,
    )
    await session.refresh(lot)
    assert lot.quantity_remaining == Decimal("7")


@pytest.mark.asyncio
async def test_adjustment_negative_to_zero_marks_depleted(session, test_data):
    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("5"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    await svc.adjustment(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        quantity=Decimal("-5"),
        unit="unit",
        reason="recount",
        created_by_user_id=test_data["user"],
        lot_id=lot.id,
    )
    await session.refresh(lot)
    assert lot.status == LotStatus.DEPLETED


@pytest.mark.asyncio
async def test_adjustment_would_go_negative_raises(session, test_data):
    from app.core.exceptions import ConflictError

    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("3"),
        expiry_date=NEXT_WEEK,
    )
    svc = StockService(session)
    with pytest.raises(ConflictError):
        await svc.adjustment(
            restaurant_id=test_data["restaurant"],
            product_id=test_data["product"],
            quantity=Decimal("-10"),
            unit="unit",
            reason="recount",
            created_by_user_id=test_data["user"],
            lot_id=lot.id,
        )


@pytest.mark.asyncio
async def test_adjustment_no_lot_id_allowed(session, test_data):
    svc = StockService(session)
    movement = await svc.adjustment(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        quantity=Decimal("2"),
        unit="unit",
        reason="bulk_recount",
        created_by_user_id=test_data["user"],
        lot_id=None,
    )
    assert movement.lot_id is None
    assert movement.kind == MovementKind.ADJUSTMENT


@pytest.mark.asyncio
async def test_discard_marks_lot_discarded(session, test_data):
    lot = await make_lot(
        session,
        test_data["restaurant"],
        test_data["product"],
        Decimal("8"),
        expiry_date=TOMORROW,
    )
    svc = StockService(session)
    movement = await svc.discard(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        lot_id=lot.id,
        created_by_user_id=test_data["user"],
        reason="contaminated",
    )
    assert movement.kind == MovementKind.DISCARD
    assert movement.quantity == Decimal("-8")
    await session.refresh(lot)
    assert lot.status == LotStatus.DISCARDED
    assert lot.quantity_remaining == Decimal("0")


@pytest.mark.asyncio
async def test_discard_lot_not_found(session, test_data):
    from app.core.exceptions import NotFoundError

    svc = StockService(session)
    with pytest.raises(NotFoundError):
        await svc.discard(
            restaurant_id=test_data["restaurant"],
            product_id=test_data["product"],
            lot_id=uuid4(),
            created_by_user_id=test_data["user"],
        )


@pytest.mark.asyncio
async def test_stock_movement_source_check_constraint_enforced(session, test_data):
    """Regression guard for the 'recipe' production bug.

    Phase 3 Part 2/3 started writing source='recipe' rows but migration
    003's CHECK constraint hadn't been updated, so production 500'd
    while local tests passed. Tests passed because the pytest fixture
    builds tables via SQLModel.metadata.create_all, which used to skip
    CHECK constraints declared only in alembic migrations. Mirroring
    them in StockMovement.__table_args__ closes that gap — this test
    asserts the mechanism is in place by inserting an invalid `source`
    value and expecting a DB-level violation.
    """
    from sqlalchemy.exc import IntegrityError

    from app.models.stock_movement import StockMovement

    bad = StockMovement(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        lot_id=None,
        kind=MovementKind.CONSUME,
        source="not_a_real_source",
        quantity=Decimal("1"),
        unit="kg",
        created_by_user_id=test_data["user"],
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()
