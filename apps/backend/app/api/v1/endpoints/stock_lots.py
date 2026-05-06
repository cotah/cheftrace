"""Stock lot endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.models.membership import RestaurantMembership
from app.models.product import Product
from app.models.stock_lot import StockLot
from app.schemas.stock import LotCreate, LotExpiryUpdate, LotRead
from app.services.stock_service import StockService

router = APIRouter(prefix="/restaurants/{restaurant_id}/stock-lots", tags=["stock"])


@router.get("", response_model=list[LotRead])
async def list_lots(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> list[StockLot]:
    result = await session.exec(
        select(StockLot)
        .where(
            StockLot.restaurant_id == membership.restaurant_id,
        )
        .order_by(StockLot.expiry_date.asc().nulls_last())  # type: ignore[union-attr]
    )
    return list(result.all())


@router.post("", response_model=LotRead, status_code=201)
async def receive_lot(
    data: LotCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> StockLot:
    # Enforce expiry_required business rule server-side
    product_result = await session.exec(
        select(Product).where(
            Product.id == data.product_id,
            Product.restaurant_id == membership.restaurant_id,
        )
    )
    product = product_result.first()
    if not product:
        raise NotFoundError("Product")
    if product.expiry_required and data.expiry_date is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail="expiry_date is required for this product",
        )

    svc = StockService(session)
    lot = await svc.receive(
        restaurant_id=membership.restaurant_id,
        product_id=data.product_id,
        supplier_id=data.supplier_id,
        quantity=data.quantity_received,
        unit=data.unit,
        created_by_user_id=membership.user_id,
        unit_cost=data.unit_cost,
        expiry_date=data.expiry_date,
        received_date=data.received_date,
        notes=data.notes,
    )
    await session.commit()
    await session.refresh(lot)
    return lot


@router.put("/{lot_id}/expiry", response_model=LotRead)
async def update_lot_expiry(
    lot_id: UUID,
    data: LotExpiryUpdate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> StockLot:
    svc = StockService(session)
    lot = await svc.edit_lot_expiry(
        restaurant_id=membership.restaurant_id,
        lot_id=lot_id,
        new_expiry_date=data.expiry_date,
        reason=data.reason,
        changed_by_user_id=membership.user_id,
    )
    await session.commit()
    await session.refresh(lot)
    return lot


@router.post("/{lot_id}/discard", response_model=LotRead)
async def discard_lot(
    lot_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> StockLot:
    result = await session.exec(
        select(StockLot).where(
            StockLot.id == lot_id,
            StockLot.restaurant_id == membership.restaurant_id,
        )
    )
    lot = result.first()
    if not lot:
        raise NotFoundError("StockLot")
    svc = StockService(session)
    await svc.discard(
        restaurant_id=membership.restaurant_id,
        product_id=lot.product_id,
        lot_id=lot_id,
        created_by_user_id=membership.user_id,
    )
    await session.commit()
    await session.refresh(lot)
    return lot
