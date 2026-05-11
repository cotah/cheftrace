"""POS integration CRUD + pgcrypto-backed credential storage.

The service is the only place that touches the master encryption key.
Models hold the ciphertext as BYTEA; endpoints take/return plaintext
through these methods and never persist plaintext anywhere else.

Threat model
- Master key in env (POS_ENCRYPTION_KEY). Rotating it requires re-
  encrypting every existing row — a separate operational task.
- Compromising the DB alone does not leak tokens. Compromising the
  app server (env + DB) leaks everything; that's the standard
  symmetric-encryption trade-off.
"""

from uuid import UUID

import structlog
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.pos_integration import PosIntegration

logger = structlog.get_logger(__name__)


class POSIntegrationService:
    def __init__(self, session: AsyncSession, encryption_key: str | None) -> None:
        self._session = session
        self._encryption_key = encryption_key

    def _require_key(self) -> str:
        """Used by credential-touching methods. Other CRUD is fine without."""
        if not self._encryption_key:
            raise ConflictError(
                "POS_ENCRYPTION_KEY is not configured. "
                "Set it in the backend environment before managing POS credentials."
            )
        return self._encryption_key

    async def list_integrations(self, restaurant_id: UUID) -> list[PosIntegration]:
        result = await self._session.exec(
            select(PosIntegration)
            .where(PosIntegration.restaurant_id == restaurant_id)
            .order_by(PosIntegration.created_at.desc())  # type: ignore[attr-defined]
        )
        return list(result.all())

    async def get_integration(self, restaurant_id: UUID, integration_id: UUID) -> PosIntegration:
        result = await self._session.exec(
            select(PosIntegration).where(
                PosIntegration.id == integration_id,
                PosIntegration.restaurant_id == restaurant_id,
            )
        )
        integration = result.first()
        if integration is None:
            # Never reveal cross-tenant existence — same pattern as the rest
            # of the codebase.
            raise NotFoundError("PosIntegration")
        return integration

    async def create_integration(
        self,
        restaurant_id: UUID,
        provider: str,
        name: str,
        external_location_id: str | None,
        created_by_user_id: UUID,
    ) -> PosIntegration:
        integration = PosIntegration(
            restaurant_id=restaurant_id,
            provider=provider,
            name=name,
            external_location_id=external_location_id,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(integration)
        try:
            await self._session.flush()
        except Exception as exc:
            await self._session.rollback()
            # UNIQUE(restaurant_id, provider) violation is the most likely
            # path here; surface as a 409 so the UI can guide the owner to
            # the existing row.
            raise ConflictError(
                f"A {provider} integration already exists for this restaurant."
            ) from exc
        await self._session.refresh(integration)
        logger.info(
            "pos_integration.create",
            restaurant_id=str(restaurant_id),
            integration_id=str(integration.id),
            provider=provider,
        )
        return integration

    async def update_integration(
        self,
        restaurant_id: UUID,
        integration_id: UUID,
        *,
        name: str | None = None,
        external_location_id: str | None = None,
        confirmation_mode: str | None = None,
        is_active: bool | None = None,
    ) -> PosIntegration:
        integration = await self.get_integration(restaurant_id, integration_id)
        if name is not None:
            integration.name = name
        if external_location_id is not None:
            integration.external_location_id = external_location_id
        if confirmation_mode is not None:
            integration.confirmation_mode = confirmation_mode
        if is_active is not None:
            integration.is_active = is_active
        self._session.add(integration)
        await self._session.flush()
        await self._session.refresh(integration)
        return integration

    async def soft_delete(self, restaurant_id: UUID, integration_id: UUID) -> None:
        """Disable the integration. Past pos_events stay around for audit;
        new webhooks are rejected when the integration is is_active=False
        (enforced in the webhook endpoint in Part 2/4).
        """
        integration = await self.get_integration(restaurant_id, integration_id)
        integration.is_active = False
        self._session.add(integration)
        await self._session.flush()

    # --- credential management (encryption boundary) --- #

    async def set_credentials(
        self,
        restaurant_id: UUID,
        integration_id: UUID,
        access_token: str,
        webhook_signing_key: str,
    ) -> PosIntegration:
        """Encrypt and persist both secrets in a single statement.

        Both are required together — an integration without a webhook
        signing key can't verify inbound events, and one without an
        access token can't sync items or fetch missed orders.
        """
        key = self._require_key()
        # Validate the row exists and belongs to the tenant before mutating.
        integration = await self.get_integration(restaurant_id, integration_id)
        await self._session.execute(
            text(
                "UPDATE pos_integrations SET "
                "access_token_encrypted = pgp_sym_encrypt(:tok, :key), "
                "webhook_signing_key_encrypted = pgp_sym_encrypt(:sig, :key), "
                "updated_at = NOW() "
                "WHERE id = :id AND restaurant_id = :rid"
            ),
            {
                "tok": access_token,
                "sig": webhook_signing_key,
                "key": key,
                "id": integration_id,
                "rid": restaurant_id,
            },
        )
        await self._session.flush()
        # The raw UPDATE bypassed the identity map, so the in-memory copy
        # still has the old NULL ciphertext. Refresh pulls the new BYTEA
        # values back into the Python object the caller is using.
        await self._session.refresh(integration)
        return integration

    async def get_access_token(self, restaurant_id: UUID, integration_id: UUID) -> str | None:
        """Return the decrypted access token or None if not set yet."""
        key = self._require_key()
        result = await self._session.execute(
            text(
                "SELECT pgp_sym_decrypt(access_token_encrypted, :key)::text "
                "FROM pos_integrations "
                "WHERE id = :id "
                "AND restaurant_id = :rid "
                "AND access_token_encrypted IS NOT NULL"
            ),
            {"key": key, "id": integration_id, "rid": restaurant_id},
        )
        row = result.first()
        if row is None:
            # Row exists but no credentials set yet — different from "no row
            # at all". Caller decides whether to 404 (no row) or 409 (no
            # credentials yet). get_integration() handles the 404 path.
            await self.get_integration(restaurant_id, integration_id)
            return None
        return str(row[0])

    async def get_webhook_signing_key(
        self, restaurant_id: UUID, integration_id: UUID
    ) -> str | None:
        """Return the decrypted webhook signing key or None if not set."""
        key = self._require_key()
        result = await self._session.execute(
            text(
                "SELECT pgp_sym_decrypt(webhook_signing_key_encrypted, :key)::text "
                "FROM pos_integrations "
                "WHERE id = :id "
                "AND restaurant_id = :rid "
                "AND webhook_signing_key_encrypted IS NOT NULL"
            ),
            {"key": key, "id": integration_id, "rid": restaurant_id},
        )
        row = result.first()
        if row is None:
            await self.get_integration(restaurant_id, integration_id)
            return None
        return str(row[0])
