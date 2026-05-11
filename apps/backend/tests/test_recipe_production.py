"""Phase 3 Part 2/3 — recipe production preview + confirm.

Covers FEFO ordering across multiple lots, shortage flag, unit mismatch
between ingredient and product, soft-deleted recipe, cross-tenant, and
the source/source_id tagging on stock_movements.
"""

import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401
from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import LotStatus, MovementSource
from app.models.product import Product
from app.models.recipe import Recipe
from app.models.recipe_ingredient import RecipeIngredient
from app.models.recipe_production import RecipeProduction
from app.models.restaurant import Restaurant
from app.models.stock_lot import StockLot
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.schemas.recipe import RecipeProductionRead
from app.services.recipe_production_service import RecipeProductionService
from app.services.stock_service import InsufficientStockError

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
NEXT_WEEK = TODAY + timedelta(days=7)


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
async def scenario(session):
    """Two restaurants, one recipe in A with two kg-based ingredients."""
    user = User(email=f"prod_{uuid4()}@test.com")
    session.add(user)
    restaurant_a = Restaurant(name="Prod Resto A", country="IE")
    session.add(restaurant_a)
    restaurant_b = Restaurant(name="Prod Resto B", country="IE")
    session.add(restaurant_b)
    await session.flush()

    tomato = Product(restaurant_id=restaurant_a.id, name="Tomato", unit="kg")
    onion = Product(restaurant_id=restaurant_a.id, name="Onion", unit="kg")
    salt_g = Product(restaurant_id=restaurant_a.id, name="Salt", unit="g")  # for unit-mismatch test
    session.add(tomato)
    session.add(onion)
    session.add(salt_g)
    await session.flush()

    recipe = Recipe(
        restaurant_id=restaurant_a.id,
        name="Tomato sauce",
        yield_quantity=Decimal("5.000"),
        yield_unit="L",
    )
    session.add(recipe)
    await session.flush()

    ing_tomato = RecipeIngredient(
        restaurant_id=restaurant_a.id,
        recipe_id=recipe.id,
        product_id=tomato.id,
        quantity=Decimal("2.000"),
        unit="kg",
    )
    ing_onion = RecipeIngredient(
        restaurant_id=restaurant_a.id,
        recipe_id=recipe.id,
        product_id=onion.id,
        quantity=Decimal("0.500"),
        unit="kg",
    )
    session.add(ing_tomato)
    session.add(ing_onion)
    await session.commit()

    return {
        "user_id": user.id,
        "restaurant_a": restaurant_a.id,
        "restaurant_b": restaurant_b.id,
        "recipe": recipe,
        "tomato": tomato,
        "onion": onion,
        "salt_g": salt_g,
        "ing_tomato": ing_tomato,
        "ing_onion": ing_onion,
    }


async def _make_lot(
    session: AsyncSession,
    restaurant_id,
    product_id,
    user_id,
    quantity: Decimal,
    unit: str = "kg",
    expiry: date | None = None,
    received: date | None = None,
) -> StockLot:
    lot = StockLot(
        restaurant_id=restaurant_id,
        product_id=product_id,
        supplier_id=None,
        quantity_received=quantity,
        quantity_remaining=quantity,
        unit=unit,
        expiry_date=expiry,
        received_date=received or TODAY,
        status=LotStatus.ACTIVE,
        created_by_user_id=user_id,
    )
    session.add(lot)
    await session.flush()
    return lot


# --- preview --- #


