"""In-memory fake POS adapter for tests and local development.

Records every call so tests can assert on the contract. Default
responses cover the happy path; tests inject custom responses via the
`set_*` setters when they need failure or edge-case behaviour.
"""

from datetime import datetime
from decimal import Decimal

from app.integrations.pos.base import (
    POSAdapter,
    POSItem,
    POSLineItem,
    POSWebhookEvent,
)


class FakePOSAdapter(POSAdapter):
    def __init__(self) -> None:
        self.verify_calls: list[tuple[bytes, str, str]] = []
        self.parse_calls: list[bytes] = []
        self.enrich_calls: list[tuple[POSWebhookEvent, str]] = []
        self.list_items_calls: list[tuple[str, str | None]] = []
        self.fetch_orders_calls: list[tuple[str, str | None, datetime]] = []

        self._verify_response: bool = True
        self._parse_response: POSWebhookEvent | None = None
        # Map event_id -> list[POSLineItem]. Lets tests stage different
        # enrichment outcomes per event in one suite.
        self._enrich_line_items: dict[str, list[POSLineItem]] = {}
        self._enrich_raises: Exception | None = None
        self._items_response: list[POSItem] = []
        self._orders_response: list[POSWebhookEvent] = []

    # --- setters used by tests ---

    def set_verify_response(self, value: bool) -> None:
        self._verify_response = value

    def set_parse_response(self, event: POSWebhookEvent) -> None:
        self._parse_response = event

    def set_enrich_line_items(self, event_id: str, line_items: list[POSLineItem]) -> None:
        self._enrich_line_items[event_id] = line_items

    def set_enrich_raises(self, exc: Exception | None) -> None:
        self._enrich_raises = exc

    def set_items_response(self, items: list[POSItem]) -> None:
        self._items_response = items

    def set_orders_response(self, events: list[POSWebhookEvent]) -> None:
        self._orders_response = events

    # --- POSAdapter implementation ---

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature_header: str,
        signing_key: str,
    ) -> bool:
        self.verify_calls.append((raw_body, signature_header, signing_key))
        return self._verify_response

    def parse_webhook(self, raw_body: bytes) -> POSWebhookEvent:
        self.parse_calls.append(raw_body)
        if self._parse_response is not None:
            return self._parse_response
        # Sensible default so tests that don't care can still run.
        return POSWebhookEvent(
            external_event_id="evt_fake_1",
            event_type="order.created",
            external_order_id="order_fake_1",
            line_items=[
                POSLineItem(
                    external_item_id="item_1",
                    external_item_name="Tomato Pasta",
                    quantity=Decimal("1"),
                ),
            ],
            raw_payload={"provider": "fake", "id": "evt_fake_1"},
        )

    async def enrich_event(
        self,
        event: POSWebhookEvent,
        access_token: str,
    ) -> POSWebhookEvent:
        self.enrich_calls.append((event, access_token))
        if self._enrich_raises is not None:
            raise self._enrich_raises
        line_items = self._enrich_line_items.get(event.external_event_id)
        if line_items is None:
            # Default: return event unchanged. Test that wants enrichment
            # must call set_enrich_line_items first.
            return event
        return event.model_copy(update={"line_items": line_items})

    async def list_items(
        self,
        access_token: str,
        location_id: str | None,
    ) -> list[POSItem]:
        self.list_items_calls.append((access_token, location_id))
        return list(self._items_response)

    async def fetch_recent_orders(
        self,
        access_token: str,
        location_id: str | None,
        since: datetime,
    ) -> list[POSWebhookEvent]:
        self.fetch_orders_calls.append((access_token, location_id, since))
        return list(self._orders_response)
