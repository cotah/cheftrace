"""Webhook ingress for POS providers.

This module orchestrates the receive path end-to-end so the FastAPI
endpoint stays a thin shim. The split lets tests drive the full flow
with a real session and skip the HTTP layer.

Steps, in order:
  1. Resolve adapter from provider name.
  2. Parse the raw body just enough to read event_id, type, location_id.
  3. Look up the active integration that owns the location_id.
  4. Decrypt the webhook signing key via pgcrypto.
  5. Verify the HMAC signature with constant-time compare.
  6. Insert into pos_events with ON CONFLICT DO NOTHING for idempotency.

The handler never processes the event (no Square API call, no FEFO
deduction) — that's Part 3/4's job, on the queue of pending events.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.integrations.pos.registry import get_pos_adapter
from app.models.pos_integration import PosIntegration
from app.services.pos_integration_service import POSIntegrationService

if TYPE_CHECKING:
    from app.integrations.pos.base import POSWebhookEvent

logger = structlog.get_logger(__name__)


class WebhookOutcome(StrEnum):
    """All terminal states of webhook receipt.

    The endpoint maps each to an HTTP status. Several outcomes intentionally
    map to 200 so the provider doesn't retry forever — webhooks for an
    unconfigured location or a disabled integration are not "errors" from
    Square's perspective; they're just no-ops on our side.
    """

    ACCEPTED = "accepted"
    REPLAY = "replay"
    UNKNOWN_PROVIDER = "unknown_provider"
    PROVIDER_MISCONFIGURED = "provider_misconfigured"
    MALFORMED_PAYLOAD = "malformed_payload"
    NO_LOCATION_ID = "no_location_id"
    NO_INTEGRATION = "no_integration"
    INTEGRATION_DISABLED = "integration_disabled"
    NO_SIGNING_KEY = "no_signing_key"
    INVALID_SIGNATURE = "invalid_signature"


_STATUS_FOR: dict[WebhookOutcome, int] = {
    WebhookOutcome.ACCEPTED: 200,
    WebhookOutcome.REPLAY: 200,
    WebhookOutcome.UNKNOWN_PROVIDER: 404,
    WebhookOutcome.PROVIDER_MISCONFIGURED: 503,
    WebhookOutcome.MALFORMED_PAYLOAD: 400,
    # The next four are "silently OK" — return 200 so the provider stops
    # retrying. We still log a warning so the operator notices.
    WebhookOutcome.NO_LOCATION_ID: 200,
    WebhookOutcome.NO_INTEGRATION: 200,
    WebhookOutcome.INTEGRATION_DISABLED: 200,
    WebhookOutcome.NO_SIGNING_KEY: 200,
    WebhookOutcome.INVALID_SIGNATURE: 401,
}


def status_code_for(outcome: WebhookOutcome) -> int:
    return _STATUS_FOR[outcome]


@dataclass(frozen=True)
class WebhookResult:
    outcome: WebhookOutcome
    pos_event_id: str | None = None  # set when an INSERT happened
    detail: str | None = None  # human-readable explanation, useful in logs


async def process_pos_webhook(
    session: AsyncSession,
    provider: str,
    raw_body: bytes,
    signature_header: str,
) -> WebhookResult:
    # Step 1: provider -> adapter
    try:
        adapter = get_pos_adapter(provider)
    except ValueError as exc:
        return WebhookResult(WebhookOutcome.UNKNOWN_PROVIDER, detail=str(exc))
    except RuntimeError as exc:
        # E.g. SQUARE_WEBHOOK_URL missing. Don't reveal config details.
        logger.warning("pos.webhook.provider_misconfigured", provider=provider, error=str(exc))
        return WebhookResult(WebhookOutcome.PROVIDER_MISCONFIGURED)

    # Step 2: shallow parse to find the routing fields
    try:
        event: POSWebhookEvent = adapter.parse_webhook(raw_body)
    except ValueError as exc:
        return WebhookResult(WebhookOutcome.MALFORMED_PAYLOAD, detail=str(exc))

    if not event.external_location_id:
        logger.warning(
            "pos.webhook.no_location_id",
            provider=provider,
            event_id=event.external_event_id,
        )
        return WebhookResult(WebhookOutcome.NO_LOCATION_ID)

    # Step 3: find the integration that owns this location
    integration_result = await session.exec(
        select(PosIntegration).where(
            PosIntegration.provider == provider,
            PosIntegration.external_location_id == event.external_location_id,
        )
    )
    integration = integration_result.first()
    if integration is None:
        logger.warning(
            "pos.webhook.no_integration",
            provider=provider,
            location_id=event.external_location_id,
            event_id=event.external_event_id,
        )
        return WebhookResult(WebhookOutcome.NO_INTEGRATION)

    if not integration.is_active:
        logger.warning(
            "pos.webhook.integration_disabled",
            integration_id=str(integration.id),
            event_id=event.external_event_id,
        )
        return WebhookResult(WebhookOutcome.INTEGRATION_DISABLED)

    # Step 4: decrypt signing key (requires POS_ENCRYPTION_KEY)
    if integration.webhook_signing_key_encrypted is None:
        logger.warning(
            "pos.webhook.no_signing_key",
            integration_id=str(integration.id),
        )
        return WebhookResult(WebhookOutcome.NO_SIGNING_KEY)

    pos_service = POSIntegrationService(session, settings.pos_encryption_key)
    signing_key = await pos_service.get_webhook_signing_key(
        integration.restaurant_id, integration.id
    )
    if not signing_key:
        return WebhookResult(WebhookOutcome.NO_SIGNING_KEY)

    # Step 5: HMAC verify
    if not adapter.verify_webhook_signature(raw_body, signature_header, signing_key):
        logger.warning(
            "pos.webhook.invalid_signature",
            integration_id=str(integration.id),
            event_id=event.external_event_id,
        )
        return WebhookResult(WebhookOutcome.INVALID_SIGNATURE)

    # Step 6: idempotent insert.
    # NOW() for created_at + updated_at because TimestampedBase uses a
    # Python-side default_factory rather than a server_default — the
    # raw INSERT path bypasses Python defaults, so we set the values
    # explicitly. Works whether the schema came from alembic
    # (server_default redundant here) or from create_all in tests
    # (no server_default at all).
    new_event_id = uuid4()
    insert_result = await session.execute(
        text(
            "INSERT INTO pos_events ("
            "id, restaurant_id, pos_integration_id, provider, "
            "external_event_id, external_order_id, event_type, "
            "raw_payload, processing_status, "
            "created_at, updated_at"
            ") VALUES ("
            ":id, :rid, :iid, :provider, "
            ":ext_event, :ext_order, :event_type, "
            "CAST(:payload AS JSONB), 'pending', "
            "NOW(), NOW()"
            ") ON CONFLICT (provider, external_event_id) DO NOTHING "
            "RETURNING id"
        ),
        {
            "id": new_event_id,
            "rid": integration.restaurant_id,
            "iid": integration.id,
            "provider": provider,
            "ext_event": event.external_event_id,
            "ext_order": event.external_order_id,
            "event_type": event.event_type,
            "payload": json.dumps(event.raw_payload),
        },
    )
    inserted_row = insert_result.first()
    await session.commit()

    if inserted_row is None:
        # Idempotency win — same external_event_id arrived twice.
        logger.info(
            "pos.webhook.replay",
            provider=provider,
            event_id=event.external_event_id,
        )
        return WebhookResult(WebhookOutcome.REPLAY)

    logger.info(
        "pos.webhook.accepted",
        provider=provider,
        event_id=event.external_event_id,
        pos_event_id=str(inserted_row[0]),
    )
    return WebhookResult(
        WebhookOutcome.ACCEPTED,
        pos_event_id=str(inserted_row[0]),
    )
