"""Phase 3 Part 1/3 — recipes CRUD + multi-tenant.

Produce/confirm endpoints (Phase 3 Part 2/3) are tested separately.
"""

import os
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401
from app.core.exceptions import ConflictError, NotFoundError
from app.models.product import Product
from app.models.recipe import Recipe
from app.models.recipe_ingredient import RecipeIngredient
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.recipe import (
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeIngredientUpdate,
    RecipeRead,
    RecipeUpdate,
)
from app.services.recipe_service import RecipeService


@pytest.fixture
async def db_engine():
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5433/test",
    )
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(db_engine):
    factory = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest.fixture
async def test_data(session):
    user = User(email=f"rec_{uuid4()}@test.com")
    session.add(user)
    restaurant_a = Restaurant(name="Recipe Resto A", country="IE")
    session.add(restaurant_a)
    restaurant_b = Restaurant(name="Recipe Resto B", country="IE")
    session.add(restaurant_b)
    await session.flush()

    product_a = Product(
        restaurant_id=restaurant_a.id,
        name="Tomatoes",
        unit="kg",
    )
    product_b = Product(
        restaurant_id=restaurant_b.id,
        name="Other tenant product",
        unit="kg",
    )
    session.add(product_a)
    session.add(product_b)
    await session.flush()

    return {
        "user_id": user.id,
        "restaurant_a": restaurant_a.id,
        "restaurant_b": restaurant_b.id,
        "product_a": product_a.id,
        "product_b": product_b.id,
    }


def _make_recipe_payload(name: str = "Tomato sauce") -> RecipeCreate:
    return RecipeCreate(
        name=name,
        yield_quantity=Decimal("5.000"),
        yield_unit="L",
        prep_time_minutes=15,
        cook_time_minutes=45,
        instructions="Simmer everything for 30 minutes.",
    )


# --- create / list / get --- #


@pytest.mark.asyncio
async def test_create_recipe(session, test_data):
    svc = RecipeService(session)
    recipe = await svc.create_recipe(test_data["restaurant_a"], _make_recipe_payload())
    assert recipe.id is not None
    assert recipe.is_active is True
    assert recipe.yield_quantity == Decimal("5.000")
    assert recipe.yield_unit == "L"


@pytest.mark.asyncio
async def test_list_recipes_filters_is_active(session, test_data):
    svc = RecipeService(session)
    active = await svc.create_recipe(test_data["restaurant_a"], _make_recipe_payload("Active one"))
    inactive = await svc.create_recipe(
        test_data["restaurant_a"], _make_recipe_payload("To deactivate")
    )
    await svc.soft_delete_recipe(test_data["restaurant_a"], inactive.id)

    all_recipes = await svc.list_recipes(test_data["restaurant_a"])
    active_only = await svc.list_recipes(test_data["restaurant_a"], is_active=True)
    inactive_only = await svc.list_recipes(test_data["restaurant_a"], is_active=False)

    assert len(all_recipes) == 2
    assert [r.id for r in active_only] == [active.id]
    assert [r.id for r in inactive_only] == [inactive.id]


@pytest.mark.asyncio
async def test_get_recipe_other_tenant_returns_404(session, test_data):
    svc_a = RecipeService(session)
    recipe = await svc_a.create_recipe(test_data["restaurant_a"], _make_recipe_payload())

    # Query for the same recipe but under tenant B.
    with pytest.raises(NotFoundError):
        await svc_a.get_recipe(test_data["restaurant_b"], recipe.id)


@pytest.mark.asyncio
async def test_get_recipe_unknown_returns_404(session, test_data):
    svc = RecipeService(session)
    with pytest.raises(NotFoundError):
        await svc.get_recipe(test_data["restaurant_a"], uuid4())


# --- update / soft delete --- #


@pytest.mark.asyncio
async def test_update_recipe_applies_partial_fields(session, test_data):
    svc = RecipeService(session)
    recipe = await svc.create_recipe(test_data["restaurant_a"], _make_recipe_payload())
    updated = await svc.update_recipe(
        test_data["restaurant_a"],
        recipe.id,
        RecipeUpdate(name="Renamed", cook_time_minutes=60),
    )
    assert updated.name == "Renamed"
    assert updated.cook_time_minutes == 60
    # Untouched fields stay.
    assert updated.yield_unit == "L"


@pytest.mark.asyncio
async def test_soft_delete_recipe_keeps_row(session, test_data):
    svc = RecipeService(session)
    recipe = await svc.create_recipe(test_data["restaurant_a"], _make_recipe_payload())
    await svc.soft_delete_recipe(test_data["restaurant_a"], recipe.id)

    row = (await session.exec(select(Recipe).where(Recipe.id == recipe.id))).first()
    assert row is not None
    assert row.is_active is False


