"""Stock movement action endpoints."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.permissions import Permission
from app.models.membership import RestaurantMembership
from app.models.stock_movement import StockMovement
from app.schemas.stock import AdjustmentInput, ManualInInput, ManualOutInput, MovementRead
from app.services.stock_service import StockService

router = APIRouter(prefix="/restaurants/{restaurant_id}/stock", tags=["stock"])


@router.get("/movements", response_model=list[MovementRead])
async def list_movements(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> list[StockMovement]:
    result = await session.exec(
        select(StockMovement)
        .where(StockMovement.restaurant_id == membership.restaurant_id)
        .order_by(StockMovement.created_at.desc())  # type: ignore[attr-defined]
        .limit(200)
    )
    return list(result.all())


@router.post("/manual-in", response_model=MovementRead, status_code=201)
async def manual_in(
    data: ManualInInput,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> StockMovement:
    svc = StockService(session)
    movement = await svc.manual_in(
        restaurant_id=membership.restaurant_id,
        product_id=data.product_id,
        lot_id=data.lot_id,
        quantity=data.quantity,
        unit=data.unit,
        created_by_user_id=membership.user_id,
        reason=data.reason,
        notes=data.notes,
    )
    await session.commit()
    await session.refresh(movement)
    return movement


@router.post("/manual-out", response_model=list[MovementRead], status_code=201)
async def manual_out(
    data: ManualOutInput,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> list[StockMovement]:
    svc = StockService(session)
    movements = await svc.manual_out(
        restaurant_id=membership.restaurant_id,
        product_id=data.product_id,
        quantity=data.quantity,
        unit=data.unit,
        created_by_user_id=membership.user_id,
        lot_id=data.lot_id,
        reason=data.reason,
        notes=data.notes,
    )
    await session.commit()
    for m in movements:
        await session.refresh(m)
    return movements


@router.post("/adjustment", response_model=MovementRead, status_code=201)
async def adjustment(
    data: AdjustmentInput,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> StockMovement:
    svc = StockService(session)
    movement = await svc.adjustment(
        restaurant_id=membership.restaurant_id,
        product_id=data.product_id,
        quantity=data.quantity,
        unit=data.unit,
        reason=data.reason,
        created_by_user_id=membership.user_id,
        lot_id=data.lot_id,
        notes=data.notes,
    )
    await session.commit()
    await session.refresh(movement)
    return movement
