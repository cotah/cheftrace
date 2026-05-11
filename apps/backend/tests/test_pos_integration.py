"""Phase 4 Part 1/4 — POS integration foundation tests.

Covers CRUD on pos_integrations, the pgcrypto-backed credential
round-trip, multi-tenant isolation, the DB-level CHECK constraints
mirrored on the new POS models, and the FakePOSAdapter contract.
"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- register all models with SQLModel.metadata
from app.core.exceptions import ConflictError, NotFoundError
from app.integrations.pos.base import POSItem, POSLineItem, POSWebhookEvent
from app.integrations.pos.fake_provider import FakePOSAdapter
from app.models.enums import POSConfirmationMode
from app.models.pos_event import PosEvent
from app.models.pos_integration import PosIntegration
from app.models.pos_item_mapping import PosItemMapping
from app.models.restaurant import Restaurant
from app.models.user import User
from app.services.pos_integration_service import POSIntegrationService

TEST_KEY = "test-master-key-only-for-pytest"


@pytest.fixture
async def db_engine():
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5433/test",
    )
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        # pgcrypto is required for pgp_sym_encrypt/decrypt. Migrations
        # install it in production; the create_all fixture has to mirror
        # that since it doesn't run migrations.
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
async def scenario(session):
    """Two restaurants + one user for cross-tenant tests."""
    user = User(email=f"pos_{uuid4()}@test.com")
    session.add(user)
    restaurant_a = Restaurant(name="POS Resto A", country="IE")
    session.add(restaurant_a)
    restaurant_b = Restaurant(name="POS Resto B", country="IE")
    session.add(restaurant_b)
    await session.commit()
    return {
        "user_id": user.id,
        "restaurant_a": restaurant_a.id,
        "restaurant_b": restaurant_b.id,
    }


def _service(session: AsyncSession, with_key: bool = True) -> POSIntegrationService:
    return POSIntegrationService(session, encryption_key=TEST_KEY if with_key else None)


# --- POSIntegrationService CRUD --- #


@pytest.mark.asyncio
async def test_create_integration_happy_path(session, scenario):
    svc = _service(session)
    row = await svc.create_integration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="Main POS",
        external_location_id=None,
        created_by_user_id=scenario["user_id"],
    )
    assert row.id is not None
    assert row.provider == "square"
    assert row.name == "Main POS"
    assert row.is_active is True
    assert row.confirmation_mode == POSConfirmationMode.MANUAL
    # Credentials start empty until set_credentials runs.
    assert row.access_token_encrypted is None
    assert row.webhook_signing_key_encrypted is None


@pytest.mark.asyncio
async def test_create_duplicate_provider_raises_conflict(session, scenario):
    svc = _service(session)
    await svc.create_integration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="One",
        external_location_id=None,
        created_by_user_id=scenario["user_id"],
    )
    await session.commit()
    with pytest.raises(ConflictError):
        await svc.create_integration(
            restaurant_id=scenario["restaurant_a"],
            provider="square",
            name="Two",
            external_location_id=None,
            created_by_user_id=scenario["user_id"],
        )


@pytest.mark.asyncio
async def test_list_returns_only_own_restaurant(session, scenario):
    svc = _service(session)
    await svc.create_integration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="A's POS",
        external_location_id=None,
        created_by_user_id=scenario["user_id"],
    )
    await svc.create_integration(
        restaurant_id=scenario["restaurant_b"],
        provider="square",
        name="B's POS",
        external_location_id=None,
        created_by_user_id=scenario["user_id"],
    )
    await session.commit()

    a_rows = await svc.list_integrations(scenario["restaurant_a"])
    assert len(a_rows) == 1
    assert a_rows[0].name == "A's POS"

    b_rows = await svc.list_integrations(scenario["restaurant_b"])
    assert len(b_rows) == 1
    assert b_rows[0].name == "B's POS"


@pytest.mark.asyncio
async def test_get_cross_tenant_returns_404(session, scenario):
    svc = _service(session)
    row = await svc.create_integration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="A's POS",
        external_location_id=None,
        created_by_user_id=scenario["user_id"],
    )
    await session.commit()

    with pytest.raises(NotFoundError):
        await svc.get_integration(scenario["restaurant_b"], row.id)


@pytest.mark.asyncio
async def test_update_partial_preserves_untouched_fields(session, scenario):
    svc = _service(session)
    row = await svc.create_integration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="Original",
        external_location_id="loc_1",
        created_by_user_id=scenario["user_id"],
    )
    await session.commit()

    updated = await svc.update_integration(
        scenario["restaurant_a"],
        row.id,
        confirmation_mode=POSConfirmationMode.AUTO,
    )
    assert updated.confirmation_mode == POSConfirmationMode.AUTO
    assert updated.name == "Original"  # untouched
    assert updated.external_location_id == "loc_1"  # untouched


@pytest.mark.asyncio
async def test_soft_delete_sets_is_active_false(session, scenario):
    svc = _service(session)
    row = await svc.create_integration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="POS",
        external_location_id=None,
        created_by_user_id=scenario["user_id"],
    )
    await session.commit()

    await svc.soft_delete(scenario["restaurant_a"], row.id)
    refreshed = await svc.get_integration(scenario["restaurant_a"], row.id)
    assert refreshed.is_active is False


# --- credential encryption round-trip --- #


@pytest.mark.asyncio
async def test_set_credentials_populates_encrypted_columns(session, scenario):
    svc = _service(session)
    row = await svc.create_integration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="POS",
        external_location_id=None,
        created_by_user_id=scenario["user_id"],
    )
    await session.commit()

    updated = await svc.set_credentials(
        restaurant_id=scenario["restaurant_a"],
        integration_id=row.id,
        access_token="secret-token-123",
        webhook_signing_key="webhook-secret-abc",
    )
    assert updated.access_token_encrypted is not None
    assert updated.webhook_signing_key_encrypted is not None
    # The ciphertext must not literally equal the plaintext.
    assert b"secret-token-123" not in (updated.access_token_encrypted or b"")
    assert b"webhook-secret-abc" not in (updated.webhook_signing_key_encrypted or b"")


@pytest.mark.asyncio
async def test_credentials_round_trip(session, scenario):
    svc = _service(session)
    row = await svc.create_integration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="POS",
        external_location_id=None,
        created_by_user_id=scenario["user_id"],
    )
    await session.commit()
    await svc.set_credentials(
        restaurant_id=scenario["restaurant_a"],
        integration_id=row.id,
        access_token="my-square-token",
        webhook_signing_key="my-signing-key",
    )
    await session.commit()

    token = await svc.get_access_token(scenario["restaurant_a"], row.id)
    signing = await svc.get_webhook_signing_key(scenario["restaurant_a"], row.id)
    assert token == "my-square-token"
    assert signing == "my-signing-key"


@pytest.mark.asyncio
async def test_set_credentials_without_master_key_raises(session, scenario):
    svc = _service(session, with_key=False)
    # Create the integration directly so we can target the credentials call.
    row = PosIntegration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="POS",
        created_by_user_id=scenario["user_id"],
    )
    session.add(row)
    await session.commit()

    with pytest.raises(ConflictError):
        await svc.set_credentials(
            restaurant_id=scenario["restaurant_a"],
            integration_id=row.id,
            access_token="t",
            webhook_signing_key="s",
        )


@pytest.mark.asyncio
async def test_get_access_token_without_credentials_returns_none(session, scenario):
    svc = _service(session)
    row = await svc.create_integration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="POS",
        external_location_id=None,
        created_by_user_id=scenario["user_id"],
    )
    await session.commit()
    assert await svc.get_access_token(scenario["restaurant_a"], row.id) is None


# --- DB-level CHECK constraints mirrored on the models --- #


@pytest.mark.asyncio
async def test_pos_integrations_provider_check_enforced(session, scenario):
    bad = PosIntegration(
        restaurant_id=scenario["restaurant_a"],
        provider="not_a_real_provider",
        name="Bad",
        created_by_user_id=scenario["user_id"],
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_pos_integrations_confirmation_mode_check_enforced(session, scenario):
    bad = PosIntegration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="Bad",
        confirmation_mode="something_else",
        created_by_user_id=scenario["user_id"],
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_pos_events_processing_status_check_enforced(session, scenario):
    integration = PosIntegration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="POS",
        created_by_user_id=scenario["user_id"],
    )
    session.add(integration)
    await session.flush()

    bad = PosEvent(
        restaurant_id=scenario["restaurant_a"],
        pos_integration_id=integration.id,
        provider="square",
        external_event_id="evt_1",
        event_type="order.created",
        raw_payload={"foo": "bar"},
        processing_status="not_a_real_status",
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_pos_events_idempotency_unique(session, scenario):
    """Same (provider, external_event_id) inserted twice must error."""
    integration = PosIntegration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="POS",
        created_by_user_id=scenario["user_id"],
    )
    session.add(integration)
    await session.flush()

    first = PosEvent(
        restaurant_id=scenario["restaurant_a"],
        pos_integration_id=integration.id,
        provider="square",
        external_event_id="evt_dup",
        event_type="order.created",
        raw_payload={"k": "v"},
    )
    session.add(first)
    await session.commit()

    second = PosEvent(
        restaurant_id=scenario["restaurant_a"],
        pos_integration_id=integration.id,
        provider="square",
        external_event_id="evt_dup",
        event_type="order.created",
        raw_payload={"k": "v2"},
    )
    session.add(second)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_pos_item_mapping_units_positive_check_enforced(session, scenario):
    integration = PosIntegration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="POS",
        created_by_user_id=scenario["user_id"],
    )
    session.add(integration)
    await session.flush()

    bad = PosItemMapping(
        restaurant_id=scenario["restaurant_a"],
        pos_integration_id=integration.id,
        external_item_id="item_1",
        external_item_name_snapshot="Pasta",
        units_per_sale=Decimal("0"),
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_pos_item_mapping_with_null_recipe_is_allowed(session, scenario):
    """recipe_id IS NULL is the explicit 'ignore this item' state."""
    integration = PosIntegration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="POS",
        created_by_user_id=scenario["user_id"],
    )
    session.add(integration)
    await session.flush()

    ignored = PosItemMapping(
        restaurant_id=scenario["restaurant_a"],
        pos_integration_id=integration.id,
        external_item_id="gift_card",
        external_item_name_snapshot="Gift Card",
        recipe_id=None,
    )
    session.add(ignored)
    await session.flush()
    assert ignored.id is not None
    assert ignored.recipe_id is None
    # Lookup round-trip preserves the NULL.
    fetched = (
        await session.exec(select(PosItemMapping).where(PosItemMapping.id == ignored.id))
    ).first()
    assert fetched is not None
    assert fetched.recipe_id is None


# --- FakePOSAdapter contract --- #


def test_fake_pos_adapter_default_parse_returns_valid_event():
    adapter = FakePOSAdapter()
    event = adapter.parse_webhook(b'{"id":"x"}')
    assert isinstance(event, POSWebhookEvent)
    assert event.external_event_id == "evt_fake_1"
    assert len(event.line_items) == 1
    assert adapter.parse_calls == [b'{"id":"x"}']


def test_fake_pos_adapter_verify_signature_records_calls_and_obeys_response():
    adapter = FakePOSAdapter()
    assert adapter.verify_webhook_signature(b"body", "sig", "key") is True

    adapter.set_verify_response(False)
    assert adapter.verify_webhook_signature(b"body2", "sig2", "key2") is False
    assert adapter.verify_calls == [
        (b"body", "sig", "key"),
        (b"body2", "sig2", "key2"),
    ]


def test_fake_pos_adapter_parse_response_override():
    adapter = FakePOSAdapter()
    custom = POSWebhookEvent(
        external_event_id="evt_custom",
        event_type="order.fulfilled",
        line_items=[
            POSLineItem(
                external_item_id="item_x",
                external_item_name="Custom Item",
                quantity=3,
            ),
        ],
        raw_payload={"custom": True},
    )
    adapter.set_parse_response(custom)
    out = adapter.parse_webhook(b"anything")
    assert out.external_event_id == "evt_custom"
    assert out.line_items[0].quantity == 3


@pytest.mark.asyncio
async def test_fake_pos_adapter_list_items_returns_canned_response():
    adapter = FakePOSAdapter()
    adapter.set_items_response(
        [
            POSItem(external_id="item_1", name="Pasta", category="Mains"),
            POSItem(external_id="item_2", name="Salad", category="Sides"),
        ]
    )
    out = await adapter.list_items("tok", "loc_1")
    assert len(out) == 2
    assert out[0].name == "Pasta"
    assert adapter.list_items_calls == [("tok", "loc_1")]


# --- regression guard: read schema doesn't leak ciphertext --- #


@pytest.mark.asyncio
async def test_read_schema_only_exposes_has_flags(session, scenario):
    from app.schemas.pos import POSIntegrationRead

    svc = _service(session)
    row = await svc.create_integration(
        restaurant_id=scenario["restaurant_a"],
        provider="square",
        name="POS",
        external_location_id=None,
        created_by_user_id=scenario["user_id"],
    )
    await session.commit()
    await svc.set_credentials(
        restaurant_id=scenario["restaurant_a"],
        integration_id=row.id,
        access_token="should-never-appear",
        webhook_signing_key="also-secret",
    )
    await session.commit()
    refreshed = await svc.get_integration(scenario["restaurant_a"], row.id)

    read = POSIntegrationRead.from_model(refreshed)
    dumped = read.model_dump()
    # The boolean flags are present and true.
    assert dumped["has_access_token"] is True
    assert dumped["has_webhook_signing_key"] is True
    # No field named anything close to the secret is leaked.
    serialised = read.model_dump_json()
    assert "should-never-appear" not in serialised
    assert "also-secret" not in serialised
    assert "encrypted" not in serialised.lower()