@pytest.mark.asyncio
async def test_soft_delete_is_idempotent(session, test_data):
    svc = RecipeService(session)
    recipe = await svc.create_recipe(test_data["restaurant_a"], _make_recipe_payload())
    await svc.soft_delete_recipe(test_data["restaurant_a"], recipe.id)
    again = await svc.soft_delete_recipe(test_data["restaurant_a"], recipe.id)
    assert again.is_active is False


# --- ingredients sub-resource --- #


@pytest.mark.asyncio
async def test_add_ingredient_and_list(session, test_data):
    svc = RecipeService(session)
    recipe = await svc.create_recipe(test_data["restaurant_a"], _make_recipe_payload())

    ing = await svc.add_ingredient(
        test_data["restaurant_a"],
        recipe.id,
        RecipeIngredientCreate(
            product_id=test_data["product_a"],
            quantity=Decimal("2.500"),
            unit="kg",
            notes="ripe ones",
        ),
    )
    assert ing.recipe_id == recipe.id
    assert ing.product_id == test_data["product_a"]
    assert ing.quantity == Decimal("2.500")

    listed = await svc.list_ingredients(test_data["restaurant_a"], recipe.id)
    assert len(listed) == 1
    assert listed[0].id == ing.id


@pytest.mark.asyncio
async def test_add_ingredient_rejects_cross_tenant_product(session, test_data):
    svc = RecipeService(session)
    recipe = await svc.create_recipe(test_data["restaurant_a"], _make_recipe_payload())

    with pytest.raises(ConflictError):
        await svc.add_ingredient(
            test_data["restaurant_a"],
            recipe.id,
            RecipeIngredientCreate(
                product_id=test_data["product_b"],  # belongs to tenant B
                quantity=Decimal("1"),
                unit="kg",
            ),
        )


@pytest.mark.asyncio
async def test_update_ingredient_partial(session, test_data):
    svc = RecipeService(session)
    recipe = await svc.create_recipe(test_data["restaurant_a"], _make_recipe_payload())
    ing = await svc.add_ingredient(
        test_data["restaurant_a"],
        recipe.id,
        RecipeIngredientCreate(
            product_id=test_data["product_a"],
            quantity=Decimal("2.500"),
            unit="kg",
        ),
    )
    updated = await svc.update_ingredient(
        test_data["restaurant_a"],
        recipe.id,
        ing.id,
        RecipeIngredientUpdate(quantity=Decimal("3.000"), notes="more please"),
    )
    assert updated.quantity == Decimal("3.000")
    assert updated.notes == "more please"
    assert updated.unit == "kg"  # untouched


@pytest.mark.asyncio
async def test_remove_ingredient(session, test_data):
    svc = RecipeService(session)
    recipe = await svc.create_recipe(test_data["restaurant_a"], _make_recipe_payload())
    ing = await svc.add_ingredient(
        test_data["restaurant_a"],
        recipe.id,
        RecipeIngredientCreate(
            product_id=test_data["product_a"],
            quantity=Decimal("1"),
            unit="kg",
        ),
    )
    await svc.remove_ingredient(test_data["restaurant_a"], recipe.id, ing.id)

    rows = (await session.exec(select(RecipeIngredient).where(RecipeIngredient.id == ing.id))).all()
    assert list(rows) == []


@pytest.mark.asyncio
async def test_ingredient_other_tenant_returns_404(session, test_data):
    svc = RecipeService(session)
    recipe = await svc.create_recipe(test_data["restaurant_a"], _make_recipe_payload())
    ing = await svc.add_ingredient(
        test_data["restaurant_a"],
        recipe.id,
        RecipeIngredientCreate(
            product_id=test_data["product_a"],
            quantity=Decimal("1"),
            unit="kg",
        ),
    )

    # Trying to fetch from tenant B fails.
    with pytest.raises(NotFoundError):
        await svc.get_ingredient(test_data["restaurant_b"], recipe.id, ing.id)


# --- regression: Pydantic vs ORM shape --- #


@pytest.mark.asyncio
async def test_recipe_read_validates_orm_shape(session, test_data):
    """Guard against str-vs-datetime drift seen in HACCPRunRead (BUG-05)."""
    svc = RecipeService(session)
    recipe = await svc.create_recipe(test_data["restaurant_a"], _make_recipe_payload())
    await session.refresh(recipe)
    read = RecipeRead.model_validate(recipe)
    assert isinstance(read.created_at, datetime)
    assert isinstance(read.updated_at, datetime)
    assert read.yield_quantity == Decimal("5.000")
