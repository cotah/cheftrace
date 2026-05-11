"""Public webhook endpoints (no JWT — auth is per-provider).

Currently hosts POS webhooks only. The router prefix `/webhooks` is
intentionally outside the `/restaurants/{rid}` tree because external
providers don't know about our tenancy — they post to one URL and we
route to the right tenant via the location_id in the payload.
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Request, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_session
from app.services.pos_webhook_service import (
    WebhookOutcome,
    process_pos_webhook,
    run_processor_in_background,
    status_code_for,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/pos/{provider}")
async def receive_pos_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    provider: str = Path(..., description="POS provider key, e.g. 'square'"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Single entry point for every POS provider's webhook.

    Body is read once as raw bytes (HMAC needs the exact bytes Square
    signed; re-serialising after json.loads would change whitespace and
    break verification). Authentication is the HMAC signature on the
    body — we never trust the path, the headers, or anything else.

    On ACCEPTED, a BackgroundTask is queued to run the processor (Part
    3/4) right after the response is sent. The processor itself decides
    based on `confirmation_mode`: auto deducts, manual parks at
    `pending_approval`. Replay events are skipped — either they were
    already auto-processed on the first delivery (terminal status, no
    work) or the operator already handled them via the UI.
    """
    raw_body = await request.body()
    # Square uses `x-square-hmacsha256-signature`. Other providers will
    # have their own header; the adapter knows which one to pick. For
    # now Square is the only provider so we read its header here; when
    # a second provider lands, push this lookup into the adapter.
    signature_header = request.headers.get("x-square-hmacsha256-signature", "")

    result = await process_pos_webhook(
        session=session,
        provider=provider,
        raw_body=raw_body,
        signature_header=signature_header,
    )

    if (
        result.outcome == WebhookOutcome.ACCEPTED
        and result.pos_event_id
        and result.restaurant_id is not None
        and result.user_id_for_processing is not None
    ):
        background_tasks.add_task(
            run_processor_in_background,
            UUID(result.pos_event_id),
            result.restaurant_id,
            result.user_id_for_processing,
        )

    return Response(status_code=status_code_for(result.outcome))
