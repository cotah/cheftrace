"""Square POS adapter — HMAC verify + payment.created parsing.

Sale-to-stock enrichment (looking up the order via Square's Orders API
to get line_items) lives in Part 3/4. This adapter only covers the
webhook ingress path: prove the bytes came from Square, extract the
fields the event-store needs (event_id, type, location_id, order_id),
and hand it off.

References to the Square webhook signature spec:
- Algorithm: HMAC-SHA256
- Signed data: notification_url + raw_body
- Header:     x-square-hmacsha256-signature (base64)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

from app.integrations.pos.base import (
    POSAdapter,
    POSItem,
    POSWebhookEvent,
)


class SquarePOSAdapter(POSAdapter):
    def __init__(self, notification_url: str) -> None:
        if not notification_url:
            # Fail closed at construction. The signature verifier can't run
            # without the URL — Square mixes it into the signed payload.
            raise ValueError("notification_url is required")
        self._notification_url = notification_url

    # --- webhook verification + parsing --- #

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature_header: str,
        signing_key: str,
    ) -> bool:
        if not signature_header:
            return False
        # Reject blatantly malformed base64 headers up front; the
        # `compare_digest` later would catch it but a clean False is
        # easier to reason about.
        try:
            expected_signature = hmac.new(
                signing_key.encode("utf-8"),
                self._notification_url.encode("utf-8") + raw_body,
                hashlib.sha256,
            ).digest()
        except Exception:
            return False
        expected_b64 = base64.b64encode(expected_signature).decode("ascii")
        # Constant-time compare to avoid leaking timing info on near-miss
        # signatures.
        return hmac.compare_digest(expected_b64, signature_header)

    def parse_webhook(self, raw_body: bytes) -> POSWebhookEvent:
        try:
            payload: dict[str, Any] = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")

        event_id = payload.get("event_id")
        event_type = payload.get("type")
        if not event_id or not isinstance(event_id, str):
            raise ValueError("Missing required field: event_id")
        if not event_type or not isinstance(event_type, str):
            raise ValueError("Missing required field: type")

        location_id, order_id = self._extract_location_and_order(payload)

        return POSWebhookEvent(
            external_event_id=event_id,
            event_type=event_type,
            external_order_id=order_id,
            external_location_id=location_id,
            line_items=[],  # populated by Part 3/4 via the Orders API
            raw_payload=payload,
        )

    @staticmethod
    def _extract_location_and_order(
        payload: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        """Walk the known Square payload shapes.

        payment.created -> data.object.payment.{location_id, order_id}
        order.created   -> data.object.order.{location_id, id}
        order.updated   -> data.object.order_updated.{location_id, order_id}

        Returns (location_id, order_id) — either can be None if the
        provider didn't include it. The webhook handler decides what to
        do with None (typically: log + 200 + skip).
        """
        data = payload.get("data") or {}
        obj = data.get("object") or {}

        if isinstance(obj.get("payment"), dict):
            p = obj["payment"]
            return p.get("location_id"), p.get("order_id")
        if isinstance(obj.get("order"), dict):
            o = obj["order"]
            return o.get("location_id"), o.get("id")
        if isinstance(obj.get("order_updated"), dict):
            o = obj["order_updated"]
            return o.get("location_id"), o.get("order_id")
        return None, None

    # --- catalog + history (stubs; Part 4/4 fills these in) --- #

    async def list_items(
        self,
        access_token: str,
        location_id: str | None,
    ) -> list[POSItem]:
        raise NotImplementedError("Square catalog sync lands in Part 4/4 with the mapping UI.")

    async def fetch_recent_orders(
        self,
        access_token: str,
        location_id: str | None,
        since: datetime,
    ) -> list[POSWebhookEvent]:
        raise NotImplementedError("Square 'Sync now' (fetch_recent_orders) lands in Part 4/4.")
