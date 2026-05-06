"""Dashboard service tests."""

import os
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- register all models with SQLModel.metadata
from app.models.product import Product
from app.models.restaurant import Restaurant
from app.models.stock_lot import StockLot
from app.models.user import User
from app.services.dashboard_service import DashboardService

TODAY = date.today()


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
    user = User(email=f"dash_{uuid4()}@test.com")
    session.add(user)
    restaurant = Restaurant(
        name="Dashboard Test",
        country="IE",
        expiry_warning_days=3,
        critical_expiry_days=1,
    )
    session.add(restaurant)
    await session.flush()
    product = Product(
        restaurant_id=restaurant.id,
        name="Test Product",
        unit="kg",
        expiry_required=True,
    )
    session.add(product)
    await session.flush()
    return {
        "user": user.id,
        "restaurant": restaurant.id,
        "restaurant_obj": restaurant,
        "product": product.id,
    }


@pytest.mark.asyncio
async def test_dashboard_empty_restaurant(session, test_data):
    svc = DashboardService(session)
    result = await svc.get_dashboard(test_data["restaurant"], role="owner")
    assert result.expiry_alerts == []
    assert result.critical_expiry == []
    assert result.low_stock == []
    assert result.haccp_pending == []


@pytest.mark.asyncio
async def test_dashboard_chef_has_no_financial_fields(session, test_data):
    svc = DashboardService(session)
    result = await svc.get_dashboard(test_data["restaurant"], role="chef")
    assert not hasattr(result, "stock_value_eur")
    assert not hasattr(result, "lots_without_cost")


@pytest.mark.asyncio
async def test_dashboard_manager_has_financial_fields(session, test_data):
    svc = DashboardService(session)
    result = await svc.get_dashboard(test_data["restaurant"], role="manager")
    assert hasattr(result, "stock_value_eur")
    assert hasattr(result, "lots_without_cost")


@pytest.mark.asyncio
async def test_dashboard_expiry_alert_triggered(session, test_data):
    lot = StockLot(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        quantity_received=Decimal("5"),
        quantity_remaining=Decimal("5"),
        unit="kg",
        expiry_date=TODAY + timedelta(days=2),
        status="active",
        created_by_user_id=test_data["user"],
    )
    session.add(lot)
    await session.flush()
    svc = DashboardService(session)
    result = await svc.get_dashboard(
        test_data["restaurant"],
        role="owner",
        expiry_warning_days=3,
        critical_expiry_days=1,
    )
    assert len(result.expiry_alerts) == 1
    assert result.expiry_alerts[0].days_left == 2


@pytest.mark.asyncio
async def test_dashboard_critical_expiry_triggered(session, test_data):
    lot = StockLot(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        quantity_received=Decimal("3"),
        quantity_remaining=Decimal("3"),
        unit="kg",
        expiry_date=TODAY,
        status="active",
        created_by_user_id=test_data["user"],
    )
    session.add(lot)
    await session.flush()
    svc = DashboardService(session)
    result = await svc.get_dashboard(
        test_data["restaurant"],
        role="owner",
        critical_expiry_days=1,
    )
    assert len(result.critical_expiry) >= 1


@pytest.mark.asyncio
async def test_dashboard_stock_value_computed(session, test_data):
    lot = StockLot(
        restaurant_id=test_data["restaurant"],
        product_id=test_data["product"],
        quantity_received=Decimal("10"),
        quantity_remaining=Decimal("10"),
        unit="kg",
        unit_cost=Decimal("5.00"),
        expiry_date=TODAY + timedelta(days=30),
        status="active",
        created_by_user_id=test_data["user"],
    )
    session.add(lot)
    await session.flush()
    svc = DashboardService(session)
    result = await svc.get_dashboard(test_data["restaurant"], role="manager")
    assert result.stock_value_eur == 50.0
    assert result.stock_value_partial is False
    assert result.lots_without_cost == 0
