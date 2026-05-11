"""Storage provider abstraction.

All file uploads/downloads go through this interface so we can swap
Supabase Storage for S3/R2/Backblaze without touching business logic.
"""

from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Bucket-and-path file store."""

    @abstractmethod
    async def generate_upload_url(self, bucket: str, path: str, expires_in: int = 300) -> str:
        """Return a pre-signed URL the client can PUT bytes to.

        - bucket: storage bucket name (must exist on the provider).
        - path:   object path inside the bucket (e.g. "<restaurant>/<id>.pdf").
        - expires_in: URL validity in seconds.
        """

    @abstractmethod
    async def generate_download_url(self, bucket: str, path: str, expires_in: int = 300) -> str:
        """Return a pre-signed URL the client can GET the file from."""

    @abstractmethod
    async def delete_object(self, bucket: str, path: str) -> None:
        """Remove an object from the bucket.

        Implementations should be idempotent — deleting a missing object
        must not raise. The caller treats this as best-effort: it logs
        and continues if the object was already gone."""
