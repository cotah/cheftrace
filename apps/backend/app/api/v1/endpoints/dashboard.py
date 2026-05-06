"""Dashboard endpoint."""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session
from app.models.restaurant import Restaurant
from app.schemas.dashboard import DashboardResponseChef, DashboardResponseManager
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/restaurants/{restaurant_id}", tags=["dashboard"])


@router.get(
    "/dashboard",
    response_model=DashboardResponseChef | DashboardResponseManager,
)
async def get_dashboard(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> DashboardResponseChef | DashboardResponseManager:
    restaurant_result = await session.exec(
        select(Restaurant).where(Restaurant.id == membership.restaurant_id)
    )
    restaurant = restaurant_result.first()
    warning_days = restaurant.expiry_warning_days if restaurant else 3
    critical_days = restaurant.critical_expiry_days if restaurant else 1

    svc = DashboardService(session)
    return await svc.get_dashboard(
        restaurant_id=membership.restaurant_id,
        role=membership.role,
        expiry_warning_days=warning_days,
        critical_expiry_days=critical_days,
    )
