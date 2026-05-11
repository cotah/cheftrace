"""POS event queue + processing endpoints.

Owner-only setup of integrations lives in `pos.py`. This module hosts
the day-to-day actions any operational role (owner / manager / chef)
performs on incoming events: list, inspect, approve, retry, dismiss.

Trigger model
- Webhook ingress (Part 2/4) deposits events in `pending`. The auto-
  vs-manual gate is decided when an event is processed, not when it's
  received — so receiving is fast and processing is a separate step.
- Part 3/4 does not auto-trigger processing yet. Operators hit
  `POST /process` from the UI (Part 4/4) or curl. `force=True` is
  what the "Approve" button on a `pending_approval` event sends.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_session, require_permission
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.integrations.pos.registry import get_pos_adapter
from app.models.membership import RestaurantMembership
from app.models.pos_event import PosEvent
from app.schemas.pos import (
    POSEventDetail,
    POSEventDismissRequest,
    POSEventProcessResponse,
    POSEventRead,
)
from app.services.pos_event_processor_service import POSEventProcessorService

router = APIRouter(
    prefix="/restaurants/{restaurant_id}/pos/events",
    tags=["pos"],
)


def _processor(session: AsyncSession) -> POSEventProcessorService:
    return POSEventProcessorService(
        session=session,
        encryption_key=settings.pos_encryption_key,
        adapter_factory=get_pos_adapter,
    )


@router.get("", response_model=list[POSEventRead])
async def list_pos_events(
    status: (
        Literal[
            "pending",
            "needs_mapping",
            "pending_approval",
            "processed",
            "insufficient_stock",
            "failed",
            "ignored",
        ]
        | None
    ) = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> list[POSEventRead]:
    """Most recent events first. Use `status` to filter the queue UI."""
    query = select(PosEvent).where(PosEvent.restaurant_id == membership.restaurant_id)
    if status:
        query = query.where(PosEvent.processing_status == status)
    query = query.order_by(PosEvent.received_at.desc()).limit(limit)  # type: ignore[attr-defined]
    result = await session.exec(query)
    return [POSEventRead.from_model(r) for r in result.all()]


@router.get("/{event_id}", response_model=POSEventDetail)
async def get_pos_event(
    event_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> POSEventDetail:
    result = await session.exec(
        select(PosEvent).where(
            PosEvent.id == event_id,
            PosEvent.restaurant_id == membership.restaurant_id,
        )
    )
    event = result.first()
    if event is None:
        raise NotFoundError("PosEvent")
    return POSEventDetail.from_model(event)


@router.post("/{event_id}/process", response_model=POSEventProcessResponse)
async def process_pos_event(
    event_id: UUID,
    force: bool = Query(
        default=False,
        description=(
            "True bypasses the manual-mode gate. The UI sends this from "
            "the Approve button on a pending_approval event."
        ),
    ),
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> POSEventProcessResponse:
    """Enrich + map + deduct in one call. Idempotent — terminal
    statuses (processed, ignored) return the current state without
    re-deducting.
    """
    proc = _processor(session)
    result = await proc.process_event(
        restaurant_id=membership.restaurant_id,
        event_id=event_id,
        user_id=membership.user_id,
        force=force,
    )
    return POSEventProcessResponse(
        status=result.status.value,
        movements_created=result.movements_created,
        error_message=result.error_message,
        unmapped_item_ids=result.unmapped_item_ids,
        insufficient_product_ids=result.insufficient_product_ids,
    )


@router.post("/{event_id}/dismiss", response_model=POSEventProcessResponse)
async def dismiss_pos_event(
    event_id: UUID,
    data: POSEventDismissRequest,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> POSEventProcessResponse:
    """Mark the event as IGNORED with a reason. Used for events that
    shouldn't move stock (test events, comp orders, etc.).
    """
    proc = _processor(session)
    result = await proc.dismiss_event(
        restaurant_id=membership.restaurant_id,
        event_id=event_id,
        user_id=membership.user_id,
        reason=data.reason,
    )
    return POSEventProcessResponse(
        status=result.status.value,
        movements_created=result.movements_created,
        error_message=result.error_message,
    )