@pytest.mark.asyncio
async def test_preview_happy_path_with_fefo_order(session, scenario):
    # Two tomato lots, the soonest-expiring should be drained first.
    earlier = await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["tomato"].id,
        scenario["user_id"],
        Decimal("1.000"),
        expiry=TOMORROW,
    )
    later = await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["tomato"].id,
        scenario["user_id"],
        Decimal("5.000"),
        expiry=NEXT_WEEK,
    )
    await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["onion"].id,
        scenario["user_id"],
        Decimal("2.000"),
        expiry=NEXT_WEEK,
    )
    await session.commit()

    svc = RecipeProductionService(session)
    preview = await svc.preview(
        scenario["restaurant_a"], scenario["recipe"].id, batches=Decimal("1")
    )

    assert preview.can_confirm is True
    assert len(preview.lines) == 2
    tomato_line = next(li for li in preview.lines if li.product_id == scenario["tomato"].id)
    assert tomato_line.quantity_needed == Decimal("2.000")
    assert tomato_line.shortage is False
    # FEFO: 1kg from earlier (expiry tomorrow) + 1kg from later.
    assert [a.lot_id for a in tomato_line.allocations] == [earlier.id, later.id]
    assert tomato_line.allocations[0].quantity_from_lot == Decimal("1.000")
    assert tomato_line.allocations[1].quantity_from_lot == Decimal("1.000")


@pytest.mark.asyncio
async def test_preview_batches_multiplies_quantity(session, scenario):
    await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["tomato"].id,
        scenario["user_id"],
        Decimal("10.000"),
        expiry=NEXT_WEEK,
    )
    await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["onion"].id,
        scenario["user_id"],
        Decimal("5.000"),
        expiry=NEXT_WEEK,
    )
    await session.commit()

    svc = RecipeProductionService(session)
    preview = await svc.preview(
        scenario["restaurant_a"], scenario["recipe"].id, batches=Decimal("1.5")
    )

    tomato_line = next(li for li in preview.lines if li.product_id == scenario["tomato"].id)
    assert tomato_line.quantity_needed == Decimal("3.000")
    onion_line = next(li for li in preview.lines if li.product_id == scenario["onion"].id)
    assert onion_line.quantity_needed == Decimal("0.750")


@pytest.mark.asyncio
async def test_preview_shortage_flag(session, scenario):
    # Only 0.5kg of tomato available, recipe needs 2kg.
    await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["tomato"].id,
        scenario["user_id"],
        Decimal("0.500"),
        expiry=NEXT_WEEK,
    )
    await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["onion"].id,
        scenario["user_id"],
        Decimal("5.000"),
        expiry=NEXT_WEEK,
    )
    await session.commit()

    svc = RecipeProductionService(session)
    preview = await svc.preview(
        scenario["restaurant_a"], scenario["recipe"].id, batches=Decimal("1")
    )

    assert preview.can_confirm is False
    tomato_line = next(li for li in preview.lines if li.product_id == scenario["tomato"].id)
    assert tomato_line.shortage is True
    assert tomato_line.available == Decimal("0.500")
    # Allocations cover only what's available — partial.
    total_from_allocs = sum((a.quantity_from_lot for a in tomato_line.allocations), Decimal("0"))
    assert total_from_allocs == Decimal("0.500")


@pytest.mark.asyncio
async def test_preview_unit_mismatch_flag(session, scenario):
    # Bad ingredient: links Salt (product unit 'g') with unit 'kg'.
    bad_ing = RecipeIngredient(
        restaurant_id=scenario["restaurant_a"],
        recipe_id=scenario["recipe"].id,
        product_id=scenario["salt_g"].id,
        quantity=Decimal("0.010"),
        unit="kg",  # MISMATCH — Salt's product unit is 'g'
    )
    session.add(bad_ing)
    await session.commit()
    await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["tomato"].id,
        scenario["user_id"],
        Decimal("5.000"),
        expiry=NEXT_WEEK,
    )
    await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["onion"].id,
        scenario["user_id"],
        Decimal("5.000"),
        expiry=NEXT_WEEK,
    )
    await session.commit()

    svc = RecipeProductionService(session)
    preview = await svc.preview(
        scenario["restaurant_a"], scenario["recipe"].id, batches=Decimal("1")
    )

    assert preview.can_confirm is False
    salt_line = next(li for li in preview.lines if li.product_id == scenario["salt_g"].id)
    assert salt_line.unit_mismatch is True
    assert salt_line.ingredient_unit == "kg"
    assert salt_line.product_unit == "g"
    assert salt_line.allocations == []  # skipped


