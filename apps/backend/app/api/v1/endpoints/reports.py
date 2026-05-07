"""HACCP PDF report endpoints."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_session, require_permission
from app.core.permissions import Permission
from app.models.membership import RestaurantMembership
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/restaurants/{restaurant_id}/reports", tags=["reports"])


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/temperature-log.pdf")
async def temperature_log_pdf(
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    equipment_id: UUID | None = None,
    membership: RestaurantMembership = Depends(require_permission(Permission.EXPORT_HACCP_PDF)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    svc = PDFService(session)
    pdf_bytes = await svc.generate_temperature_log(
        restaurant_id=membership.restaurant_id,
        date_from=date_from,
        date_to=date_to,
        equipment_id=equipment_id,
    )
    filename = f"temperature-log-{date_from}-to-{date_to}.pdf"
    return _pdf_response(pdf_bytes, filename)


@router.get("/daily-checklist.pdf")
async def daily_checklist_pdf(
    run_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.EXPORT_HACCP_PDF)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    svc = PDFService(session)
    pdf_bytes = await svc.generate_daily_checklist(
        restaurant_id=membership.restaurant_id,
        run_id=run_id,
    )
    filename = f"checklist-{run_id}.pdf"
    return _pdf_response(pdf_bytes, filename)


@router.get("/monthly-haccp.pdf")
async def monthly_haccp_pdf(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    membership: RestaurantMembership = Depends(require_permission(Permission.EXPORT_HACCP_PDF)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    svc = PDFService(session)
    pdf_bytes = await svc.generate_monthly_haccp_summary(
        restaurant_id=membership.restaurant_id,
        year=year,
        month=month,
    )
    filename = f"haccp-summary-{year}-{month:02d}.pdf"
    return _pdf_response(pdf_bytes, filename)
