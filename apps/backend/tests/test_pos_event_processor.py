"""Phase 4 Part 3/4 — POSEventProcessor tests.

The processor is the largest piece of new logic in this part — these
tests cover the full state machine (pending -> processed / needs_
mapping / insufficient_stock / pending_approval / failed / ignored)
plus idempotency, force-flag override, and the FEFO + audit_log
side effects on the happy path.
"""

import os
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- register all models with SQLModel.metadata
from app.integrations.pos.base import POSLineItem
from app.integrations.pos.fake_provider import FakePOSAdapter
from app.models.audit_log import AuditLog
from app.models.enums import (
    AuditAction,
    AuditEntity,
    LotStatus,
    MovementSource,
    POSConfirmationMode,
    POSEventStatus,
)
from app.models.pos_event import PosEvent
from app.models.pos_item_mapping import PosItemMapping
from app.models.product import Product
from app.models.recipe import Recipe
from app.models.recipe_ingredient import RecipeIngredient
from app.models.restaurant import Restaurant
from app.models.stock_lot import StockLot
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.services.pos_event_processor_service import POSEventProcessorService
from app.services.pos_integration_service import POSIntegrationService

TEST_KEY = "test-master-key-only-for-pytest"
TEST_LOCATION_ID = "L_TEST_PROC"
TEST_ACCESS_TOKEN = "test-access-token"
TEST_SIGNING_KEY = "test-signing-key"


@pytest.fixture
async def db_engine():
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5433/test",
    )
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
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


async def _seed_world(
    session: AsyncSession,
    *,
    confirmation_mode: str = POSConfirmationMode.AUTO.value,
    tomato_stock: Decimal = Decimal("10.000"),
    onion_stock: Decimal = Decimal("5.000"),
) -> dict:
    """One restaurant + one Square integration with creds + one recipe
    (Tomato Pasta: 0.2kg tomato + 0.05kg onion) + a mapping that says
    each POS sale of `item_pasta` is one portion. Stock quantities are
    parameterisable for shortage tests.
    """
    user = User(email=f"proc_{uuid4()}@test.com")
    session.add(user)
    restaurant = Restaurant(name="Proc Resto", country="IE")
    session.add(restaurant)
    await session.commit()

    pos_svc = POSIntegrationService(session, encryption_key=TEST_KEY)
    integration = await pos_svc.create_integration(
        restaurant_id=restaurant.id,
        provider="square",
        name="Main POS",
        external_location_id=TEST_LOCATION_ID,
        created_by_user_id=user.id,
    )
    await session.commit()
    await pos_svc.set_credentials(
        restaurant_id=restaurant.id,
        integration_id=integration.id,
        access_token=TEST_ACCESS_TOKEN,
        webhook_signing_key=TEST_SIGNING_KEY,
    )
    if confirmation_mode != POSConfirmationMode.MANUAL.value:
        await pos_svc.update_integration(
            restaurant.id,
            integration.id,
            confirmation_mode=confirmation_mode,
        )
    await session.commit()

    tomato = Product(restaurant_id=restaurant.id, name="Tomato", unit="kg")
    onion = Product(restaurant_id=restaurant.id, name="Onion", unit="kg")
    session.add(tomato)
    session.add(onion)
    await session.commit()

    recipe = Recipe(
        restaurant_id=restaurant.id,
        name="Tomato Pasta",
        yield_quantity=Decimal("1"),
        yield_unit="portion",
    )
    session.add(recipe)
    await session.commit()
    session.add(
        RecipeIngredient(
            restaurant_id=restaurant.id,
            recipe_id=recipe.id,
            product_id=tomato.id,
            quantity=Decimal("0.200"),
            unit="kg",
        )
    )
    session.add(
        RecipeIngredient(
            restaurant_id=restaurant.id,
            recipe_id=recipe.id,
            product_id=onion.id,
            quantity=Decimal("0.050"),
            unit="kg",
        )
    )
    await session.commit()

    mapping = PosItemMapping(
        restaurant_id=restaurant.id,
        pos_integration_id=integration.id,
        external_item_id="item_pasta",
        external_item_name_snapshot="Tomato Pasta",
        recipe_id=recipe.id,
        units_per_sale=Decimal("1.000"),
    )
    session.add(mapping)
    await session.commit()

    if tomato_stock > 0:
        session.add(
            StockLot(
                restaurant_id=restaurant.id,
                product_id=tomato.id,
                quantity_received=tomato_stock,
                quantity_remaining=tomato_stock,
                unit="kg",
                expiry_date=date.today() + timedelta(days=14),
                received_date=date.today(),
                status=LotStatus.ACTIVE,
                created_by_user_id=user.id,
            )
        )
    if onion_stock > 0:
        session.add(
            StockLot(
                restaurant_id=restaurant.id,
                product_id=onion.id,
                quantity_received=onion_stock,
                quantity_remaining=onion_stock,
                unit="kg",
                expiry_date=date.today() + timedelta(days=14),
                received_date=date.today(),
                status=LotStatus.ACTIVE,
                created_by_user_id=user.id,
            )
        )
    await session.commit()

    return {
        "user_id": user.id,
        "restaurant_id": restaurant.id,
        "integration_id": integration.id,
        "tomato_id": tomato.id,
        "onion_id": onion.id,
        "recipe_id": recipe.id,
        "mapping_id": mapping.id,
    }