@pytest.mark.asyncio
async def test_preview_inactive_recipe_raises_409(session, scenario):
    recipe = scenario["recipe"]
    recipe.is_active = False
    session.add(recipe)
    await session.commit()

    svc = RecipeProductionService(session)
    with pytest.raises(ConflictError):
        await svc.preview(scenario["restaurant_a"], recipe.id, batches=Decimal("1"))


@pytest.mark.asyncio
async def test_preview_cross_tenant_returns_404(session, scenario):
    svc = RecipeProductionService(session)
    with pytest.raises(NotFoundError):
        await svc.preview(scenario["restaurant_b"], scenario["recipe"].id, batches=Decimal("1"))


@pytest.mark.asyncio
async def test_preview_recipe_with_no_ingredients_raises_409(session, scenario):
    empty = Recipe(
        restaurant_id=scenario["restaurant_a"],
        name="Empty",
        yield_quantity=Decimal("1"),
        yield_unit="unit",
    )
    session.add(empty)
    await session.commit()

    svc = RecipeProductionService(session)
    with pytest.raises(ConflictError):
        await svc.preview(scenario["restaurant_a"], empty.id, batches=Decimal("1"))


# --- confirm --- #


@pytest.mark.asyncio
async def test_confirm_happy_path_creates_production_and_movements(session, scenario):
    earlier = await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["tomato"].id,
        scenario["user_id"],
        Decimal("1.000"),
        expiry=TOMORROW,
    )
    later = await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["tomato"].id,
        scenario["user_id"],
        Decimal("5.000"),
        expiry=NEXT_WEEK,
    )
    onion_lot = await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["onion"].id,
        scenario["user_id"],
        Decimal("2.000"),
        expiry=NEXT_WEEK,
    )
    await session.commit()

    svc = RecipeProductionService(session)
    production = await svc.confirm(
        restaurant_id=scenario["restaurant_a"],
        recipe_id=scenario["recipe"].id,
        batches=Decimal("1"),
        produced_by_user_id=scenario["user_id"],
        notes="lunch service",
    )

    assert production.id is not None
    assert production.batches == Decimal("1.000")
    assert production.notes == "lunch service"

    # Production row persisted.
    row = (
        await session.exec(select(RecipeProduction).where(RecipeProduction.id == production.id))
    ).first()
    assert row is not None

    # Stock movements created and tagged correctly.
    moves = (
        await session.exec(select(StockMovement).where(StockMovement.source_id == production.id))
    ).all()
    moves_list = list(moves)
    # Expect 3 consume movements: 2 from tomato FEFO + 1 from onion.
    assert len(moves_list) == 3
    for m in moves_list:
        assert m.source == MovementSource.RECIPE
        assert m.kind == "consume"
        assert m.quantity < 0  # outflow

    # FEFO: earlier tomato lot fully drained, later partially.
    await session.refresh(earlier)
    await session.refresh(later)
    await session.refresh(onion_lot)
    assert earlier.quantity_remaining == Decimal("0.000")
    assert earlier.status == LotStatus.DEPLETED
    assert later.quantity_remaining == Decimal("4.000")
    assert onion_lot.quantity_remaining == Decimal("1.500")


