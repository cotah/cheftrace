"""POS integration endpoints.

All endpoints here are owner-only via MANAGE_POS_INTEGRATIONS. Webhook
ingestion lives separately in Part 2/4 — it has its own permission
model (public + HMAC signature, no JWT).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_session, require_permission
from app.core.config import settings
from app.core.permissions import Permission
from app.models.membership import RestaurantMembership
from app.schemas.pos import (
    POSIntegrationCreate,
    POSIntegrationRead,
    POSIntegrationSetCredentials,
    POSIntegrationUpdate,
    POSItemMappingCreate,
    POSItemMappingRead,
    POSItemMappingUpdate,
)
from app.services.pos_integration_service import POSIntegrationService
from app.services.pos_mapping_service import POSItemMappingService

router = APIRouter(
    prefix="/restaurants/{restaurant_id}/pos/integrations",
    tags=["pos"],
)


def _service(session: AsyncSession) -> POSIntegrationService:
    # Encryption key is read once per request from settings. Callable paths
    # that don't touch credentials still work when the key is unset.
    return POSIntegrationService(session, settings.pos_encryption_key)


@router.get("", response_model=list[POSIntegrationRead])
async def list_pos_integrations(
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_POS_INTEGRATIONS)
    ),
    session: AsyncSession = Depends(get_session),
) -> list[POSIntegrationRead]:
    svc = _service(session)
    rows = await svc.list_integrations(membership.restaurant_id)
    return [POSIntegrationRead.from_model(r) for r in rows]


@router.post("", response_model=POSIntegrationRead, status_code=201)
async def create_pos_integration(
    data: POSIntegrationCreate,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_POS_INTEGRATIONS)
    ),
    session: AsyncSession = Depends(get_session),
) -> POSIntegrationRead:
    svc = _service(session)
    row = await svc.create_integration(
        restaurant_id=membership.restaurant_id,
        provider=data.provider,
        name=data.name,
        external_location_id=data.external_location_id,
        created_by_user_id=membership.user_id,
    )
    return POSIntegrationRead.from_model(row)


@router.get("/{integration_id}", response_model=POSIntegrationRead)
async def get_pos_integration(
    integration_id: UUID,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_POS_INTEGRATIONS)
    ),
    session: AsyncSession = Depends(get_session),
) -> POSIntegrationRead:
    svc = _service(session)
    row = await svc.get_integration(membership.restaurant_id, integration_id)
    return POSIntegrationRead.from_model(row)


@router.put("/{integration_id}", response_model=POSIntegrationRead)
async def update_pos_integration(
    integration_id: UUID,
    data: POSIntegrationUpdate,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_POS_INTEGRATIONS)
    ),
    session: AsyncSession = Depends(get_session),
) -> POSIntegrationRead:
    svc = _service(session)
    row = await svc.update_integration(
        restaurant_id=membership.restaurant_id,
        integration_id=integration_id,
        name=data.name,
        external_location_id=data.external_location_id,
        confirmation_mode=data.confirmation_mode,
        is_active=data.is_active,
    )
    return POSIntegrationRead.from_model(row)


@router.delete("/{integration_id}", status_code=204)
async def delete_pos_integration(
    integration_id: UUID,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_POS_INTEGRATIONS)
    ),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Soft delete — sets is_active=false, preserves audit and event history."""
    svc = _service(session)
    await svc.soft_delete(membership.restaurant_id, integration_id)
    return Response(status_code=204)


@router.put("/{integration_id}/credentials", response_model=POSIntegrationRead)
async def set_pos_credentials(
    integration_id: UUID,
    data: POSIntegrationSetCredentials,
    membership: RestaurantMembership = Depends(
        require_permission(Permission.MANAGE_POS_INTEGRATIONS)
    ),
    session: AsyncSession = Depends(get_session),
) -> POSIntegrationRead:
    """Encrypt and persist the access token + webhook signing key.

    Both values are required together — they're meaningless individually.
    The response never echoes them back; only `has_access_token` and
    `has_webhook_signing_key` flip to True.
    """
    svc = _service(session)
    row = await svc.set_credentials(
        restaurant_id=membership.restaurant_id,
        integration_id=integration_id,
        access_token=data.access_token,
        webhook_signing_key=data.webhook_signing_key,
    )
    return POSIntegrationRead.from_model(row)


# --- item mappings (nested under integration) --- #
#
# Owner-only would prevent managers from fixing a mistyped mapping in
# the middle of service — MANAGE_STOCK lets manager and chef adjust
# mappings without giving them credential / mode control.


@router.get(
    "/{integration_id}/mappings",
    response_model=list[POSItemMappingRead],
)
async def list_pos_mappings(
    integration_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> list[POSItemMappingRead]:
    svc = POSItemMappingService(session)
    rows = await svc.list_mappings(membership.restaurant_id, integration_id)
    return [POSItemMappingRead.from_model(r) for r in rows]


@router.post(
    "/{integration_id}/mappings",
    response_model=POSItemMappingRead,
    status_code=201,
)
async def create_pos_mapping(
    integration_id: UUID,
    data: POSItemMappingCreate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> POSItemMappingRead:
    svc = POSItemMappingService(session)
    row = await svc.create_mapping(
        restaurant_id=membership.restaurant_id,
        integration_id=integration_id,
        external_item_id=data.external_item_id,
        external_item_name_snapshot=data.external_item_name_snapshot,
        recipe_id=data.recipe_id,
        units_per_sale=data.units_per_sale,
    )
    return POSItemMappingRead.from_model(row)


@router.put(
    "/{integration_id}/mappings/{mapping_id}",
    response_model=POSItemMappingRead,
)
async def update_pos_mapping(
    integration_id: UUID,
    mapping_id: UUID,
    data: POSItemMappingUpdate,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> POSItemMappingRead:
    """Partial update.

    `exclude_unset=True` is what lets the caller flip recipe_id to NULL
    explicitly (ignore-state) without that being indistinguishable from
    "leave it alone". Pydantic v2 default None is ambiguous otherwise.
    """
    svc = POSItemMappingService(session)
    update_fields = data.model_dump(exclude_unset=True)
    row = await svc.update_mapping(
        restaurant_id=membership.restaurant_id,
        integration_id=integration_id,
        mapping_id=mapping_id,
        update=update_fields,
    )
    return POSItemMappingRead.from_model(row)


@router.delete(
    "/{integration_id}/mappings/{mapping_id}",
    status_code=204,
)
async def delete_pos_mapping(
    integration_id: UUID,
    mapping_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Soft delete (is_active=False). Past pos_events keep their FK
    integrity and the audit trail."""
    svc = POSItemMappingService(session)
    await svc.delete_mapping(membership.restaurant_id, integration_id, mapping_id)
    return Response(status_code=204)
