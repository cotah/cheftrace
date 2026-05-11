"""Phase 4 Part 4a — auto-trigger after webhook.

Tests the `run_processor_in_background` helper that the webhook
endpoint queues via FastAPI BackgroundTasks. The helper opens a fresh
session from the global factory (the request-scoped session is closed
by the time the task runs), so the test monkey-patches that factory
to point at the test engine.

End-to-end FastAPI BackgroundTasks plumbing (i.e. add_task actually
firing after a real Response) is FastAPI's job and not retested here.
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

import app.core.database
import app.models
from app.models.enums import LotStatus, POSConfirmationMode, POSEventStatus
from app.models.pos_event import PosEvent
from app.models.pos_item_mapping import PosItemMapping
from app.models.product import Product
from app.models.recipe import Recipe
from app.models.recipe_ingredient import RecipeIngredient
from app.models.restaurant import Restaurant
from app.models.stock_lot import StockLot
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.services.pos_integration_service import POSIntegrationService
from app.services.pos_webhook_service import run_processor_in_background

TEST_KEY = "test-master-key-only-for-pytest"
TEST_LOCATION_ID = "L_AUTO"


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


@pytest.fixture
async def patched_factory(db_engine, monkeypatch):
    """Replace the global session factory with one bound to the test
    engine, plus the master key needed by the processor service. The
    background task imports `async_session_factory` inside its body,
    so monkey-patching the module attribute works.
    """
    test_factory = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(app.core.database, "async_session_factory", test_factory)
    monkeypatch.setattr(
        "app.core.config.settings.pos_encryption_key",
        TEST_KEY,
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.config.settings.square_webhook_url",
        "https://test.example.com/api/v1/webhooks/pos/square",
        raising=False,
    )
    return test_factory


@pytest.fixture
async def auto_world(session, patched_factory):
    """One restaurant, one Square integration in AUTO mode with credentials,
    one recipe (1 portion = 0.1kg tomato), one mapping, stock = 5kg."""
    user = User(email=f"auto_{uuid4()}@test.com")
    session.add(user)
    restaurant = Restaurant(name="Auto Resto", country="IE")
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
        access_token="test-token",
        webhook_signing_key="test-signing-key",
    )
    await pos_svc.update_integration(
        restaurant.id,
        integration.id,
        confirmation_mode=POSConfirmationMode.AUTO.value,
    )
    await session.commit()

    tomato = Product(restaurant_id=restaurant.id, name="Tomato", unit="kg")
    session.add(tomato)
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
            quantity=Decimal("0.100"),
            unit="kg",
        )
    )
    session.add(
        PosItemMapping(
            restaurant_id=restaurant.id,
            pos_integration_id=integration.id,
            external_item_id="item_pasta",
            external_item_name_snapshot="Tomato Pasta",
            recipe_id=recipe.id,
            units_per_sale=Decimal("1.000"),
        )
    )
    session.add(
        StockLot(
            restaurant_id=restaurant.id,
            product_id=tomato.id,
            quantity_received=Decimal("5.000"),
            quantity_remaining=Decimal("5.000"),
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
        "recipe_id": recipe.id,
    }


async def _insert_event(
    session: AsyncSession,
    *,
    restaurant_id,
    integration_id,
    event_id_text: str,
) -> PosEvent:
    """Build a payload that Square's enrich path normally fetches via
    the Orders API. We don't have Square here — but the processor in
    auto mode for this event will try adapter.enrich_event, which
    triggers an HTTP call. Tests need to bypass that.

    For now this test uses an `order.created`-shaped payload so the
    Square adapter parses line_items inline (no HTTP fetch).
    """
    payload = {
        "event_id": event_id_text,
        "type": "order.created",
        "data": {
            "type": "order",
            "id": "order_auto",
            "object": {
                "order": {
                    "id": "order_auto",
                    "location_id": TEST_LOCATION_ID,
                    "line_items": [
                        {
                            "uid": "li_1",
                            "catalog_object_id": "item_pasta",
                            "name": "Tomato Pasta",
                            "quantity": "2",
                        }
                    ],
                }
            },
        },
    }
    event = PosEvent(
        restaurant_id=restaurant_id,
        pos_integration_id=integration_id,
        provider="square",
        external_event_id=event_id_text,
        external_order_id="order_auto",
        event_type="order.created",
        raw_payload=payload,
        processing_status=POSEventStatus.PENDING.value,
    )
    session.add(event)
    await session.commit()
    return event


@pytest.mark.asyncio
async def test_run_processor_in_background_processes_event(session, auto_world):
    """End-to-end: pending event + auto mode -> processed, stock dropped,
    movements tagged source=POS."""
    event = await _insert_event(
        session,
        restaurant_id=auto_world["restaurant_id"],
        integration_id=auto_world["integration_id"],
        event_id_text="evt_auto_1",
    )

    await run_processor_in_background(
        event_id=event.id,
        restaurant_id=auto_world["restaurant_id"],
        user_id=auto_world["user_id"],
    )

    # The background task ran in its own session and committed. Refresh
    # to see the changes from this session's identity map.
    await session.refresh(event)
    assert event.processing_status == POSEventStatus.PROCESSED.value
    assert event.processed_at is not None

    # 2 portions * 0.1kg = 0.2kg tomato deducted.
    lots = (
        await session.exec(select(StockLot).where(StockLot.product_id == auto_world["tomato_id"]))
    ).all()
    lots_list = list(lots)
    assert len(lots_list) == 1
    assert lots_list[0].quantity_remaining == Decimal("4.800")

    moves = (
        await session.exec(select(StockMovement).where(StockMovement.source_id == event.id))
    ).all()
    moves_list = list(moves)
    assert len(moves_list) == 1
    assert moves_list[0].source == "pos"
    assert moves_list[0].quantity == Decimal("-0.200")


@pytest.mark.asyncio
async def test_run_processor_in_background_swallows_exceptions(session, monkeypatch, auto_world):
    """A failure in the processor must not propagate out of the helper
    — the webhook response is already sent at that point. The event
    is left in whatever state the failure produced (typically `failed`
    or `pending` if the failure was before any write)."""
    event = await _insert_event(
        session,
        restaurant_id=auto_world["restaurant_id"],
        integration_id=auto_world["integration_id"],
        event_id_text="evt_auto_err",
    )

    # Force a failure by removing the access token entry (decryption
    # returns None -> processor flips event to `failed`).
    await session.execute(text("UPDATE pos_integrations SET access_token_encrypted = NULL"))
    await session.commit()

    # Must not raise.
    await run_processor_in_background(
        event_id=event.id,
        restaurant_id=auto_world["restaurant_id"],
        user_id=auto_world["user_id"],
    )

    await session.refresh(event)
    # `failed` is the processor's verdict; the exact state doesn't
    # matter for this test — what matters is the function returned
    # cleanly and recorded SOMETHING terminal-or-actionable.
    assert event.processing_status in {
        POSEventStatus.FAILED.value,
        POSEventStatus.PENDING.value,
    }
