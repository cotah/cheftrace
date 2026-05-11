"""Recipe production — preview FEFO allocations, then commit them.

Split from RecipeService so produce concerns (FEFO, multi-product
transactions, mutation) stay isolated from CRUD. The two services
coexist in the same Phase 3 module space.
"""

from decimal import Decimal
from uuid import UUID

import structlog
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ConflictError
from app.models.enums import MovementSource
from app.models.product import Product
from app.models.recipe import Recipe
from app.models.recipe_ingredient import RecipeIngredient
from app.models.recipe_production import RecipeProduction
from app.schemas.recipe import (
    RecipeProductionAllocation,
    RecipeProductionPreviewLine,
    RecipeProductionPreviewResponse,
)
from app.services.recipe_service import RecipeService
from app.services.stock_service import StockService

logger = structlog.get_logger(__name__)


class RecipeProductionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._recipes = RecipeService(session)
        self._stock = StockService(session)

    async def _load_recipe_active_or_raise(self, restaurant_id: UUID, recipe_id: UUID) -> Recipe:
        """Fetch recipe and refuse to produce inactive ones — 409.

        Inactive recipes are kept as historical references; producing from
        a deleted spec would silently produce stale ingredient lists.
        """
        recipe = await self._recipes.get_recipe(restaurant_id, recipe_id)
        if not recipe.is_active:
            raise ConflictError(f"Recipe '{recipe.name}' is inactive and cannot be produced.")
        return recipe

    async def _load_ingredients_with_products(
        self, restaurant_id: UUID, recipe_id: UUID
    ) -> list[tuple[RecipeIngredient, Product]]:
        ingredients = await self._recipes.list_ingredients(restaurant_id, recipe_id)
        if not ingredients:
            raise ConflictError("Recipe has no ingredients to consume.")
        product_ids = [ing.product_id for ing in ingredients]
        result = await self._session.exec(
            select(Product).where(Product.id.in_(product_ids))  # type: ignore[attr-defined]
        )
        products_by_id = {p.id: p for p in result.all()}
        out: list[tuple[RecipeIngredient, Product]] = []
        for ing in ingredients:
            product = products_by_id.get(ing.product_id)
            if product is None:
                # Product was hard-deleted — should not happen in practice
                # because we soft-delete via is_active.
                raise ConflictError(
                    f"Product {ing.product_id} for ingredient {ing.id} no longer exists."
                )
            out.append((ing, product))
        return out

    async def preview(
        self,
        restaurant_id: UUID,
        recipe_id: UUID,
        batches: Decimal,
    ) -> RecipeProductionPreviewResponse:
        """Compute FEFO allocations for `batches x recipe ingredients`.

        Read-only. Flags shortages and unit mismatches per line so the
        UI can show issues without a second round-trip. `can_confirm` is
        True iff every line has enough stock AND no unit mismatches.
        """
        await self._load_recipe_active_or_raise(restaurant_id, recipe_id)
        pairs = await self._load_ingredients_with_products(restaurant_id, recipe_id)

        lines: list[RecipeProductionPreviewLine] = []
        all_ok = True
        for ing, product in pairs:
            quantity_needed = (ing.quantity * batches).quantize(Decimal("0.001"))
            unit_mismatch = ing.unit != product.unit
            allocations: list[RecipeProductionAllocation] = []
            available = Decimal("0")
            shortage = False

            if unit_mismatch:
                # We deliberately skip the FEFO peek for mismatched units —
                # the numbers would be misleading. UI should surface a clear
                # "fix the unit on this ingredient" message.
                all_ok = False
            else:
                allocs, total_avail = await self._stock.peek_fefo_allocations(
                    restaurant_id, product.id, quantity_needed
                )
                available = total_avail
                shortage = total_avail < quantity_needed
                if shortage:
                    all_ok = False
                allocations = [
                    RecipeProductionAllocation(
                        lot_id=a.lot_id,
                        expiry_date=a.expiry_date.isoformat() if a.expiry_date else None,
                        quantity_from_lot=a.quantity_from_lot,
                        unit_cost=a.unit_cost,
                        unit=a.unit,
                    )
                    for a in allocs
                ]

            lines.append(
                RecipeProductionPreviewLine(
                    ingredient_id=ing.id,
                    product_id=product.id,
                    product_name=product.name,
                    ingredient_unit=ing.unit,
                    product_unit=product.unit,
                    quantity_needed=quantity_needed,
                    available=available,
                    shortage=shortage,
                    unit_mismatch=unit_mismatch,
                    allocations=allocations,
                )
            )

        return RecipeProductionPreviewResponse(
            recipe_id=recipe_id,
            batches=batches,
            lines=lines,
            can_confirm=all_ok,
        )

    async def confirm(
        self,
        restaurant_id: UUID,
        recipe_id: UUID,
        batches: Decimal,
        produced_by_user_id: UUID,
        notes: str | None = None,
    ) -> RecipeProduction:
        """Persist a RecipeProduction and consume FEFO for every ingredient.

        All-or-nothing transaction: if any consume() raises (insufficient
        stock, unit mismatch caught here), the whole call rolls back and
        no movements are created.
        """
        await self._load_recipe_active_or_raise(restaurant_id, recipe_id)
        pairs = await self._load_ingredients_with_products(restaurant_id, recipe_id)

        # Pre-flight: catch unit mismatches before mutating anything.
        for ing, product in pairs:
            if ing.unit != product.unit:
                raise ConflictError(
                    f"Ingredient unit '{ing.unit}' does not match product "
                    f"'{product.name}' unit '{product.unit}'. "
                    "Edit the ingredient before producing."
                )

        production = RecipeProduction(
            restaurant_id=restaurant_id,
            recipe_id=recipe_id,
            batches=batches,
            produced_by_user_id=produced_by_user_id,
            notes=notes,
        )
        self._session.add(production)
        await self._session.flush()  # need the id to tag movements with source_id

        try:
            for ing, _product in pairs:
                quantity_needed = (ing.quantity * batches).quantize(Decimal("0.001"))
                await self._stock.consume(
                    restaurant_id=restaurant_id,
                    product_id=ing.product_id,
                    quantity=quantity_needed,
                    unit=ing.unit,
                    created_by_user_id=produced_by_user_id,
                    source=MovementSource.RECIPE,
                    source_id=production.id,
                    reason=f"recipe production {production.id}",
                )
        except Exception:
            # consume() raises InsufficientStockError (a ConflictError) or
            # similar; either way roll the production back.
            await self._session.rollback()
            raise

        await self._session.commit()
        await self._session.refresh(production)

        logger.info(
            "recipe.produce",
            restaurant_id=str(restaurant_id),
            recipe_id=str(recipe_id),
            production_id=str(production.id),
            batches=str(batches),
        )
        return production
