"""Equipment and temperature log endpoints."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.models.equipment import Equipment
from app.models.membership import RestaurantMembership
from app.models.temperature_log import TemperatureLog
from app.schemas.equipment import (
    EquipmentCreate,
    EquipmentRead,
    TemperatureLogCreate,
    TemperatureLogRead,
)

router = APIRouter(prefix="/restaurants/{restaurant_id}", tags=["equipment"])


@router.get("/equipment", response_model=list[EquipmentRead])
async def list_equipment(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> list[Equipment]:
    result = await session.exec(
        select(Equipment).where(
            Equipment.restaurant_id == membership.restaurant_id,
            Equipment.is_active == True,  # noqa: E712
        )
    )
    return list(result.all())


@router.post("/equipment", response_model=EquipmentRead, status_code=201)
async def create_equipment(
    data: EquipmentCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_EQUIPMENT)),
    session: AsyncSession = Depends(get_session),
) -> Equipment:
    equipment = Equipment(restaurant_id=membership.restaurant_id, **data.model_dump())
    session.add(equipment)
    await session.commit()
    await session.refresh(equipment)
    return equipment


@router.put("/equipment/{equipment_id}", response_model=EquipmentRead)
async def update_equipment(
    equipment_id: UUID,
    data: EquipmentCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_EQUIPMENT)),
    session: AsyncSession = Depends(get_session),
) -> Equipment:
    result = await session.exec(
        select(Equipment).where(
            Equipment.id == equipment_id,
            Equipment.restaurant_id == membership.restaurant_id,
        )
    )
    equipment = result.first()
    if not equipment:
        raise NotFoundError("Equipment")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(equipment, field, value)
    session.add(equipment)
    await session.commit()
    await session.refresh(equipment)
    return equipment


@router.delete("/equipment/{equipment_id}", status_code=204)
async def delete_equipment(
    equipment_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.SOFT_DELETE)),
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.exec(
        select(Equipment).where(
            Equipment.id == equipment_id,
            Equipment.restaurant_id == membership.restaurant_id,
        )
    )
    equipment = result.first()
    if not equipment:
        raise NotFoundError("Equipment")
    equipment.is_active = False
    session.add(equipment)
    await session.commit()


@router.post("/temperature-logs", response_model=TemperatureLogRead, status_code=201)
async def create_temperature_log(
    data: TemperatureLogCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_HACCP)),
    session: AsyncSession = Depends(get_session),
) -> TemperatureLog:
    eq_result = await session.exec(
        select(Equipment).where(
            Equipment.id == data.equipment_id,
            Equipment.restaurant_id == membership.restaurant_id,
            Equipment.is_active == True,  # noqa: E712
        )
    )
    equipment = eq_result.first()
    if not equipment:
        raise NotFoundError("Equipment")

    temperature = Decimal(str(data.temperature))
    is_out_of_range = False
    if equipment.min_temp is not None and temperature < equipment.min_temp:
        is_out_of_range = True
    if equipment.max_temp is not None and temperature > equipment.max_temp:
        is_out_of_range = True

    recorded_at = (
        datetime.fromisoformat(data.recorded_at)
        if data.recorded_at
        else datetime.now(UTC).replace(tzinfo=None)
    )

    log = TemperatureLog(
        restaurant_id=membership.restaurant_id,
        equipment_id=data.equipment_id,
        temperature=temperature,
        is_out_of_range=is_out_of_range,
        notes=data.notes,
        recorded_by_user_id=membership.user_id,
        recorded_at=recorded_at,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


@router.get("/temperature-logs", response_model=list[TemperatureLogRead])
async def list_temperature_logs(
    membership: CurrentMembership,
    equipment_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[TemperatureLog]:
    query = select(TemperatureLog).where(
        TemperatureLog.restaurant_id == membership.restaurant_id,
    )
    if equipment_id:
        query = query.where(TemperatureLog.equipment_id == equipment_id)
    query = query.order_by(TemperatureLog.recorded_at.desc()).limit(200)  # type: ignore[attr-defined]
    result = await session.exec(query)
    return list(result.all())
