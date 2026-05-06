"""Supplier endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.models.membership import RestaurantMembership
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierRead

router = APIRouter(prefix="/restaurants/{restaurant_id}/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierRead])
async def list_suppliers(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> list[Supplier]:
    result = await session.exec(
        select(Supplier).where(
            Supplier.restaurant_id == membership.restaurant_id,
            Supplier.is_active == True,  # noqa: E712
        )
    )
    return list(result.all())


@router.post("", response_model=SupplierRead, status_code=201)
async def create_supplier(
    data: SupplierCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_SUPPLIERS)),
    session: AsyncSession = Depends(get_session),
) -> Supplier:
    supplier = Supplier(restaurant_id=membership.restaurant_id, **data.model_dump())
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return supplier


@router.put("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    supplier_id: UUID,
    data: SupplierCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_SUPPLIERS)),
    session: AsyncSession = Depends(get_session),
) -> Supplier:
    result = await session.exec(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.restaurant_id == membership.restaurant_id,
        )
    )
    supplier = result.first()
    if not supplier:
        raise NotFoundError("Supplier")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}", status_code=204)
async def delete_supplier(
    supplier_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.SOFT_DELETE)),
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.exec(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.restaurant_id == membership.restaurant_id,
        )
    )
    supplier = result.first()
    if not supplier:
        raise NotFoundError("Supplier")
    supplier.is_active = False
    session.add(supplier)
    await session.commit()
