"""Product endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.models.membership import RestaurantMembership
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductRead

router = APIRouter(prefix="/restaurants/{restaurant_id}/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
async def list_products(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> list[Product]:
    result = await session.exec(
        select(Product).where(
            Product.restaurant_id == membership.restaurant_id,
            Product.is_active == True,  # noqa: E712
        )
    )
    return list(result.all())


@router.post("", response_model=ProductRead, status_code=201)
async def create_product(
    data: ProductCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_PRODUCTS)),
    session: AsyncSession = Depends(get_session),
) -> Product:
    product = Product(restaurant_id=membership.restaurant_id, **data.model_dump())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: UUID,
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> Product:
    result = await session.exec(
        select(Product).where(
            Product.id == product_id,
            Product.restaurant_id == membership.restaurant_id,
        )
    )
    product = result.first()
    if not product:
        raise NotFoundError("Product")
    return product


@router.put("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: UUID,
    data: ProductCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_PRODUCTS)),
    session: AsyncSession = Depends(get_session),
) -> Product:
    result = await session.exec(
        select(Product).where(
            Product.id == product_id,
            Product.restaurant_id == membership.restaurant_id,
        )
    )
    product = result.first()
    if not product:
        raise NotFoundError("Product")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.SOFT_DELETE)),
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.exec(
        select(Product).where(
            Product.id == product_id,
            Product.restaurant_id == membership.restaurant_id,
        )
    )
    product = result.first()
    if not product:
        raise NotFoundError("Product")
    product.is_active = False
    session.add(product)
    await session.commit()
