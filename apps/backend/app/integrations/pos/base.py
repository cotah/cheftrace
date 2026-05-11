"""POS provider abstraction.

Every concrete adapter (Square, Lightspeed, future Flipdish, etc.) takes
a provider-specific webhook payload + a list of items from the provider
API and returns the normalised Pydantic types below. Business code in
services/* and api/* never depends on a concrete adapter — it works off
these types.

Methods are intentionally small and async-only so any HTTP-backed
implementation can plug in without forcing the service layer into
thread pools.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class POSLineItem(BaseModel):
    """One line on a POS order.

    `quantity` is how many of this item were sold in the order. Decimal
    (not int) because Square — and most POS providers — let you sell
    fractional quantities for items priced per kg/litre, and we
    multiply this by the recipe yield before deducting from stock.
    """

    external_item_id: str
    external_item_name: str
    quantity: Decimal


class POSWebhookEvent(BaseModel):
    """Normalised view of a POS webhook payload.

    `raw_payload` is the original JSON, preserved verbatim so the audit
    trail can reconstruct what the provider actually sent. `line_items`
    is the adapter's interpretation; downstream code is allowed to trust
    it but the raw is kept as the source of truth.

    `external_location_id` is how we route the event back to the right
    tenant — providers tag every event with the store/location it came
    from, and we look up the matching PosIntegration by that id.
    """

    model_config = ConfigDict(frozen=True)

    external_event_id: str
    event_type: str
    external_order_id: str | None = None
    external_location_id: str | None = None
    line_items: list[POSLineItem] = []
    raw_payload: dict[str, Any]


class POSItem(BaseModel):
    """A menu item discovered via the provider's catalog API. Used by the
    mapping screen to let the owner pair POS items with ChefTrace recipes.
    """

    model_config = ConfigDict(frozen=True)

    external_id: str
    name: str
    category: str | None = None


class POSAdapter(ABC):
    """Translate between a specific POS provider and our normalised types."""

    @abstractmethod
    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature_header: str,
        signing_key: str,
    ) -> bool:
        """Return True iff `signature_header` is a valid HMAC of `raw_body`
        under `signing_key`. Synchronous because HMAC is CPU-only.
        """

    @abstractmethod
    def parse_webhook(self, raw_body: bytes) -> POSWebhookEvent:
        """Decode the raw bytes of a webhook into a normalised event.

        Implementations should be tolerant of unknown fields — providers
        add new fields over time — but raise on missing required ones
        (event id, type) so the caller can return 400 to the provider.
        """

    @abstractmethod
    async def enrich_event(
        self,
        event: POSWebhookEvent,
        access_token: str,
    ) -> POSWebhookEvent:
        """Return a new event with `line_items` populated.

        Webhook payloads from Square's `payment.*` events don't include
        line items — the adapter is expected to call the provider's
        Orders API to fetch them. For providers (or event types) that
        already deliver line items inline, this can be a no-op that
        returns the input unchanged.

        Called by POSEventProcessor right before mapping + FEFO. The
        access_token is decrypted by the caller and passed in; the
        adapter never sees ciphertext.
        """

    @abstractmethod
    async def list_items(
        self,
        access_token: str,
        location_id: str | None,
    ) -> list[POSItem]:
        """Fetch the full catalog of items for the given location.

        Used by the mapping UI on first connect. Pagination is the
        adapter's concern — return the full list.
        """

    @abstractmethod
    async def fetch_recent_orders(
        self,
        access_token: str,
        location_id: str | None,
        since: datetime,
    ) -> list[POSWebhookEvent]:
        """Pull orders since `since` from the provider's REST API.

        Backs the "Sync now" button in the UI and is the recovery path
        for missed webhooks. Returned events use the same shape webhooks
        produce so downstream processing is identical.
        """
