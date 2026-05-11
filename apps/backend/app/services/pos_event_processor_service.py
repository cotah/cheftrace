"""POS event processor — enrich, map, FEFO-deduct.

Picks up a `pos_event` row, fetches the order line items via the
provider's API (Square: Orders API; future providers: their
equivalent), translates line items to recipes, and either deducts
stock via FEFO or files the event for owner attention.

The state machine
  pending           : just arrived from the webhook
    -> processed              (auto mode + all green)
    -> pending_approval       (manual mode + all green, waiting for human)
    -> needs_mapping          (one or more items not mapped)
    -> insufficient_stock     (FEFO can't satisfy demand)
    -> failed                 (enrich error, decryption error, etc.)
    -> ignored                (integration inactive)
  pending_approval  -> processed (via force=True from approve endpoint)
  needs_mapping     -> any of the above (after owner adds mapping + retry)
  insufficient_stock -> any of the above (after stock added + retry)
  failed            -> any of the above (transient errors retry)
  processed | ignored : terminal (idempotent re-process returns current)

Locking
  SELECT ... FOR UPDATE on the event row blocks concurrent processors
  for the same event. The second caller then sees a terminal status
  and returns the current state without re-deducting.

Audit
  Every non-trivial state transition writes one audit_logs row with
  before_value/after_value snapshots so the timeline of an event is
  reconstructable post-hoc.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import NotFoundError
from app.integrations.pos.base import POSAdapter, POSWebhookEvent
from app.models.audit_log import AuditLog
from app.models.base import utcnow
from app.models.enums import (
    AuditAction,
    AuditEntity,
    MovementSource,
    POSConfirmationMode,
    POSEventStatus,
)
from app.models.pos_event import PosEvent
from app.models.pos_integration import PosIntegration
from app.models.pos_item_mapping import PosItemMapping
from app.models.product import Product
from app.models.recipe import Recipe
from app.models.recipe_ingredient import RecipeIngredient
from app.services.pos_integration_service import POSIntegrationService
from app.services.stock_service import StockService

logger = structlog.get_logger(__name__)


# Statuses that are terminal — a second process_event call returns
# immediately with the current state, no work, no second deduction.
_TERMINAL_STATUSES = frozenset({POSEventStatus.PROCESSED, POSEventStatus.IGNORED})


@dataclass(frozen=True)
class ProcessingResult:
    status: POSEventStatus
    movements_created: int = 0
    error_message: str | None = None
    unmapped_item_ids: list[str] = field(default_factory=list)
    insufficient_product_ids: list[UUID] = field(default_factory=list)


class POSEventProcessorService:
    """One processor instance per request. Holds the adapter factory
    so tests can inject FakePOSAdapter without touching settings.
    """

    def __init__(
        self,
        session: AsyncSession,
        encryption_key: str | None,
        adapter_factory: Callable[[str], POSAdapter],
    ) -> None:
        self._session = session
        self._encryption_key = encryption_key
        self._adapter_factory = adapter_factory
        self._pos_service = POSIntegrationService(session, encryption_key)
        self._stock_service = StockService(session)

    # --- public entry points --- #

    async def process_event(
        self,
        restaurant_id: UUID,
        event_id: UUID,
        user_id: UUID,
        *,
        force: bool = False,
    ) -> ProcessingResult:
        """Run the full pipeline on a single event.

        `force=True` skips the manual-mode gate. Used by the approve
        endpoint so a human can release a pending_approval event.
        """
        event = await self._load_event_for_update(restaurant_id, event_id)
        previous_status = POSEventStatus(event.processing_status)

        # Idempotency: terminal states return immediately.
        if previous_status in _TERMINAL_STATUSES:
            return ProcessingResult(status=previous_status)

        integration = await self._load_integration(event.pos_integration_id)
        if integration is None or not integration.is_active:
            return await self._finalize(
                event,
                previous_status,
                user_id,
                POSEventStatus.IGNORED,
                error_message="Integration is inactive or missing",
                reason="integration_inactive",
            )

        try:
            access_token = await self._pos_service.get_access_token(restaurant_id, integration.id)
        except Exception as exc:
            return await self._finalize(
                event,
                previous_status,
                user_id,
                POSEventStatus.FAILED,
                error_message=f"decrypt failed: {exc}",
                reason="decrypt_failed",
            )
        if not access_token:
            return await self._finalize(
                event,
                previous_status,
                user_id,
                POSEventStatus.FAILED,
                error_message="Integration has no access token",
                reason="no_access_token",
            )

        adapter = self._adapter_factory(integration.provider)

        parsed_event = POSWebhookEvent(
            external_event_id=event.external_event_id,
            event_type=event.event_type,
            external_order_id=event.external_order_id,
            external_location_id=integration.external_location_id,
            line_items=[],
            raw_payload=event.raw_payload,
        )
        try:
            enriched = await adapter.enrich_event(parsed_event, access_token)
        except Exception as exc:
            # Square API down, 4xx/5xx, JSON malformed, etc. Mark failed
            # so the retry endpoint can pick it up later — clear out the
            # stale error on success.
            return await self._finalize(
                event,
                previous_status,
                user_id,
                POSEventStatus.FAILED,
                error_message=f"enrich failed: {exc}"[:500],
                reason="enrich_failed",
            )

        if not enriched.line_items:
            # Could be an event type we don't deduct on (refund, void,
            # etc.) or an order with no catalog-mapped lines. Either
            # way, audit and move on.
            return await self._finalize(
                event,
                previous_status,
                user_id,
                POSEventStatus.IGNORED,
                error_message="No line items to process",
                reason="empty_line_items",
            )

        # Map every line item to a PosItemMapping row.
        mappings_by_ext = await self._load_mappings(
            integration.id,
            [li.external_item_id for li in enriched.line_items],
        )
        unmapped = [
            li.external_item_id
            for li in enriched.line_items
            if li.external_item_id not in mappings_by_ext
        ]
        if unmapped:
            return await self._finalize(
                event,
                previous_status,
                user_id,
                POSEventStatus.NEEDS_MAPPING,
                error_message=f"Unmapped items: {len(unmapped)}",
                reason="needs_mapping",
                unmapped_item_ids=unmapped,
            )

        # Build consumption: product -> total quantity (in product's unit).
        # Multiple line items can share an ingredient product; we sum them
        # so FEFO sees one ask per product.
        try:
            consumption = await self._build_consumption_plan(
                restaurant_id, enriched, mappings_by_ext
            )
        except _UnitMismatchError as exc:
            return await self._finalize(
                event,
                previous_status,
                user_id,
                POSEventStatus.NEEDS_MAPPING,
                error_message=str(exc),
                reason="unit_mismatch",
            )

        if not consumption:
            # All items were ignore-state (recipe_id IS NULL). Counts as
            # processed — the operator decided these are no-ops.
            return await self._finalize(
                event,
                previous_status,
                user_id,
                POSEventStatus.PROCESSED,
                reason="all_ignored",
            )

        # Pre-flight stock availability.
        insufficient: list[UUID] = []
        for product_id, (qty_needed, _unit) in consumption.items():
            _allocs, available = await self._stock_service.peek_fefo_allocations(
                restaurant_id, product_id, qty_needed
            )
            if available < qty_needed:
                insufficient.append(product_id)
        if insufficient:
            return await self._finalize(
                event,
                previous_status,
                user_id,
                POSEventStatus.INSUFFICIENT_STOCK,
                error_message=f"Products short: {len(insufficient)}",
                reason="insufficient_stock",
                insufficient_product_ids=insufficient,
            )

        # Manual gate. Owner has to approve before stock actually moves.
        manual_mode = integration.confirmation_mode == POSConfirmationMode.MANUAL.value
        if manual_mode and not force:
            event.processing_status = POSEventStatus.PENDING_APPROVAL.value
            event.error_message = None
            self._session.add(event)
            await self._session.commit()
            # Don't audit a pending-approval transition — no user action,
            # nothing changed in the world. Audit lands on the actual
            # approval (force=True path) or on dismiss.
            return ProcessingResult(status=POSEventStatus.PENDING_APPROVAL)

        # Deduct.
        movements_created = await self._deduct_stock(
            restaurant_id=restaurant_id,
            event_id=event_id,
            user_id=user_id,
            external_event_id=event.external_event_id,
            consumption=consumption,
        )

        reason = "force_approval" if force else "auto_processed"
        return await self._finalize(
            event,
            previous_status,
            user_id,
            POSEventStatus.PROCESSED,
            movements_created=movements_created,
            reason=reason,
        )

    async def dismiss_event(
        self,
        restaurant_id: UUID,
        event_id: UUID,
        user_id: UUID,
        reason: str,
    ) -> ProcessingResult:
        """Mark a pending/needs_mapping/etc. event as IGNORED.

        Owner action: "I've reviewed this and we don't want to deduct
        from stock for it." Terminal — audited.
        """
        event = await self._load_event_for_update(restaurant_id, event_id)
        previous_status = POSEventStatus(event.processing_status)
        if previous_status in _TERMINAL_STATUSES:
            return ProcessingResult(status=previous_status)

        return await self._finalize(
            event,
            previous_status,
            user_id,
            POSEventStatus.IGNORED,
            error_message=reason,
            reason=f"manual_dismiss:{reason}"[:500],
            action=AuditAction.POS_DISMISSED,
        )

    # --- internal helpers --- #

    async def _load_event_for_update(self, restaurant_id: UUID, event_id: UUID) -> PosEvent:
        result = await self._session.exec(
            select(PosEvent)
            .where(
                PosEvent.id == event_id,
                PosEvent.restaurant_id == restaurant_id,
            )
            .with_for_update()
        )
        event = result.first()
        if event is None:
            raise NotFoundError("PosEvent")
        return event

    async def _load_integration(self, integration_id: UUID) -> PosIntegration | None:
        result = await self._session.exec(
            select(PosIntegration).where(PosIntegration.id == integration_id)
        )
        return result.first()

    async def _load_mappings(
        self, integration_id: UUID, external_item_ids: list[str]
    ) -> dict[str, PosItemMapping]:
        if not external_item_ids:
            return {}
        result = await self._session.exec(
            select(PosItemMapping).where(
                PosItemMapping.pos_integration_id == integration_id,
                PosItemMapping.external_item_id.in_(external_item_ids),  # type: ignore[attr-defined]
                PosItemMapping.is_active.is_(True),  # type: ignore[attr-defined]
            )
        )
        return {m.external_item_id: m for m in result.all()}

    async def _build_consumption_plan(
        self,
        restaurant_id: UUID,
        enriched: POSWebhookEvent,
        mappings: dict[str, PosItemMapping],
    ) -> dict[UUID, tuple[Decimal, str]]:
        """Aggregate ingredient consumption by product_id.

        Skips items whose mapping has recipe_id IS NULL (intentional
        ignore). Raises _UnitMismatchError when an ingredient's unit
        diverges from the underlying product's unit, so the operator
        can fix the recipe before stock is touched.
        """
        plan: dict[UUID, tuple[Decimal, str]] = {}
        recipe_ingredients_cache: dict[UUID, list[tuple[RecipeIngredient, Product]]] = {}

        for li in enriched.line_items:
            mapping = mappings[li.external_item_id]
            if mapping.recipe_id is None:
                continue

            if mapping.recipe_id not in recipe_ingredients_cache:
                recipe_ingredients_cache[
                    mapping.recipe_id
                ] = await self._load_recipe_ingredients_with_products(
                    restaurant_id, mapping.recipe_id
                )
            ingredients = recipe_ingredients_cache[mapping.recipe_id]

            portions = (li.quantity * mapping.units_per_sale).quantize(Decimal("0.001"))
            for ing, product in ingredients:
                if ing.unit != product.unit:
                    raise _UnitMismatchError(
                        f"Ingredient unit '{ing.unit}' does not match product "
                        f"'{product.name}' unit '{product.unit}'. "
                        "Fix the recipe before retrying."
                    )
                demand = (ing.quantity * portions).quantize(Decimal("0.001"))
                if product.id in plan:
                    existing_qty, _ = plan[product.id]
                    plan[product.id] = (existing_qty + demand, ing.unit)
                else:
                    plan[product.id] = (demand, ing.unit)
        return plan

    async def _load_recipe_ingredients_with_products(
        self, restaurant_id: UUID, recipe_id: UUID
    ) -> list[tuple[RecipeIngredient, Product]]:
        recipe_result = await self._session.exec(
            select(Recipe).where(
                Recipe.id == recipe_id,
                Recipe.restaurant_id == restaurant_id,
            )
        )
        recipe = recipe_result.first()
        if recipe is None:
            raise NotFoundError("Recipe")

        ing_result = await self._session.exec(
            select(RecipeIngredient).where(
                RecipeIngredient.recipe_id == recipe_id,
                RecipeIngredient.restaurant_id == restaurant_id,
            )
        )
        ingredients = list(ing_result.all())
        if not ingredients:
            return []

        product_ids = [ing.product_id for ing in ingredients]
        prod_result = await self._session.exec(
            select(Product).where(Product.id.in_(product_ids))  # type: ignore[attr-defined]
        )
        products_by_id = {p.id: p for p in prod_result.all()}

        return [
            (ing, products_by_id[ing.product_id])
            for ing in ingredients
            if ing.product_id in products_by_id
        ]

    async def _deduct_stock(
        self,
        restaurant_id: UUID,
        event_id: UUID,
        user_id: UUID,
        external_event_id: str,
        consumption: dict[UUID, tuple[Decimal, str]],
    ) -> int:
        total_movements = 0
        for product_id, (qty, unit) in consumption.items():
            movements = await self._stock_service.consume(
                restaurant_id=restaurant_id,
                product_id=product_id,
                quantity=qty,
                unit=unit,
                created_by_user_id=user_id,
                source=MovementSource.POS,
                source_id=event_id,
                reason=f"POS sale {external_event_id}",
            )
            total_movements += len(movements)
        return total_movements

    async def _finalize(
        self,
        event: PosEvent,
        previous_status: POSEventStatus,
        user_id: UUID,
        new_status: POSEventStatus,
        *,
        movements_created: int = 0,
        error_message: str | None = None,
        reason: str = "",
        action: AuditAction = AuditAction.POS_PROCESSED,
        unmapped_item_ids: list[str] | None = None,
        insufficient_product_ids: list[UUID] | None = None,
    ) -> ProcessingResult:
        """Persist the state transition + commit + audit + return result."""
        event.processing_status = new_status.value
        event.error_message = error_message
        if new_status in _TERMINAL_STATUSES:
            event.processed_at = utcnow()
        self._session.add(event)

        before_value: dict[str, Any] = {"processing_status": previous_status.value}
        after_value: dict[str, Any] = {
            "processing_status": new_status.value,
            "movements_created": movements_created,
        }
        if error_message:
            after_value["error_message"] = error_message

        audit = AuditLog(
            restaurant_id=event.restaurant_id,
            entity_type=AuditEntity.POS_EVENT.value,
            entity_id=event.id,
            action=action.value,
            reason=reason,
            before_value=before_value,
            after_value=after_value,
            changed_by_user_id=user_id,
        )
        self._session.add(audit)
        await self._session.commit()

        logger.info(
            "pos.event.transition",
            event_id=str(event.id),
            from_=previous_status.value,
            to=new_status.value,
            reason=reason,
            movements=movements_created,
        )
        return ProcessingResult(
            status=new_status,
            movements_created=movements_created,
            error_message=error_message,
            unmapped_item_ids=unmapped_item_ids or [],
            insufficient_product_ids=insufficient_product_ids or [],
        )


class _UnitMismatchError(Exception):
    """Internal sentinel — bubbles up from _build_consumption_plan to
    flip the event into NEEDS_MAPPING with a helpful message."""
