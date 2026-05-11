"""Recipe service — recipes catalogue + ingredients sub-resource.

Production logic (FEFO preview + confirm) lives in Phase 3 Part 2/3 and
will be added as a separate service to keep CRUD concerns isolated.
"""

from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.product import Product
from app.models.recipe import Recipe
from app.models.recipe_ingredient import RecipeIngredient
from app.schemas.recipe import (
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeIngredientUpdate,
    RecipeUpdate,
)


class RecipeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- queries --- #

    async def list_recipes(
        self, restaurant_id: UUID, is_active: bool | None = None
    ) -> list[Recipe]:
        stmt = select(Recipe).where(Recipe.restaurant_id == restaurant_id)
        if is_active is not None:
            stmt = stmt.where(Recipe.is_active == is_active)
        stmt = stmt.order_by(Recipe.name.asc())  # type: ignore[attr-defined]
        result = await self._session.exec(stmt)
        return list(result.all())

    async def get_recipe(self, restaurant_id: UUID, recipe_id: UUID) -> Recipe:
        result = await self._session.exec(
            select(Recipe).where(
                Recipe.id == recipe_id,
                Recipe.restaurant_id == restaurant_id,
            )
        )
        recipe = result.first()
        if not recipe:
            raise NotFoundError("Recipe")
        return recipe

    async def list_ingredients(
        self, restaurant_id: UUID, recipe_id: UUID
    ) -> list[RecipeIngredient]:
        await self.get_recipe(restaurant_id, recipe_id)
        result = await self._session.exec(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_id == recipe_id)
            .order_by(RecipeIngredient.created_at.asc())  # type: ignore[attr-defined]
        )
        return list(result.all())

    # --- mutations: recipe --- #

    async def create_recipe(self, restaurant_id: UUID, data: RecipeCreate) -> Recipe:
        recipe = Recipe(
            restaurant_id=restaurant_id,
            name=data.name,
            yield_quantity=data.yield_quantity,
            yield_unit=data.yield_unit,
            prep_time_minutes=data.prep_time_minutes,
            cook_time_minutes=data.cook_time_minutes,
            instructions=data.instructions,
            is_active=True,
        )
        self._session.add(recipe)
        await self._session.commit()
        await self._session.refresh(recipe)
        return recipe

    async def update_recipe(
        self, restaurant_id: UUID, recipe_id: UUID, data: RecipeUpdate
    ) -> Recipe:
        recipe = await self.get_recipe(restaurant_id, recipe_id)
        # Apply only the fields the caller actually sent.
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(recipe, field, value)
        self._session.add(recipe)
        await self._session.commit()
        await self._session.refresh(recipe)
        return recipe

    async def soft_delete_recipe(self, restaurant_id: UUID, recipe_id: UUID) -> Recipe:
        """Soft delete — preserves recipe history and any prior productions."""
        recipe = await self.get_recipe(restaurant_id, recipe_id)
        if not recipe.is_active:
            # Idempotent: already inactive.
            return recipe
        recipe.is_active = False
        self._session.add(recipe)
        await self._session.commit()
        await self._session.refresh(recipe)
        return recipe

    # --- mutations: ingredients sub-resource --- #

    async def _validate_product_in_tenant(self, restaurant_id: UUID, product_id: UUID) -> Product:
        result = await self._session.exec(
            select(Product).where(
                Product.id == product_id,
                Product.restaurant_id == restaurant_id,
            )
        )
        product = result.first()
        if not product:
            raise ConflictError(f"Product {product_id} does not belong to this restaurant.")
        return product

    async def add_ingredient(
        self,
        restaurant_id: UUID,
        recipe_id: UUID,
        data: RecipeIngredientCreate,
    ) -> RecipeIngredient:
        await self.get_recipe(restaurant_id, recipe_id)
        await self._validate_product_in_tenant(restaurant_id, data.product_id)
        ingredient = RecipeIngredient(
            restaurant_id=restaurant_id,
            recipe_id=recipe_id,
            product_id=data.product_id,
            quantity=data.quantity,
            unit=data.unit,
            notes=data.notes,
        )
        self._session.add(ingredient)
        await self._session.commit()
        await self._session.refresh(ingredient)
        return ingredient

    async def get_ingredient(
        self, restaurant_id: UUID, recipe_id: UUID, ingredient_id: UUID
    ) -> RecipeIngredient:
        await self.get_recipe(restaurant_id, recipe_id)
        result = await self._session.exec(
            select(RecipeIngredient).where(
                RecipeIngredient.id == ingredient_id,
                RecipeIngredient.recipe_id == recipe_id,
                RecipeIngredient.restaurant_id == restaurant_id,
            )
        )
        ingredient = result.first()
        if not ingredient:
            raise NotFoundError("RecipeIngredient")
        return ingredient

    async def update_ingredient(
        self,
        restaurant_id: UUID,
        recipe_id: UUID,
        ingredient_id: UUID,
        data: RecipeIngredientUpdate,
    ) -> RecipeIngredient:
        ingredient = await self.get_ingredient(restaurant_id, recipe_id, ingredient_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(ingredient, field, value)
        self._session.add(ingredient)
        await self._session.commit()
        await self._session.refresh(ingredient)
        return ingredient

    async def remove_ingredient(
        self, restaurant_id: UUID, recipe_id: UUID, ingredient_id: UUID
    ) -> None:
        ingredient = await self.get_ingredient(restaurant_id, recipe_id, ingredient_id)
        await self._session.delete(ingredient)
        await self._session.commit()
