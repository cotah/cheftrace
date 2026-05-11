"""FastAPI dependency providers for integrations.

Tests override these via app.dependency_overrides[...] to inject fakes.
"""

from app.core.config import settings
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
