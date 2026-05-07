"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    categories,
    dashboard,
    equipment,
    haccp,
    health,
    products,
    purchase_lists,
    reports,
    restaurants,
    stock,
    stock_lots,
    suppliers,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(restaurants.router)
api_router.include_router(categories.router)
api_router.include_router(suppliers.router)
api_router.include_router(products.router)
api_router.include_router(stock_lots.router)
api_router.include_router(stock.router)
api_router.include_router(equipment.router)
api_router.include_router(haccp.router)
api_router.include_router(dashboard.router)
api_router.include_router(purchase_lists.router)
api_router.include_router(reports.router)
