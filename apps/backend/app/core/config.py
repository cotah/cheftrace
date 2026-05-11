"""Application configuration using pydantic-settings."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = Field(..., description="PostgreSQL connection string")

    @field_validator("database_url")
    @classmethod
    def fix_async_scheme(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_anon_key: str = Field(..., description="Supabase anon public key")
    supabase_jwt_secret: str = Field(..., description="Supabase JWT secret for token verification")
    supabase_service_role_key: str | None = Field(
        default=None,
        description="Supabase service role key — required for signed Storage URLs (Phase 2+)",
    )
    invoices_bucket: str = Field(
        default="invoices",
        description="Supabase Storage bucket name for invoice files",
    )

    gemini_api_key: str | None = Field(
        default=None,
        description="Google AI Studio API key — required for OCR (Phase 2 Sprint 6+)",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model id used for invoice OCR",
    )
    ocr_match_threshold: float = Field(
        default=70.0,
        description="rapidfuzz score (0-100) below which a product match is treated as no match",
    )

    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
