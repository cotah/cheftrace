"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    categories,
    health,
    products,
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
