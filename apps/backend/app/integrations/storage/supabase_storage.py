"""Supabase Storage adapter.

Uses Supabase Storage REST API directly via httpx. Requires
SUPABASE_SERVICE_ROLE_KEY (NOT the anon key — service role is needed
to issue signed URLs for private buckets).

Buckets must be created out-of-band in the Supabase dashboard.
"""

import httpx

from app.integrations.storage.base import StorageProvider


class SupabaseStorageProvider(StorageProvider):
    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self._base = supabase_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {service_role_key}",
            "apikey": service_role_key,
            "Content-Type": "application/json",
        }

    async def generate_upload_url(self, bucket: str, path: str, expires_in: int = 300) -> str:
        # Supabase signed upload endpoint returns a token; the client uploads to
        # /storage/v1/object/upload/sign/{bucket}/{path}?token=...
        url = f"{self._base}/storage/v1/object/upload/sign/{bucket}/{path}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=self._headers, json={})
            resp.raise_for_status()
            data = resp.json()
        token = data.get("token") or data.get("signedURL", "").split("token=")[-1]
        return f"{self._base}/storage/v1/object/upload/sign/{bucket}/{path}?token={token}"

    async def generate_download_url(self, bucket: str, path: str, expires_in: int = 300) -> str:
        url = f"{self._base}/storage/v1/object/sign/{bucket}/{path}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=self._headers, json={"expiresIn": expires_in})
            resp.raise_for_status()
            data = resp.json()
        signed_path = data.get("signedURL") or ""
        if signed_path.startswith("/"):
            return f"{self._base}/storage/v1{signed_path}"
        return signed_path