async def _insert_pending_event(
    session: AsyncSession,
    *,
    restaurant_id,
    integration_id,
    external_event_id: str = "evt_proc_1",
    external_order_id: str = "ord_1",
) -> PosEvent:
    event = PosEvent(
        restaurant_id=restaurant_id,
        pos_integration_id=integration_id,
        provider="square",
        external_event_id=external_event_id,
        external_order_id=external_order_id,
        event_type="payment.created",
        raw_payload={"event_id": external_event_id, "type": "payment.created"},
        processing_status=POSEventStatus.PENDING.value,
    )
    session.add(event)
    await session.commit()
    return event


def _adapter_factory_with(fake: FakePOSAdapter):
    """Build a callable that returns this exact FakePOSAdapter."""

    def factory(provider: str) -> FakePOSAdapter:
        if provider != "square":
            raise ValueError(f"Unknown provider in test: {provider}")
        return fake

    return factory


# --- happy path --- #


@pytest.mark.asyncio
async def test_auto_mode_processes_and_deducts_stock(session):
    world = await _seed_world(session, confirmation_mode=POSConfirmationMode.AUTO.value)
    event = await _insert_pending_event(
        session,
        restaurant_id=world["restaurant_id"],
        integration_id=world["integration_id"],
    )

    fake = FakePOSAdapter()
    fake.set_enrich_line_items(
        event.external_event_id,
        [
            POSLineItem(
                external_item_id="item_pasta",
                external_item_name="Tomato Pasta",
                quantity=Decimal("2"),
            ),
        ],
    )
    proc = POSEventProcessorService(session, TEST_KEY, _adapter_factory_with(fake))

    result = await proc.process_event(world["restaurant_id"], event.id, world["user_id"])
    assert result.status == POSEventStatus.PROCESSED
    # 2 portions x (1 tomato_movement + 1 onion_movement) -- but the
    # service aggregates per-product before calling consume, so one
    # FEFO consumption per product per event. With one lot per product
    # we get 1 movement per product = 2 movements total.
    assert result.movements_created == 2

    # Stock decremented: 2 portions x 0.2 = 0.4kg tomato, 0.1kg onion.
    refreshed = await session.exec(select(StockLot))
    lots = list(refreshed.all())
    tomato_lot = next(lot for lot in lots if lot.product_id == world["tomato_id"])
    onion_lot = next(lot for lot in lots if lot.product_id == world["onion_id"])
    assert tomato_lot.quantity_remaining == Decimal("9.600")
    assert onion_lot.quantity_remaining == Decimal("4.900")

    # Movements tagged with the POS source + source_id.
    moves = (
        await session.exec(select(StockMovement).where(StockMovement.source_id == event.id))
    ).all()
    moves_list = list(moves)
    assert len(moves_list) == 2
    for m in moves_list:
        assert m.source == MovementSource.POS
        assert m.kind == "consume"
        assert m.quantity < 0

    # Event status persisted.
    refreshed_event = (await session.exec(select(PosEvent).where(PosEvent.id == event.id))).first()
    assert refreshed_event is not None
    assert refreshed_event.processing_status == POSEventStatus.PROCESSED.value
    assert refreshed_event.processed_at is not None

    # Audit log written.
    audits = (await session.exec(select(AuditLog).where(AuditLog.entity_id == event.id))).all()
    audits_list = list(audits)
    assert len(audits_list) == 1
    assert audits_list[0].entity_type == AuditEntity.POS_EVENT
    assert audits_list[0].action == AuditAction.POS_PROCESSED
    assert audits_list[0].after_value["processing_status"] == "processed"


# --- manual mode --- #


@pytest.mark.asyncio
async def test_manual_mode_holds_at_pending_approval(session):
    world = await _seed_world(session, confirmation_mode=POSConfirmationMode.MANUAL.value)
    event = await _insert_pending_event(
        session,
        restaurant_id=world["restaurant_id"],
        integration_id=world["integration_id"],
    )

    fake = FakePOSAdapter()
    fake.set_enrich_line_items(
        event.external_event_id,
        [POSLineItem(external_item_id="item_pasta", external_item_name="x", quantity=Decimal("1"))],
    )
    proc = POSEventProcessorService(session, TEST_KEY, _adapter_factory_with(fake))

    result = await proc.process_event(world["restaurant_id"], event.id, world["user_id"])
    assert result.status == POSEventStatus.PENDING_APPROVAL
    assert result.movements_created == 0

    # No stock movements created.
    moves = (await session.exec(select(StockMovement))).all()
    assert list(moves) == []


@pytest.mark.asyncio
async def test_force_processes_pending_approval(session):
    """The Approve button path: force=True bypasses the manual gate."""
    world = await _seed_world(session, confirmation_mode=POSConfirmationMode.MANUAL.value)
    event = await _insert_pending_event(
        session,
        restaurant_id=world["restaurant_id"],
        integration_id=world["integration_id"],
    )

    fake = FakePOSAdapter()
    fake.set_enrich_line_items(
        event.external_event_id,
        [POSLineItem(external_item_id="item_pasta", external_item_name="x", quantity=Decimal("1"))],
    )
    proc = POSEventProcessorService(session, TEST_KEY, _adapter_factory_with(fake))

    # First call: lands in pending_approval.
    first = await proc.process_event(world["restaurant_id"], event.id, world["user_id"])
    assert first.status == POSEventStatus.PENDING_APPROVAL

    # Second call with force=True: actually deducts.
    second = await proc.process_event(
        world["restaurant_id"], event.id, world["user_id"], force=True
    )
    assert second.status == POSEventStatus.PROCESSED
    assert second.movements_created == 2


# --- idempotency + locking --- #


@pytest.mark.asyncio
async def test_processed_event_is_idempotent(session):
    world = await _seed_world(session)
    event = await _insert_pending_event(
        session,
        restaurant_id=world["restaurant_id"],
        integration_id=world["integration_id"],
    )

    fake = FakePOSAdapter()
    fake.set_enrich_line_items(
        event.external_event_id,
        [POSLineItem(external_item_id="item_pasta", external_item_name="x", quantity=Decimal("1"))],
    )
    proc = POSEventProcessorService(session, TEST_KEY, _adapter_factory_with(fake))

    await proc.process_event(world["restaurant_id"], event.id, world["user_id"])
    # Snapshot movements after first run.
    moves_after_first = (await session.exec(select(StockMovement))).all()
    count_after_first = len(list(moves_after_first))

    # Second call must NOT re-deduct.
    result = await proc.process_event(world["restaurant_id"], event.id, world["user_id"])
    assert result.status == POSEventStatus.PROCESSED
    assert result.movements_created == 0  # nothing new created

    moves_after_second = (await session.exec(select(StockMovement))).all()
    assert len(list(moves_after_second)) == count_after_first


# --- failure / blocker states --- #


@pytest.mark.asyncio
async def test_unmapped_item_lands_in_needs_mapping(session):
    world = await _seed_world(session)
    event = await _insert_pending_event(
        session,
        restaurant_id=world["restaurant_id"],
        integration_id=world["integration_id"],
    )

    fake = FakePOSAdapter()
    fake.set_enrich_line_items(
        event.external_event_id,
        [
            POSLineItem(
                external_item_id="item_unknown",
                external_item_name="Mystery Item",
                quantity=Decimal("1"),
            ),
        ],
    )
    proc = POSEventProcessorService(session, TEST_KEY, _adapter_factory_with(fake))

    result = await proc.process_event(world["restaurant_id"], event.id, world["user_id"])
    assert result.status == POSEventStatus.NEEDS_MAPPING
    assert "item_unknown" in result.unmapped_item_ids
    # No stock touched.
    moves = (await session.exec(select(StockMovement))).all()
    assert list(moves) == []


@pytest.mark.asyncio
async def test_insufficient_stock_blocks_deduction(session):
    world = await _seed_world(
        session,
        confirmation_mode=POSConfirmationMode.AUTO.value,
        tomato_stock=Decimal("0.100"),  # << recipe needs 0.2/portion
        onion_stock=Decimal("5.000"),
    )
    event = await _insert_pending_event(
        session,
        restaurant_id=world["restaurant_id"],
        integration_id=world["integration_id"],
    )

    fake = FakePOSAdapter()
    fake.set_enrich_line_items(
        event.external_event_id,
        [POSLineItem(external_item_id="item_pasta", external_item_name="x", quantity=Decimal("1"))],
    )
    proc = POSEventProcessorService(session, TEST_KEY, _adapter_factory_with(fake))

    result = await proc.process_event(world["restaurant_id"], event.id, world["user_id"])
    assert result.status == POSEventStatus.INSUFFICIENT_STOCK
    assert world["tomato_id"] in result.insufficient_product_ids
    # Onion not touched either — all-or-nothing.
    moves = (await session.exec(select(StockMovement))).all()
    assert list(moves) == []


