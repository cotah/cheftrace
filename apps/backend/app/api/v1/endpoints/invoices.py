"""Invoice endpoints — upload + list + detail + process.

Phase 2 Sprint 5: file storage + invoice metadata.
Phase 2 Sprint 6: /process endpoint runs OCR + product matching and
moves the invoice to needs_review. /confirm (Sprint 7) creates StockLots.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.permissions import Permission
from app.integrations.ocr.base import OCRProvider
from app.integrations.providers import get_ocr_provider, get_storage_provider
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
from app.services.llm_normalizer_service import LLMNormalizerService

logger = logging.getLogger(__name__)

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


def _utc_naive_now() -> datetime:
    """The DB timestamp columns are TIMESTAMP WITHOUT TIME ZONE — strip tzinfo."""
    return datetime.now(UTC).replace(tzinfo=None)


@router.post("/{invoice_id}/process", response_model=InvoiceWithItemsRead)
async def process_invoice(
    invoice_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    storage: StorageProvider = Depends(get_storage_provider),
    ocr: OCRProvider = Depends(get_ocr_provider),
    session: AsyncSession = Depends(get_session),
) -> InvoiceWithItemsRead:
    """
    Run OCR + product matching on an uploaded invoice.

    Transitions: uploaded → processing → needs_review (success)
                                       → uploaded     (failure, with rollback)

    Only invoices in 'uploaded' status may be processed; anything else
    returns 409 to avoid double-processing or clobbering manual edits.
    """
    inv_result = await session.exec(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.restaurant_id == membership.restaurant_id,
        )
    )
    invoice = inv_result.first()
    if not invoice:
        raise NotFoundError("Invoice")
    if invoice.status != "uploaded":
        raise ConflictError(
            f"Invoice cannot be processed in status '{invoice.status}'. "
            "Only 'uploaded' invoices can be processed."
        )

    # Optimistic lock: mark as processing before the long-running OCR call,
    # so a concurrent /process request hits the 409 above.
    invoice.status = "processing"
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)

    try:
        download_url = await storage.generate_download_url(
            bucket=settings.invoices_bucket, path=invoice.file_path, expires_in=600
        )
        extracted = await ocr.extract(download_url)

        normalizer = LLMNormalizerService(session)
        matches = await normalizer.match_line_items(membership.restaurant_id, extracted.line_items)

        for match in matches:
            li = match.line
            session.add(
                InvoiceLineItem(
                    restaurant_id=membership.restaurant_id,
                    invoice_id=invoice.id,
                    line_number=li.line_number,
                    raw_text=li.raw_text,
                    suggested_product_id=match.suggested_product_id,
                    quantity=li.quantity,
                    unit=li.unit,
                    unit_cost=li.unit_cost,
                    total_cost=li.total_cost,
                    status="suggested",
                )
            )

        invoice.supplier_name_raw = extracted.supplier_name
        invoice.invoice_number = extracted.invoice_number
        invoice.invoice_date = extracted.invoice_date
        invoice.total_amount = extracted.total_amount
        invoice.vat_amount = extracted.vat_amount
        invoice.raw_ocr_json = extracted.raw or {}
        invoice.processed_at = _utc_naive_now()
        invoice.status = "needs_review"
        session.add(invoice)
        await session.commit()
    except Exception as exc:
        # Roll back the in-flight transaction (line items added to session),
        # then revert the invoice back to 'uploaded' in a fresh transaction
        # so the user can retry.
        logger.exception("OCR processing failed for invoice %s", invoice_id)
        await session.rollback()
        retry_result = await session.exec(select(Invoice).where(Invoice.id == invoice_id))
        retry = retry_result.first()
        if retry is not None:
            retry.status = "uploaded"
            session.add(retry)
            await session.commit()
        raise ConflictError(f"OCR processing failed: {exc}") from exc

    items_result = await session.exec(
        select(InvoiceLineItem)
        .where(InvoiceLineItem.invoice_id == invoice_id)
        .order_by(InvoiceLineItem.line_number.asc())  # type: ignore[attr-defined]
    )
    items = list(items_result.all())

    base = InvoiceRead.model_validate(invoice).model_dump()
    return InvoiceWithItemsRead(
        **base,
        items=[InvoiceLineItemRead.model_validate(it) for it in items],
        raw_ocr_json=invoice.raw_ocr_json,
        download_url=None,
    )
