"""Phase 4 Part 2/4 — Square adapter + webhook ingress tests.

The first block runs the SquarePOSAdapter in isolation (pure unit, no
DB) and proves the HMAC contract + payload parsing match Square's
spec. The second block drives process_pos_webhook end-to-end against
a real Postgres + pgcrypto so the routing, idempotency, and
encryption decryption paths exercise actual SQL.
"""

import base64
import hashlib
import hmac
import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- register all models with SQLModel.metadata
from app.core import config as config_module
from app.integrations.pos.square_adapter import SquarePOSAdapter
from app.models.pos_event import PosEvent
from app.models.restaurant import Restaurant
from app.models.user import User
from app.services.pos_integration_service import POSIntegrationService
from app.services.pos_webhook_service import (
    WebhookOutcome,
    process_pos_webhook,
    status_code_for,
)

TEST_KEY = "test-master-key-only-for-pytest"
TEST_WEBHOOK_URL = "https://test.example.com/api/v1/webhooks/pos/square"
TEST_SIGNING_KEY = "test-square-signing-key"
TEST_ACCESS_TOKEN = "test-square-access-token"
TEST_LOCATION_ID = "L_TEST_123"


def _hmac_for(body: bytes, key: str = TEST_SIGNING_KEY, url: str = TEST_WEBHOOK_URL) -> str:
    """Produce the exact header Square would send for `body`."""
    digest = hmac.new(
        key.encode("utf-8"),
        url.encode("utf-8") + body,
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def _payment_created_body(
    *,
    event_id: str = "evt_test_1",
    location_id: str = TEST_LOCATION_ID,
    order_id: str = "order_abc",
    payment_id: str = "pay_abc",
) -> bytes:
    return json.dumps(
        {
            "merchant_id": "MERCHANT_TEST",
            "type": "payment.created",
            "event_id": event_id,
            "created_at": "2026-05-11T10:00:00Z",
            "data": {
                "type": "payment",
                "id": payment_id,
                "object": {
                    "payment": {
                        "id": payment_id,
                        "order_id": order_id,
                        "location_id": location_id,
                        "amount_money": {"amount": 1000, "currency": "EUR"},
                        "status": "APPROVED",
                    }
                },
            },
        },
    ).encode("utf-8")


# ============================================================
# SquarePOSAdapter — pure unit tests
# ============================================================


def test_verify_signature_accepts_valid_hmac():
    adapter = SquarePOSAdapter(notification_url=TEST_WEBHOOK_URL)
    body = _payment_created_body()
    assert adapter.verify_webhook_signature(body, _hmac_for(body), TEST_SIGNING_KEY) is True


def test_verify_signature_rejects_modified_body():
    adapter = SquarePOSAdapter(notification_url=TEST_WEBHOOK_URL)
    body = _payment_created_body()
    sig = _hmac_for(body)
    # Flip one byte — Square's signature was computed on the original.
    tampered = body[:-2] + b"x}"
    assert adapter.verify_webhook_signature(tampered, sig, TEST_SIGNING_KEY) is False


def test_verify_signature_rejects_wrong_signing_key():
    adapter = SquarePOSAdapter(notification_url=TEST_WEBHOOK_URL)
    body = _payment_created_body()
    sig = _hmac_for(body)
    assert adapter.verify_webhook_signature(body, sig, "different-key") is False


def test_verify_signature_rejects_wrong_notification_url():
    """Square mixes the URL into the signed payload, so a verifier with
    the wrong URL fails closed even if the body+key are otherwise right."""
    adapter = SquarePOSAdapter(notification_url="https://other.example.com/x")
    body = _payment_created_body()
    sig = _hmac_for(body)  # computed against TEST_WEBHOOK_URL
    assert adapter.verify_webhook_signature(body, sig, TEST_SIGNING_KEY) is False


def test_verify_signature_rejects_empty_header():
    adapter = SquarePOSAdapter(notification_url=TEST_WEBHOOK_URL)
    body = _payment_created_body()
    assert adapter.verify_webhook_signature(body, "", TEST_SIGNING_KEY) is False


def test_construction_requires_notification_url():
    with pytest.raises(ValueError):
        SquarePOSAdapter(notification_url="")


def test_parse_payment_created_extracts_all_fields():
    adapter = SquarePOSAdapter(notification_url=TEST_WEBHOOK_URL)
    body = _payment_created_body(
        event_id="evt_xyz",
        location_id="L_999",
        order_id="ord_42",
    )
    event = adapter.parse_webhook(body)
    assert event.external_event_id == "evt_xyz"
    assert event.event_type == "payment.created"
    assert event.external_location_id == "L_999"
    assert event.external_order_id == "ord_42"
    assert event.line_items == []  # filled by Part 3/4 via the Orders API
    assert event.raw_payload["merchant_id"] == "MERCHANT_TEST"


def test_parse_order_created_extracts_location_and_id():
    adapter = SquarePOSAdapter(notification_url=TEST_WEBHOOK_URL)
    body = json.dumps(
        {
            "type": "order.created",
            "event_id": "evt_oc_1",
            "data": {
                "type": "order",
                "id": "ord_123",
                "object": {
                    "order": {
                        "id": "ord_123",
                        "location_id": "L_111",
                    }
                },
            },
        }
    ).encode("utf-8")
    event = adapter.parse_webhook(body)
    assert event.external_event_id == "evt_oc_1"
    assert event.event_type == "order.created"
    assert event.external_location_id == "L_111"
    assert event.external_order_id == "ord_123"


def test_parse_rejects_missing_event_id():
    adapter = SquarePOSAdapter(notification_url=TEST_WEBHOOK_URL)
    body = json.dumps({"type": "payment.created", "data": {}}).encode("utf-8")
    with pytest.raises(ValueError, match="event_id"):
        adapter.parse_webhook(body)


def test_parse_rejects_missing_type():
    adapter = SquarePOSAdapter(notification_url=TEST_WEBHOOK_URL)
    body = json.dumps({"event_id": "evt_1", "data": {}}).encode("utf-8")
    with pytest.raises(ValueError, match="type"):
        adapter.parse_webhook(body)


def test_parse_rejects_malformed_json():
    adapter = SquarePOSAdapter(notification_url=TEST_WEBHOOK_URL)
    with pytest.raises(ValueError, match="Malformed JSON"):
        adapter.parse_webhook(b"{not valid")


def test_parse_rejects_non_object_payload():
    adapter = SquarePOSAdapter(notification_url=TEST_WEBHOOK_URL)
    with pytest.raises(ValueError, match="JSON object"):
        adapter.parse_webhook(b"[1, 2, 3]")


def test_list_items_is_a_stub_until_part4():
    """Catalog sync lands in Part 4/4 — this test pins the contract."""
    import asyncio

    adapter = SquarePOSAdapter(notification_url=TEST_WEBHOOK_URL)
    with pytest.raises(NotImplementedError):
        asyncio.get_event_loop().run_until_complete(
            adapter.list_items(access_token="x", location_id=None)
        )


# ============================================================
# process_pos_webhook — integration tests with real Postgres
# ============================================================


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
async def configured_integration(session, monkeypatch):
    """A restaurant + active Square integration with credentials set.

    Monkeypatches settings so the webhook service finds the URL and key
    it needs. Restoring is automatic via pytest's monkeypatch fixture.
    """
    monkeypatch.setattr(config_module.settings, "square_webhook_url", TEST_WEBHOOK_URL)
    monkeypatch.setattr(config_module.settings, "pos_encryption_key", TEST_KEY)

    user = User(email=f"webhook_{uuid4()}@test.com")
    session.add(user)
    restaurant = Restaurant(name="Webhook Resto", country="IE")
    session.add(restaurant)
    await session.commit()

    svc = POSIntegrationService(session, encryption_key=TEST_KEY)
    integration = await svc.create_integration(
        restaurant_id=restaurant.id,
        provider="square",
        name="Main POS",
        external_location_id=TEST_LOCATION_ID,
        created_by_user_id=user.id,
    )
    await session.commit()
    await svc.set_credentials(
        restaurant_id=restaurant.id,
        integration_id=integration.id,
        access_token=TEST_ACCESS_TOKEN,
        webhook_signing_key=TEST_SIGNING_KEY,
    )
    await session.commit()
    return {
        "user_id": user.id,
        "restaurant_id": restaurant.id,
        "integration_id": integration.id,
    }


@pytest.mark.asyncio
async def test_webhook_happy_path_records_pending_event(session, configured_integration):
    body = _payment_created_body(event_id="evt_happy")
    result = await process_pos_webhook(
        session=session,
        provider="square",
        raw_body=body,
        signature_header=_hmac_for(body),
    )
    assert result.outcome == WebhookOutcome.ACCEPTED
    assert status_code_for(result.outcome) == 200
    assert result.pos_event_id is not None

    rows = (await session.exec(select(PosEvent))).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.provider == "square"
    assert row.external_event_id == "evt_happy"
    assert row.external_order_id == "order_abc"
    assert row.event_type == "payment.created"
    assert row.processing_status == "pending"
    assert row.processed_at is None
    assert row.raw_payload["type"] == "payment.created"


@pytest.mark.asyncio
async def test_webhook_replay_returns_replay_outcome(session, configured_integration):
    """Same external_event_id arriving twice must produce one row."""
    body = _payment_created_body(event_id="evt_dup")
    sig = _hmac_for(body)

    first = await process_pos_webhook(session, "square", body, sig)
    assert first.outcome == WebhookOutcome.ACCEPTED

    second = await process_pos_webhook(session, "square", body, sig)
    assert second.outcome == WebhookOutcome.REPLAY
    assert status_code_for(second.outcome) == 200

    rows = (await session.exec(select(PosEvent))).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_webhook_invalid_signature(session, configured_integration):
    body = _payment_created_body()
    result = await process_pos_webhook(
        session=session,
        provider="square",
        raw_body=body,
        signature_header="not-a-valid-signature",
    )
    assert result.outcome == WebhookOutcome.INVALID_SIGNATURE
    assert status_code_for(result.outcome) == 401
    rows = (await session.exec(select(PosEvent))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_webhook_malformed_json(session, configured_integration):
    body = b"{not json"
    result = await process_pos_webhook(
        session=session,
        provider="square",
        raw_body=body,
        signature_header=_hmac_for(body),
    )
    assert result.outcome == WebhookOutcome.MALFORMED_PAYLOAD
    assert status_code_for(result.outcome) == 400


@pytest.mark.asyncio
async def test_webhook_missing_location_returns_silent_200(session, configured_integration):
    """A Square test/ping event without a location must not crash."""
    body = json.dumps(
        {
            "type": "payment.created",
            "event_id": "evt_no_loc",
            "data": {"type": "payment", "id": "p1", "object": {"payment": {"id": "p1"}}},
        }
    ).encode("utf-8")
    result = await process_pos_webhook(
        session=session,
        provider="square",
        raw_body=body,
        signature_header=_hmac_for(body),
    )
    assert result.outcome == WebhookOutcome.NO_LOCATION_ID
    assert status_code_for(result.outcome) == 200


@pytest.mark.asyncio
async def test_webhook_no_integration_for_location(session, configured_integration):
    body = _payment_created_body(location_id="L_DIFFERENT")
    result = await process_pos_webhook(
        session=session,
        provider="square",
        raw_body=body,
        signature_header=_hmac_for(body),
    )
    assert result.outcome == WebhookOutcome.NO_INTEGRATION
    assert status_code_for(result.outcome) == 200
    rows = (await session.exec(select(PosEvent))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_webhook_integration_disabled(session, configured_integration):
    svc = POSIntegrationService(session, encryption_key=TEST_KEY)
    await svc.soft_delete(
        configured_integration["restaurant_id"],
        configured_integration["integration_id"],
    )
    await session.commit()

    body = _payment_created_body()
    result = await process_pos_webhook(
        session=session,
        provider="square",
        raw_body=body,
        signature_header=_hmac_for(body),
    )
    assert result.outcome == WebhookOutcome.INTEGRATION_DISABLED
    assert status_code_for(result.outcome) == 200
    rows = (await session.exec(select(PosEvent))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_webhook_no_signing_key_set(session, monkeypatch):
    """Integration exists but credentials never entered yet."""
    monkeypatch.setattr(config_module.settings, "square_webhook_url", TEST_WEBHOOK_URL)
    monkeypatch.setattr(config_module.settings, "pos_encryption_key", TEST_KEY)

    user = User(email=f"nokey_{uuid4()}@test.com")
    session.add(user)
    restaurant = Restaurant(name="No Key Resto", country="IE")
    session.add(restaurant)
    await session.commit()

    svc = POSIntegrationService(session, encryption_key=TEST_KEY)
    await svc.create_integration(
        restaurant_id=restaurant.id,
        provider="square",
        name="No Key POS",
        external_location_id=TEST_LOCATION_ID,
        created_by_user_id=user.id,
    )
    await session.commit()

    body = _payment_created_body()
    result = await process_pos_webhook(
        session=session,
        provider="square",
        raw_body=body,
        signature_header=_hmac_for(body),
    )
    assert result.outcome == WebhookOutcome.NO_SIGNING_KEY
    assert status_code_for(result.outcome) == 200


@pytest.mark.asyncio
async def test_webhook_unknown_provider(session, configured_integration):
    body = _payment_created_body()
    result = await process_pos_webhook(
        session=session,
        provider="lightspeed",
        raw_body=body,
        signature_header=_hmac_for(body),
    )
    assert result.outcome == WebhookOutcome.UNKNOWN_PROVIDER
    assert status_code_for(result.outcome) == 404


@pytest.mark.asyncio
async def test_webhook_provider_misconfigured(session, configured_integration, monkeypatch):
    """SQUARE_WEBHOOK_URL missing makes the registry raise — surface as 503."""
    monkeypatch.setattr(config_module.settings, "square_webhook_url", None)

    body = _payment_created_body()
    result = await process_pos_webhook(
        session=session,
        provider="square",
        raw_body=body,
        signature_header=_hmac_for(body),
    )
    assert result.outcome == WebhookOutcome.PROVIDER_MISCONFIGURED
    assert status_code_for(result.outcome) == 503
