from uuid import UUID

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str


class CategoryRead(BaseModel):
    id: UUID
    name: str
    is_active: bool

    model_config = {"from_attributes": True}