@pytest.mark.asyncio
async def test_confirm_insufficient_stock_rolls_back(session, scenario):
    # Only 0.5kg of tomato; recipe needs 2kg. Onion is fine.
    await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["tomato"].id,
        scenario["user_id"],
        Decimal("0.500"),
        expiry=NEXT_WEEK,
    )
    onion_lot = await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["onion"].id,
        scenario["user_id"],
        Decimal("5.000"),
        expiry=NEXT_WEEK,
    )
    await session.commit()

    svc = RecipeProductionService(session)
    with pytest.raises(InsufficientStockError):
        await svc.confirm(
            restaurant_id=scenario["restaurant_a"],
            recipe_id=scenario["recipe"].id,
            batches=Decimal("1"),
            produced_by_user_id=scenario["user_id"],
        )

    # Onion was NOT consumed because the whole thing was rolled back.
    await session.refresh(onion_lot)
    assert onion_lot.quantity_remaining == Decimal("5.000")
    # No production rows.
    productions = (await session.exec(select(RecipeProduction))).all()
    assert list(productions) == []


@pytest.mark.asyncio
async def test_confirm_unit_mismatch_blocks_before_any_consume(session, scenario):
    # Salt ingredient has bad unit.
    bad_ing = RecipeIngredient(
        restaurant_id=scenario["restaurant_a"],
        recipe_id=scenario["recipe"].id,
        product_id=scenario["salt_g"].id,
        quantity=Decimal("0.010"),
        unit="kg",
    )
    session.add(bad_ing)
    tomato_lot = await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["tomato"].id,
        scenario["user_id"],
        Decimal("5.000"),
        expiry=NEXT_WEEK,
    )
    await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["onion"].id,
        scenario["user_id"],
        Decimal("5.000"),
        expiry=NEXT_WEEK,
    )
    await session.commit()

    svc = RecipeProductionService(session)
    with pytest.raises(ConflictError):
        await svc.confirm(
            restaurant_id=scenario["restaurant_a"],
            recipe_id=scenario["recipe"].id,
            batches=Decimal("1"),
            produced_by_user_id=scenario["user_id"],
        )

    # Tomato was NOT consumed (pre-flight check stops before any consume).
    await session.refresh(tomato_lot)
    assert tomato_lot.quantity_remaining == Decimal("5.000")


@pytest.mark.asyncio
async def test_confirm_inactive_recipe_raises_409(session, scenario):
    recipe = scenario["recipe"]
    recipe.is_active = False
    session.add(recipe)
    await session.commit()

    svc = RecipeProductionService(session)
    with pytest.raises(ConflictError):
        await svc.confirm(
            restaurant_id=scenario["restaurant_a"],
            recipe_id=recipe.id,
            batches=Decimal("1"),
            produced_by_user_id=scenario["user_id"],
        )


@pytest.mark.asyncio
async def test_confirm_cross_tenant_returns_404(session, scenario):
    svc = RecipeProductionService(session)
    with pytest.raises(NotFoundError):
        await svc.confirm(
            restaurant_id=scenario["restaurant_b"],
            recipe_id=scenario["recipe"].id,
            batches=Decimal("1"),
            produced_by_user_id=scenario["user_id"],
        )


# --- regression: Pydantic vs ORM shape --- #


@pytest.mark.asyncio
async def test_production_read_validates_orm_shape(session, scenario):
    """Guard against str-vs-datetime drift on produced_at/created_at."""
    await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["tomato"].id,
        scenario["user_id"],
        Decimal("5.000"),
        expiry=NEXT_WEEK,
    )
    await _make_lot(
        session,
        scenario["restaurant_a"],
        scenario["onion"].id,
        scenario["user_id"],
        Decimal("5.000"),
        expiry=NEXT_WEEK,
    )
    await session.commit()

    svc = RecipeProductionService(session)
    production = await svc.confirm(
        restaurant_id=scenario["restaurant_a"],
        recipe_id=scenario["recipe"].id,
        batches=Decimal("1"),
        produced_by_user_id=scenario["user_id"],
    )
    await session.refresh(production)

    read = RecipeProductionRead.model_validate(production)
    assert isinstance(read.produced_at, datetime)
    assert isinstance(read.created_at, datetime)
    assert read.batches == Decimal("1.000")
