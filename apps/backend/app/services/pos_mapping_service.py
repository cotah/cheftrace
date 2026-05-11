"""CRUD for `pos_item_mappings`.

The mappings tell the processor (Part 3/4) what a sale of POS item X
deducts from stock: a Recipe + a units_per_sale multiplier. A row
with `recipe_id IS NULL` is the explicit "ignore this item" state —
preferred over deleting because it preserves the audit history that
the operator made a decision.
"""

from decimal import Decimal
from uuid import UUID

import structlog
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.pos_integration import PosIntegration
from app.models.pos_item_mapping import PosItemMapping
from app.models.recipe import Recipe

logger = structlog.get_logger(__name__)


class POSItemMappingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_mappings(
        self,
        restaurant_id: UUID,
        integration_id: UUID,
    ) -> list[PosItemMapping]:
        # Ensure the integration belongs to this tenant before listing
        # its children — same 404 pattern as the rest of the codebase.
        await self._require_integration(restaurant_id, integration_id)
        result = await self._session.exec(
            select(PosItemMapping)
            .where(
                PosItemMapping.restaurant_id == restaurant_id,
                PosItemMapping.pos_integration_id == integration_id,
            )
            .order_by(PosItemMapping.external_item_name_snapshot.asc())  # type: ignore[attr-defined]
        )
        return list(result.all())

    async def get_mapping(
        self,
        restaurant_id: UUID,
        integration_id: UUID,
        mapping_id: UUID,
    ) -> PosItemMapping:
        result = await self._session.exec(
            select(PosItemMapping).where(
                PosItemMapping.id == mapping_id,
                PosItemMapping.restaurant_id == restaurant_id,
                PosItemMapping.pos_integration_id == integration_id,
            )
        )
        mapping = result.first()
        if mapping is None:
            raise NotFoundError("PosItemMapping")
        return mapping

    async def create_mapping(
        self,
        restaurant_id: UUID,
        integration_id: UUID,
        external_item_id: str,
        external_item_name_snapshot: str,
        recipe_id: UUID | None,
        units_per_sale: Decimal,
    ) -> PosItemMapping:
        await self._require_integration(restaurant_id, integration_id)
        if recipe_id is not None:
            await self._require_recipe(restaurant_id, recipe_id)

        mapping = PosItemMapping(
            restaurant_id=restaurant_id,
            pos_integration_id=integration_id,
            external_item_id=external_item_id,
            external_item_name_snapshot=external_item_name_snapshot,
            recipe_id=recipe_id,
            units_per_sale=units_per_sale,
        )
        self._session.add(mapping)
        try:
            await self._session.flush()
        except Exception as exc:
            await self._session.rollback()
            # UNIQUE(pos_integration_id, external_item_id) — same external
            # item can only have one mapping per integration.
            raise ConflictError(f"A mapping for item '{external_item_id}' already exists.") from exc
        await self._session.refresh(mapping)
        logger.info(
            "pos_mapping.create",
            restaurant_id=str(restaurant_id),
            integration_id=str(integration_id),
            mapping_id=str(mapping.id),
            external_item_id=external_item_id,
        )
        return mapping

    async def update_mapping(
        self,
        restaurant_id: UUID,
        integration_id: UUID,
        mapping_id: UUID,
        update: dict[str, object],
    ) -> PosItemMapping:
        """`update` is a dict of fields that were explicitly set in the
        request (via Pydantic `model_dump(exclude_unset=True)`).

        That's the only way to distinguish "leave recipe_id alone" from
        "set recipe_id to NULL (ignore this item)" — Pydantic v2 default
        `None` doesn't tell us which the caller meant.
        """
        mapping = await self.get_mapping(restaurant_id, integration_id, mapping_id)

        if "recipe_id" in update:
            new_recipe_id = update["recipe_id"]
            if new_recipe_id is not None:
                # We must validate the recipe belongs to this tenant —
                # cross-tenant linking would otherwise be possible via
                # the API.
                if not isinstance(new_recipe_id, UUID):
                    raise ConflictError("recipe_id must be a UUID")
                await self._require_recipe(restaurant_id, new_recipe_id)
            mapping.recipe_id = new_recipe_id

        if "external_item_name_snapshot" in update:
            value = update["external_item_name_snapshot"]
            if isinstance(value, str):
                mapping.external_item_name_snapshot = value

        if "units_per_sale" in update:
            value = update["units_per_sale"]
            if isinstance(value, Decimal):
                mapping.units_per_sale = value
            elif isinstance(value, (int, float, str)):
                mapping.units_per_sale = Decimal(str(value))

        if "is_active" in update:
            value = update["is_active"]
            if isinstance(value, bool):
                mapping.is_active = value

        self._session.add(mapping)
        await self._session.flush()
        await self._session.refresh(mapping)
        return mapping

    async def delete_mapping(
        self,
        restaurant_id: UUID,
        integration_id: UUID,
        mapping_id: UUID,
    ) -> None:
        """Soft delete via is_active=False.

        Hard-deleting would silently break the audit trail for past POS
        events whose processing referenced the mapping. The integration
        flow still sees this row in lookups but the processor treats
        is_active=False as "no mapping" -> needs_mapping state.
        """
        mapping = await self.get_mapping(restaurant_id, integration_id, mapping_id)
        mapping.is_active = False
        self._session.add(mapping)
        await self._session.flush()

    # --- internal helpers --- #

    async def _require_integration(self, restaurant_id: UUID, integration_id: UUID) -> None:
        result = await self._session.exec(
            select(PosIntegration).where(
                PosIntegration.id == integration_id,
                PosIntegration.restaurant_id == restaurant_id,
            )
        )
        if result.first() is None:
            raise NotFoundError("PosIntegration")

    async def _require_recipe(self, restaurant_id: UUID, recipe_id: UUID) -> None:
        result = await self._session.exec(
            select(Recipe).where(
                Recipe.id == recipe_id,
                Recipe.restaurant_id == restaurant_id,
            )
        )
        if result.first() is None:
            raise NotFoundError("Recipe")
