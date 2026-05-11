"""Phase 4 Part 4a — pos_item_mappings CRUD service tests.

Endpoints are thin shims; this file exercises the service contract
including the multi-tenant guarantees, the explicit None vs unset
distinction on recipe_id, and the soft-delete fallback.
"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- register all models with SQLModel.metadata
from app.core.exceptions import ConflictError, NotFoundError
from app.models.pos_item_mapping import PosItemMapping
from app.models.recipe import Recipe
from app.models.restaurant import Restaurant
from app.models.user import User
from app.services.pos_integration_service import POSIntegrationService
from app.services.pos_mapping_service import POSItemMappingService

TEST_KEY = "test-master-key-only-for-pytest"


@pytest.fixture
async def db_engine():
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5433/test",
    )
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
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
async def world(session):
    """Two restaurants + one Square integration in A + one recipe in A
    + same setup in B for cross-tenant checks."""
    user = User(email=f"map_{uuid4()}@test.com")
    session.add(user)
    rest_a = Restaurant(name="Map A", country="IE")
    rest_b = Restaurant(name="Map B", country="IE")
    session.add(rest_a)
    session.add(rest_b)
    await session.commit()

    pos_svc = POSIntegrationService(session, encryption_key=TEST_KEY)
    integ_a = await pos_svc.create_integration(
        restaurant_id=rest_a.id,
        provider="square",
        name="POS A",
        external_location_id="LOC_A",
        created_by_user_id=user.id,
    )
    integ_b = await pos_svc.create_integration(
        restaurant_id=rest_b.id,
        provider="square",
        name="POS B",
        external_location_id="LOC_B",
        created_by_user_id=user.id,
    )
    await session.commit()

    recipe_a = Recipe(
        restaurant_id=rest_a.id,
        name="Pasta A",
        yield_quantity=Decimal("1"),
        yield_unit="portion",
    )
    recipe_b = Recipe(
        restaurant_id=rest_b.id,
        name="Pasta B",
        yield_quantity=Decimal("1"),
        yield_unit="portion",
    )
    session.add(recipe_a)
    session.add(recipe_b)
    await session.commit()

    return {
        "user_id": user.id,
        "rest_a": rest_a.id,
        "rest_b": rest_b.id,
        "integ_a": integ_a.id,
        "integ_b": integ_b.id,
        "recipe_a": recipe_a.id,
        "recipe_b": recipe_b.id,
    }


# --- CRUD happy path --- #


@pytest.mark.asyncio
async def test_create_mapping_happy_path(session, world):
    svc = POSItemMappingService(session)
    mapping = await svc.create_mapping(
        restaurant_id=world["rest_a"],
        integration_id=world["integ_a"],
        external_item_id="item_1",
        external_item_name_snapshot="Pasta",
        recipe_id=world["recipe_a"],
        units_per_sale=Decimal("1.000"),
    )
    assert mapping.id is not None
    assert mapping.is_active is True
    assert mapping.recipe_id == world["recipe_a"]
    assert mapping.units_per_sale == Decimal("1.000")


@pytest.mark.asyncio
async def test_create_mapping_with_null_recipe_means_ignore(session, world):
    """recipe_id=None is a valid 'ignore this item' mapping."""
    svc = POSItemMappingService(session)
    mapping = await svc.create_mapping(
        restaurant_id=world["rest_a"],
        integration_id=world["integ_a"],
        external_item_id="gift_card",
        external_item_name_snapshot="Gift Card",
        recipe_id=None,
        units_per_sale=Decimal("1"),
    )
    assert mapping.recipe_id is None


@pytest.mark.asyncio
async def test_create_duplicate_external_id_raises_conflict(session, world):
    svc = POSItemMappingService(session)
    await svc.create_mapping(
        restaurant_id=world["rest_a"],
        integration_id=world["integ_a"],
        external_item_id="dup",
        external_item_name_snapshot="x",
        recipe_id=None,
        units_per_sale=Decimal("1"),
    )
    await session.commit()
    with pytest.raises(ConflictError):
        await svc.create_mapping(
            restaurant_id=world["rest_a"],
            integration_id=world["integ_a"],
            external_item_id="dup",
            external_item_name_snapshot="x again",
            recipe_id=None,
            units_per_sale=Decimal("1"),
        )


@pytest.mark.asyncio
async def test_create_with_cross_tenant_recipe_raises(session, world):
    """Recipe in B can't be linked from A's integration."""
    svc = POSItemMappingService(session)
    with pytest.raises(NotFoundError):
        await svc.create_mapping(
            restaurant_id=world["rest_a"],
            integration_id=world["integ_a"],
            external_item_id="bad",
            external_item_name_snapshot="x",
            recipe_id=world["recipe_b"],
            units_per_sale=Decimal("1"),
        )


# --- listing + multi-tenant isolation --- #


@pytest.mark.asyncio
async def test_list_returns_only_own_tenant(session, world):
    svc = POSItemMappingService(session)
    await svc.create_mapping(
        restaurant_id=world["rest_a"],
        integration_id=world["integ_a"],
        external_item_id="a_item",
        external_item_name_snapshot="A",
        recipe_id=world["recipe_a"],
        units_per_sale=Decimal("1"),
    )
    await svc.create_mapping(
        restaurant_id=world["rest_b"],
        integration_id=world["integ_b"],
        external_item_id="b_item",
        external_item_name_snapshot="B",
        recipe_id=world["recipe_b"],
        units_per_sale=Decimal("1"),
    )
    await session.commit()

    a_rows = await svc.list_mappings(world["rest_a"], world["integ_a"])
    b_rows = await svc.list_mappings(world["rest_b"], world["integ_b"])
    assert len(a_rows) == 1
    assert a_rows[0].external_item_id == "a_item"
    assert len(b_rows) == 1
    assert b_rows[0].external_item_id == "b_item"


@pytest.mark.asyncio
async def test_get_cross_tenant_returns_404(session, world):
    svc = POSItemMappingService(session)
    a_mapping = await svc.create_mapping(
        restaurant_id=world["rest_a"],
        integration_id=world["integ_a"],
        external_item_id="a",
        external_item_name_snapshot="A",
        recipe_id=world["recipe_a"],
        units_per_sale=Decimal("1"),
    )
    await session.commit()
    with pytest.raises(NotFoundError):
        await svc.get_mapping(world["rest_b"], world["integ_b"], a_mapping.id)


# --- updates: explicit None vs unset --- #


@pytest.mark.asyncio
async def test_update_flips_recipe_to_none_means_ignore(session, world):
    """The flow that matters: owner changes a mapped item to ignore.

    Replicates what the endpoint does: model_dump(exclude_unset=True)
    keeps recipe_id=None in the dict (because the caller set it
    explicitly), so the service flips the column to NULL.
    """
    svc = POSItemMappingService(session)
    mapping = await svc.create_mapping(
        restaurant_id=world["rest_a"],
        integration_id=world["integ_a"],
        external_item_id="flip",
        external_item_name_snapshot="Flip",
        recipe_id=world["recipe_a"],
        units_per_sale=Decimal("1"),
    )
    await session.commit()
    assert mapping.recipe_id == world["recipe_a"]

    updated = await svc.update_mapping(
        restaurant_id=world["rest_a"],
        integration_id=world["integ_a"],
        mapping_id=mapping.id,
        update={"recipe_id": None},  # explicit None — the ignore state
    )
    assert updated.recipe_id is None


@pytest.mark.asyncio
async def test_update_unset_recipe_leaves_it_alone(session, world):
    """Same service signature: empty update -> no-op on recipe_id."""
    svc = POSItemMappingService(session)
    mapping = await svc.create_mapping(
        restaurant_id=world["rest_a"],
        integration_id=world["integ_a"],
        external_item_id="keep",
        external_item_name_snapshot="Keep",
        recipe_id=world["recipe_a"],
        units_per_sale=Decimal("1"),
    )
    await session.commit()

    updated = await svc.update_mapping(
        restaurant_id=world["rest_a"],
        integration_id=world["integ_a"],
        mapping_id=mapping.id,
        update={"units_per_sale": Decimal("2.500")},
    )
    assert updated.recipe_id == world["recipe_a"]
    assert updated.units_per_sale == Decimal("2.500")


@pytest.mark.asyncio
async def test_update_cross_tenant_recipe_raises(session, world):
    svc = POSItemMappingService(session)
    mapping = await svc.create_mapping(
        restaurant_id=world["rest_a"],
        integration_id=world["integ_a"],
        external_item_id="any",
        external_item_name_snapshot="x",
        recipe_id=None,
        units_per_sale=Decimal("1"),
    )
    await session.commit()
    with pytest.raises(NotFoundError):
        await svc.update_mapping(
            restaurant_id=world["rest_a"],
            integration_id=world["integ_a"],
            mapping_id=mapping.id,
            update={"recipe_id": world["recipe_b"]},
        )


# --- soft delete --- #


@pytest.mark.asyncio
async def test_delete_is_soft(session, world):
    svc = POSItemMappingService(session)
    mapping = await svc.create_mapping(
        restaurant_id=world["rest_a"],
        integration_id=world["integ_a"],
        external_item_id="trash",
        external_item_name_snapshot="x",
        recipe_id=None,
        units_per_sale=Decimal("1"),
    )
    await session.commit()
    await svc.delete_mapping(world["rest_a"], world["integ_a"], mapping.id)
    await session.commit()

    # Row still exists, just inactive.
    fetched = (
        await session.exec(select(PosItemMapping).where(PosItemMapping.id == mapping.id))
    ).first()
    assert fetched is not None
    assert fetched.is_active is False


# --- regression: integration FK enforced --- #


@pytest.mark.asyncio
async def test_create_for_unknown_integration_raises_404(session, world):
    svc = POSItemMappingService(session)
    with pytest.raises(NotFoundError):
        await svc.create_mapping(
            restaurant_id=world["rest_a"],
            integration_id=uuid4(),
            external_item_id="x",
            external_item_name_snapshot="x",
            recipe_id=None,
            units_per_sale=Decimal("1"),
        )
