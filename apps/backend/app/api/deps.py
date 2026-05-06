"""FastAPI dependencies: auth, multi-tenant, permissions."""

from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, Header, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session as get_session
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.permissions import Permission, has_permission
from app.core.security import verify_supabase_token
from app.models.membership import RestaurantMembership
from app.models.user import User

logger = structlog.get_logger(__name__)


async def get_current_user(
    authorization: Annotated[str, Header()],
    session: AsyncSession = Depends(get_session),
) -> User:
    """Verify Supabase JWT and upsert user record."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization.removeprefix("Bearer ")
    payload = await verify_supabase_token(token)
    user_id = UUID(payload["sub"])
    email = payload.get("email", "")
    result = await session.exec(select(User).where(User.id == user_id))
    user = result.first()
    if not user:
        user = User(id=user_id, email=email)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_membership(
    restaurant_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> RestaurantMembership:
    """Return active membership or 404. Never 403."""
    result = await session.exec(
        select(RestaurantMembership).where(
            RestaurantMembership.restaurant_id == restaurant_id,
            RestaurantMembership.user_id == current_user.id,
            RestaurantMembership.is_active.is_(True),  # type: ignore[attr-defined]
        )
    )
    membership = result.first()
    if not membership:
        raise NotFoundError("Restaurant")
    return membership


CurrentMembership = Annotated[RestaurantMembership, Depends(get_current_membership)]


def require_permission(
    permission: Permission,
) -> Callable[[RestaurantMembership], Awaitable[RestaurantMembership]]:
    """Dependency factory for permission checks."""

    async def check(
        membership: CurrentMembership,
    ) -> RestaurantMembership:
        if not has_permission(membership.role, permission):
            raise ForbiddenError()
        return membership

    return check
