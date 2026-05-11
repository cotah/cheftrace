"""Invoice endpoints — upload + list + detail.

Phase 2 Sprint 5 baseline: file storage + invoice metadata. OCR processing
and confirmation are added in Sprint 6 / Sprint 7.
"""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.integrations.providers import get_storage_provider
from app.integrations.storage.base import StorageProvider
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.membership import RestaurantMembership
from app.schemas.invoice import (
    InvoiceLineItemRead,
    InvoiceRead,
    InvoiceUploadRequest,
    InvoiceUploadResponse,
    InvoiceWithItemsRead,
)

router = APIRouter(prefix="/restaurants/{restaurant_id}/invoices", tags=["invoices"])


_MIME_EXT = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _ext_for(mime_type: str) -> str:
    return _MIME_EXT.get(mime_type.lower(), "bin")


@router.post("/upload-url", response_model=InvoiceUploadResponse, status_code=201)
async def create_invoice_upload_url(
    data: InvoiceUploadRequest,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    storage: StorageProvider = Depends(get_storage_provider),
    session: AsyncSession = Depends(get_session),
) -> InvoiceUploadResponse:
    """
    Create an Invoice row in 'uploaded' status and return a pre-signed URL
    the frontend can PUT the file bytes to. Path layout: {restaurant_id}/{invoice_id}.{ext}
    """
    invoice_id = uuid4()
    ext = _ext_for(data.mime_type)
    file_path = f"{membership.restaurant_id}/{invoice_id}.{ext}"

    invoice = Invoice(
        id=invoice_id,
        restaurant_id=membership.restaurant_id,
        file_path=file_path,
        status="uploaded",
        uploaded_by_user_id=membership.user_id,
    )
    session.add(invoice)
    await session.commit()

    upload_url = await storage.generate_upload_url(
        bucket=settings.invoices_bucket, path=file_path, expires_in=300
    )

    return InvoiceUploadResponse(
        invoice_id=invoice_id,
        upload_url=upload_url,
        file_path=file_path,
        expires_in=300,
    )


@router.get("", response_model=list[InvoiceRead])
async def list_invoices(
    membership: CurrentMembership,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[Invoice]:
    query = select(Invoice).where(Invoice.restaurant_id == membership.restaurant_id)
    if status:
        query = query.where(Invoice.status == status)
    query = query.order_by(Invoice.created_at.desc()).limit(200)  # type: ignore[attr-defined]
    result = await session.exec(query)
    return list(result.all())


@router.get("/{invoice_id}", response_model=InvoiceWithItemsRead)
async def get_invoice(
    invoice_id: UUID,
    membership: CurrentMembership,
    storage: StorageProvider = Depends(get_storage_provider),
    session: AsyncSession = Depends(get_session),
) -> InvoiceWithItemsRead:
    inv_result = await session.exec(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.restaurant_id == membership.restaurant_id,
        )
    )
    invoice = inv_result.first()
    if not invoice:
        raise NotFoundError("Invoice")

    items_result = await session.exec(
        select(InvoiceLineItem)
        .where(InvoiceLineItem.invoice_id == invoice_id)
        .order_by(InvoiceLineItem.line_number.asc())  # type: ignore[attr-defined]
    )
    items = list(items_result.all())

    download_url: str | None = None
    try:
        download_url = await storage.generate_download_url(
            bucket=settings.invoices_bucket, path=invoice.file_path, expires_in=300
        )
    except Exception:
        # Storage may be unavailable in non-prod. Detail still returned.
        download_url = None

    base = InvoiceRead.model_validate(invoice).model_dump()
    return InvoiceWithItemsRead(
        **base,
        items=[InvoiceLineItemRead.model_validate(it) for it in items],
        raw_ocr_json=invoice.raw_ocr_json,
        download_url=download_url,
    )
