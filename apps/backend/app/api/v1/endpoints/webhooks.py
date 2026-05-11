"""Public webhook endpoints (no JWT — auth is per-provider).

Currently hosts POS webhooks only. The router prefix `/webhooks` is
intentionally outside the `/restaurants/{rid}` tree because external
providers don't know about our tenancy — they post to one URL and we
route to the right tenant via the location_id in the payload.
"""

from fastapi import APIRouter, Depends, Path, Request, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_session
from app.services.pos_webhook_service import (
    process_pos_webhook,
    status_code_for,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/pos/{provider}")
async def receive_pos_webhook(
    request: Request,
    provider: str = Path(..., description="POS provider key, e.g. 'square'"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Single entry point for every POS provider's webhook.

    Body is read once as raw bytes (HMAC needs the exact bytes Square
    signed; re-serialising after json.loads would change whitespace and
    break verification). Authentication is the HMAC signature on the
    body — we never trust the path, the headers, or anything else.
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
    return Response(status_code=status_code_for(result.outcome))