@pytest.mark.asyncio
async def test_inactive_integration_becomes_ignored(session):
    world = await _seed_world(session)
    event = await _insert_pending_event(
        session,
        restaurant_id=world["restaurant_id"],
        integration_id=world["integration_id"],
    )
    pos_svc = POSIntegrationService(session, encryption_key=TEST_KEY)
    await pos_svc.soft_delete(world["restaurant_id"], world["integration_id"])
    await session.commit()

    fake = FakePOSAdapter()
    proc = POSEventProcessorService(session, TEST_KEY, _adapter_factory_with(fake))

    result = await proc.process_event(world["restaurant_id"], event.id, world["user_id"])
    assert result.status == POSEventStatus.IGNORED


@pytest.mark.asyncio
async def test_enrich_raising_marks_failed(session):
    """A Square Orders API outage (or any adapter exception) parks the
    event in `failed` so a later retry can pick it up."""
    world = await _seed_world(session)
    event = await _insert_pending_event(
        session,
        restaurant_id=world["restaurant_id"],
        integration_id=world["integration_id"],
    )

    fake = FakePOSAdapter()
    fake.set_enrich_raises(RuntimeError("Square 5xx"))
    proc = POSEventProcessorService(session, TEST_KEY, _adapter_factory_with(fake))

    result = await proc.process_event(world["restaurant_id"], event.id, world["user_id"])
    assert result.status == POSEventStatus.FAILED
    assert "Square 5xx" in (result.error_message or "")


@pytest.mark.asyncio
async def test_ignore_state_mapping_does_not_deduct(session):
    """recipe_id IS NULL means the operator explicitly suppressed this
    item — sale should land in PROCESSED with zero movements."""
    world = await _seed_world(session)
    # Add a second mapping for a different POS item, mapped to None.
    session.add(
        PosItemMapping(
            restaurant_id=world["restaurant_id"],
            pos_integration_id=world["integration_id"],
            external_item_id="item_gift_card",
            external_item_name_snapshot="Gift Card",
            recipe_id=None,  # ignore
        )
    )
    await session.commit()

    event = await _insert_pending_event(
        session,
        restaurant_id=world["restaurant_id"],
        integration_id=world["integration_id"],
    )
    fake = FakePOSAdapter()
    fake.set_enrich_line_items(
        event.external_event_id,
        [
            POSLineItem(
                external_item_id="item_gift_card",
                external_item_name="Gift Card",
                quantity=Decimal("1"),
            ),
        ],
    )
    proc = POSEventProcessorService(session, TEST_KEY, _adapter_factory_with(fake))

    result = await proc.process_event(world["restaurant_id"], event.id, world["user_id"])
    assert result.status == POSEventStatus.PROCESSED
    assert result.movements_created == 0
    moves = (await session.exec(select(StockMovement))).all()
    assert list(moves) == []


# --- dismiss --- #


@pytest.mark.asyncio
async def test_dismiss_marks_ignored_with_audit(session):
    world = await _seed_world(session)
    event = await _insert_pending_event(
        session,
        restaurant_id=world["restaurant_id"],
        integration_id=world["integration_id"],
    )
    proc = POSEventProcessorService(session, TEST_KEY, _adapter_factory_with(FakePOSAdapter()))

    result = await proc.dismiss_event(
        world["restaurant_id"], event.id, world["user_id"], reason="test event from Square"
    )
    assert result.status == POSEventStatus.IGNORED

    refreshed = (await session.exec(select(PosEvent).where(PosEvent.id == event.id))).first()
    assert refreshed is not None
    assert refreshed.processing_status == POSEventStatus.IGNORED.value
    assert refreshed.error_message == "test event from Square"

    audits = (await session.exec(select(AuditLog).where(AuditLog.entity_id == event.id))).all()
    audits_list = list(audits)
    assert len(audits_list) == 1
    assert audits_list[0].action == AuditAction.POS_DISMISSED


@pytest.mark.asyncio
async def test_dismiss_after_processed_is_noop(session):
    """Terminal states stay terminal."""
    world = await _seed_world(session)
    event = await _insert_pending_event(
        session,
        restaurant_id=world["restaurant_id"],
        integration_id=world["integration_id"],
    )
    fake = FakePOSAdapter()
    fake.set_enrich_line_items(
        event.external_event_id,
        [POSLineItem(external_item_id="item_pasta", external_item_name="x", quantity=Decimal("1"))],
    )
    proc = POSEventProcessorService(session, TEST_KEY, _adapter_factory_with(fake))
    await proc.process_event(world["restaurant_id"], event.id, world["user_id"])

    result = await proc.dismiss_event(
        world["restaurant_id"], event.id, world["user_id"], reason="too late"
    )
    assert result.status == POSEventStatus.PROCESSED  # unchanged
