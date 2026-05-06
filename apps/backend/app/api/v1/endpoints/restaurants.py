"""Restaurant CRUD + membership management."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import (
    CurrentMembership,
    CurrentUser,
    get_session,
    require_permission,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.core.permissions import Permission
from app.models.membership import RestaurantMembership
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.restaurant import (
    MemberInvite,
    MemberRead,
    MemberRoleUpdate,
    RestaurantCreate,
    RestaurantRead,
)
from app.services.haccp_service import HACCPService

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


@router.get("", response_model=list[RestaurantRead])
async def list_my_restaurants(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[Restaurant]:
    result = await session.exec(
        select(Restaurant)
        .join(
            RestaurantMembership,
            RestaurantMembership.restaurant_id == Restaurant.id,  # type: ignore[arg-type]
        )
        .where(
            RestaurantMembership.user_id == current_user.id,
            RestaurantMembership.is_active.is_(True),  # type: ignore[attr-defined]
            Restaurant.is_active.is_(True),  # type: ignore[attr-defined]
        )
    )
    return list(result.all())


@router.post("", response_model=RestaurantRead, status_code=201)
async def create_restaurant(
    data: RestaurantCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Restaurant:
    restaurant = Restaurant(**data.model_dump())
    session.add(restaurant)
    await session.flush()

    membership = RestaurantMembership(
        restaurant_id=restaurant.id,
        user_id=current_user.id,
        role="owner",
    )
    session.add(membership)
    await session.flush()

    haccp_svc = HACCPService(session)
    await haccp_svc.create_seed_templates(
        restaurant_id=restaurant.id,
        created_by_user_id=current_user.id,
    )

    await session.commit()
    await session.refresh(restaurant)
    return restaurant


@router.get("/{restaurant_id}", response_model=RestaurantRead)
async def get_restaurant(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> Restaurant:
    result = await session.exec(select(Restaurant).where(Restaurant.id == membership.restaurant_id))
    restaurant = result.first()
    if not restaurant:
        raise NotFoundError("Restaurant")
    return restaurant


@router.put("/{restaurant_id}", response_model=RestaurantRead)
async def update_restaurant(
    data: RestaurantCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.EDIT_RESTAURANT)),
    session: AsyncSession = Depends(get_session),
) -> Restaurant:
    result = await session.exec(select(Restaurant).where(Restaurant.id == membership.restaurant_id))
    restaurant = result.first()
    if not restaurant:
        raise NotFoundError("Restaurant")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(restaurant, field, value)
    session.add(restaurant)
    await session.commit()
    await session.refresh(restaurant)
    return restaurant


@router.get("/{restaurant_id}/members", response_model=list[MemberRead])
async def list_members(
    membership: CurrentMembership,
    session: AsyncSession = Depends(get_session),
) -> list[MemberRead]:
    result = await session.exec(
        select(RestaurantMembership, User)
        .join(User, User.id == RestaurantMembership.user_id)  # type: ignore[arg-type]
        .where(
            RestaurantMembership.restaurant_id == membership.restaurant_id,
            RestaurantMembership.is_active.is_(True),  # type: ignore[attr-defined]
        )
    )
    return [
        MemberRead(
            user_id=m.user_id,
            email=u.email,
            full_name=u.full_name,
            role=m.role,
            is_active=m.is_active,
        )
        for m, u in result.all()
    ]


@router.post("/{restaurant_id}/members", status_code=201)
async def invite_member(
    data: MemberInvite,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_MEMBERS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if data.role not in ("manager", "chef"):
        raise ConflictError("Role must be manager or chef")
    user_result = await session.exec(select(User).where(User.email == data.email))
    user = user_result.first()
    if not user:
        return {
            "status": "pending",
            "message": "User not found. Share the app signup link.",
        }
    existing_result = await session.exec(
        select(RestaurantMembership).where(
            RestaurantMembership.restaurant_id == membership.restaurant_id,
            RestaurantMembership.user_id == user.id,
        )
    )
    existing = existing_result.first()
    if existing:
        existing.is_active = True
        existing.role = data.role
        session.add(existing)
    else:
        session.add(
            RestaurantMembership(
                restaurant_id=membership.restaurant_id,
                user_id=user.id,
                role=data.role,
            )
        )
    await session.commit()
    return {"status": "added"}


@router.put("/{restaurant_id}/members/{user_id}")
async def update_member_role(
    user_id: UUID,
    data: MemberRoleUpdate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_MEMBERS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await session.exec(
        select(RestaurantMembership).where(
            RestaurantMembership.restaurant_id == membership.restaurant_id,
            RestaurantMembership.user_id == user_id,
        )
    )
    target = result.first()
    if not target:
        raise NotFoundError("Member")
    if target.role == "owner":
        raise ConflictError("Cannot change owner role")
    if data.role not in ("manager", "chef"):
        raise ConflictError("Role must be manager or chef")
    target.role = data.role
    session.add(target)
    await session.commit()
    return {"status": "updated"}


@router.delete("/{restaurant_id}/members/{user_id}")
async def remove_member(
    user_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_MEMBERS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await session.exec(
        select(RestaurantMembership).where(
            RestaurantMembership.restaurant_id == membership.restaurant_id,
            RestaurantMembership.user_id == user_id,
        )
    )
    target = result.first()
    if not target:
        raise NotFoundError("Member")
    if target.role == "owner":
        raise ConflictError("Cannot remove owner")
    target.is_active = False
    session.add(target)
    await session.commit()
    return {"status": "removed"}
