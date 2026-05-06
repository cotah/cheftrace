"""Auth endpoints — user sync via Supabase JWT."""

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.auth import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser) -> UserRead:
    return UserRead(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
    )
