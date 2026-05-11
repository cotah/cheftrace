"""Recipe endpoints — CRUD + ingredients sub-resource.

Phase 3 Part 1/3 scope. Production (FEFO preview + confirm) lives in
/produce, added in Part 2/3.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.permissions import Permission
from app.models.membership import RestaurantMembership
from app.schemas.recipe import (
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeIngredientRead,
    RecipeIngredientUpdate,
    RecipeRead,
    RecipeUpdate,
    RecipeWithIngredientsRead,
)
from app.services.recipe_service import RecipeService

router = APIRouter(prefix="/restaurants/{restaurant_id}/recipes", tags=["recipes"])


@router.get("", response_model=list[RecipeRead])
async def list_recipes(
    membership: CurrentMembership,
    is_active: bool | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[RecipeRead]:
    svc = RecipeService(session)
    recipes = await svc.list_recipes(membership.restaurant_id, is_active=is_active)
    return [RecipeRead.model_validate(r) for r in recipes]


@router.post("", response_model=RecipeRead, status_code=201)
async def create_recipe(
    data: RecipeCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> RecipeRead:
    svc = RecipeService(session)
    recipe = await svc.create_recipe(membership.restaurant_id, data)
    return RecipeRead.model_validate(recipe)


@router.get("/{recipe_id}", response_model=RecipeWithIngredientsRead)
async def get_recipe(
    recipe_id: UUID,
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> RecipeWithIngredientsRead:
    svc = RecipeService(session)
    recipe = await svc.get_recipe(membership.restaurant_id, recipe_id)
    ingredients = await svc.list_ingredients(membership.restaurant_id, recipe_id)
    base = RecipeRead.model_validate(recipe).model_dump()
    return RecipeWithIngredientsRead(
        **base,
        ingredients=[RecipeIngredientRead.model_validate(i) for i in ingredients],
    )


@router.put("/{recipe_id}", response_model=RecipeRead)
async def update_recipe(
    recipe_id: UUID,
    data: RecipeUpdate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> RecipeRead:
    svc = RecipeService(session)
    recipe = await svc.update_recipe(membership.restaurant_id, recipe_id, data)
    return RecipeRead.model_validate(recipe)


@router.delete("/{recipe_id}", status_code=204)
async def delete_recipe(
    recipe_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Soft delete — sets is_active=false, preserves history."""
    svc = RecipeService(session)
    await svc.soft_delete_recipe(membership.restaurant_id, recipe_id)
    return Response(status_code=204)


# --- ingredients sub-resource --- #


@router.post(
    "/{recipe_id}/ingredients",
    response_model=RecipeIngredientRead,
    status_code=201,
)
async def add_ingredient(
    recipe_id: UUID,
    data: RecipeIngredientCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> RecipeIngredientRead:
    svc = RecipeService(session)
    ingredient = await svc.add_ingredient(membership.restaurant_id, recipe_id, data)
    return RecipeIngredientRead.model_validate(ingredient)


@router.put(
    "/{recipe_id}/ingredients/{ingredient_id}",
    response_model=RecipeIngredientRead,
)
async def update_ingredient(
    recipe_id: UUID,
    ingredient_id: UUID,
    data: RecipeIngredientUpdate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> RecipeIngredientRead:
    svc = RecipeService(session)
    ingredient = await svc.update_ingredient(
        membership.restaurant_id, recipe_id, ingredient_id, data
    )
    return RecipeIngredientRead.model_validate(ingredient)


@router.delete("/{recipe_id}/ingredients/{ingredient_id}", status_code=204)
async def remove_ingredient(
    recipe_id: UUID,
    ingredient_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    svc = RecipeService(session)
    await svc.remove_ingredient(membership.restaurant_id, recipe_id, ingredient_id)
    return Response(status_code=204)
