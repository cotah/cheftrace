"""Product category endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.models.category import ProductCategory
from app.models.membership import RestaurantMembership
from app.schemas.category import CategoryCreate, CategoryRead

router = APIRouter(prefix="/restaurants/{restaurant_id}/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
async def list_categories(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> list[ProductCategory]:
    result = await session.exec(
        select(ProductCategory).where(
            ProductCategory.restaurant_id == membership.restaurant_id,
            ProductCategory.is_active == True,  # noqa: E712
        )
    )
    return list(result.all())


@router.post("", response_model=CategoryRead, status_code=201)
async def create_category(
    data: CategoryCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_PRODUCTS)),
    session: AsyncSession = Depends(get_session),
) -> ProductCategory:
    category = ProductCategory(restaurant_id=membership.restaurant_id, **data.model_dump())
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.SOFT_DELETE)),
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.exec(
        select(ProductCategory).where(
            ProductCategory.id == category_id,
            ProductCategory.restaurant_id == membership.restaurant_id,
        )
    )
    category = result.first()
    if not category:
        raise NotFoundError("ProductCategory")
    category.is_active = False
    session.add(category)
    await session.commit()
