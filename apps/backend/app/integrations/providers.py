"""FastAPI dependency providers for integrations.

Tests override these via app.dependency_overrides[...] to inject fakes.
"""

from fastapi import HTTPException

from app.core.config import settings
from app.integrations.ocr.base import OCRProvider
from app.integrations.ocr.gemini_provider import GeminiOCRProvider
from app.integrations.storage.base import StorageProvider
from app.integrations.storage.supabase_storage import SupabaseStorageProvider


def get_storage_provider() -> StorageProvider:
    """Default storage provider for production. Tests override with FakeStorageProvider."""
    if not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not configured — "
            "required to issue signed Storage URLs. "
            "Set it in .env or environment."
        )
    return SupabaseStorageProvider(
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )


def get_ocr_provider() -> OCRProvider:
    """Default OCR provider for production. Tests override with FakeOCRProvider.

    Raises HTTP 503 (not 500) when Gemini key is missing — the request is
    well-formed; the server just has no OCR backend configured yet.
    """
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=503,
            detail="OCR provider not configured (GEMINI_API_KEY missing).",
        )
    return GeminiOCRProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )
