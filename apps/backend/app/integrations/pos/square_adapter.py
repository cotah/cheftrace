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
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.integrations.pos.base import (
    POSAdapter,
    POSItem,
    POSLineItem,
    POSWebhookEvent,
)

# Square REST API version pin. Bumping this requires reading the
# release notes for any line_item shape changes — break that contract
# at update-time, not at request-time.
_SQUARE_API_VERSION = "2024-01-18"
_HTTP_TIMEOUT_SECONDS = 10.0


class SquarePOSAdapter(POSAdapter):
    def __init__(
        self,
        notification_url: str,
        api_base_url: str = "https://connect.squareupsandbox.com",
    ) -> None:
        if not notification_url:
            # Fail closed at construction. The signature verifier can't run
            # without the URL — Square mixes it into the signed payload.
            raise ValueError("notification_url is required")
        if not api_base_url:
            raise ValueError("api_base_url is required")
        self._notification_url = notification_url
        self._api_base_url = api_base_url.rstrip("/")

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

    # --- enrichment (Orders API lookup for payment.* events) --- #

    async def enrich_event(
        self,
        event: POSWebhookEvent,
        access_token: str,
    ) -> POSWebhookEvent:
        """Populate line_items based on the event_type.

        - payment.*   -> GET /v2/orders/{order_id} on Square's REST API
        - order.*     -> line_items are already in the webhook payload
        - everything else -> return unchanged with line_items=[]
        """
        event_type = event.event_type

        if event_type.startswith("payment."):
            if not event.external_order_id:
                # Payment event without an order_id can't be enriched.
                # Returning unchanged with [] lets the processor decide
                # what to do (typically: status=needs_mapping, log).
                return event
            line_items = await self._fetch_order_line_items(access_token, event.external_order_id)
        elif event_type.startswith("order."):
            line_items = self._parse_line_items_from_payload(event.raw_payload)
        else:
            return event

        return event.model_copy(update={"line_items": line_items})

    async def _fetch_order_line_items(self, access_token: str, order_id: str) -> list[POSLineItem]:
        url = f"{self._api_base_url}/v2/orders/{order_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Square-Version": _SQUARE_API_VERSION,
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        order = data.get("order") or {}
        return self._line_items_from_square(order.get("line_items") or [])

    @staticmethod
    def _parse_line_items_from_payload(payload: dict[str, Any]) -> list[POSLineItem]:
        """Walk the payload for an `order` block and parse its line items."""
        data = payload.get("data") or {}
        obj = data.get("object") or {}
        order = obj.get("order") or obj.get("order_updated") or {}
        if not isinstance(order, dict):
            return []
        return SquarePOSAdapter._line_items_from_square(order.get("line_items") or [])

    @staticmethod
    def _line_items_from_square(raw_items: list[dict[str, Any]]) -> list[POSLineItem]:
        """Normalise Square's line_items shape to POSLineItem.

        Square reports `catalog_object_id` (the variation id we map
        against) and `quantity` as a string. Lines without a
        catalog_object_id are ad-hoc items the staff typed in directly;
        they can never be mapped, so we drop them and let the processor
        carry on with the rest. The dropped lines stay visible in
        raw_payload for audit.
        """
        out: list[POSLineItem] = []
        for li in raw_items:
            if not isinstance(li, dict):
                continue
            cat_id = li.get("catalog_object_id")
            if not cat_id or not isinstance(cat_id, str):
                continue
            try:
                qty = Decimal(str(li.get("quantity", "1")))
            except (InvalidOperation, TypeError, ValueError):
                qty = Decimal("1")
            name = li.get("name") or ""
            out.append(
                POSLineItem(
                    external_item_id=cat_id,
                    external_item_name=name if isinstance(name, str) else "",
                    quantity=qty,
                )
            )
        return out

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
