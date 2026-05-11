"""In-memory fake storage provider for tests.

Returns deterministic URLs so test assertions are stable. Records every
URL it issued for inspection.
"""

from app.integrations.storage.base import StorageProvider


class FakeStorageProvider(StorageProvider):
    def __init__(self) -> None:
        self.upload_urls: list[tuple[str, str, int]] = []
        self.download_urls: list[tuple[str, str, int]] = []
        self.deleted: list[tuple[str, str]] = []

    async def generate_upload_url(self, bucket: str, path: str, expires_in: int = 300) -> str:
        self.upload_urls.append((bucket, path, expires_in))
        return f"https://fake.storage/upload/{bucket}/{path}?expires={expires_in}"

    async def generate_download_url(self, bucket: str, path: str, expires_in: int = 300) -> str:
        self.download_urls.append((bucket, path, expires_in))
        return f"https://fake.storage/download/{bucket}/{path}?expires={expires_in}"

    async def delete_object(self, bucket: str, path: str) -> None:
        self.deleted.append((bucket, path))
