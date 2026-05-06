from sqlmodel import Field

from app.models.base import TimestampedBase


class User(TimestampedBase, table=True):
    __tablename__ = "users"
    email: str = Field(unique=True, nullable=False, index=True)
    full_name: str | None = None
    preferred_lang: str = Field(default="pt-BR")
