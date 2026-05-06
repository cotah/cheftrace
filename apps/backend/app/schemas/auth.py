from uuid import UUID

from pydantic import BaseModel


class UserRead(BaseModel):
    id: UUID
    email: str
    full_name: str | None = None
