"""Invoice endpoints — upload + list + detail + process.

Phase 2 Sprint 5: file storage + invoice metadata.
Phase 2 Sprint 6: /process endpoint runs OCR + product matching and
moves the invoice to needs_review. /confirm (Sprint 7) creates StockLots.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentMembership, get_session, require_permission
from app.core.config import settings
from app.core.exceptions import ChefTraceError, ConflictError, NotFoundError
from app.core.permissions import Permission
from app.integrations.ocr.base import OCRProvider
from app.integrations.providers import get_ocr_provider, get_storage_provider
from app.integrations.storage.base import StorageProvider
from app.models.enums import MovementSource
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.membership import RestaurantMembership
from app.models.product import Product
from app.schemas.invoice import (
    InvoiceConfirmRequest,
    InvoiceLineItemRead,
    InvoiceRead,
    InvoiceUploadRequest,
    InvoiceUploadResponse,
    InvoiceWithItemsRead,
)
from app.services.llm_normalizer_service import LLMNormalizerService
from app.services.stock_service import StockService

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


class _BadConfirmRequestError(ChefTraceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


@router.post("/{invoice_id}/confirm", response_model=InvoiceWithItemsRead)
async def confirm_invoice(
    invoice_id: UUID,
    body: InvoiceConfirmRequest,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    session: AsyncSession = Depends(get_session),
) -> InvoiceWithItemsRead:
    """
    Apply human-reviewed decisions to an invoice in 'needs_review' status.

    For every confirmed line item, a StockLot is created via
    StockService.receive(source=OCR). Rejected lines are just marked.
    The whole flow runs in a single transaction — if any receive fails
    the invoice and all line items remain untouched (rollback) and a 400
    is returned, so the user can edit and retry.

    The frontend must send exactly one decision per line item belonging
    to this invoice; missing or unknown ids return 400.
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
    if invoice.status != "needs_review":
        raise ConflictError(
            f"Invoice cannot be confirmed in status '{invoice.status}'. "
            "Only 'needs_review' invoices can be confirmed."
        )

    items_result = await session.exec(
        select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice_id)
    )
    line_items_by_id = {li.id: li for li in items_result.all()}

    # All decisions must belong to this invoice's line items.
    decision_ids = {d.line_item_id for d in body.items}
    unknown = decision_ids - set(line_items_by_id.keys())
    if unknown:
        raise _BadConfirmRequestError(
            f"Unknown line_item_id(s) for invoice {invoice_id}: {sorted(map(str, unknown))}"
        )
    missing = set(line_items_by_id.keys()) - decision_ids
    if missing:
        raise _BadConfirmRequestError(
            f"All invoice line items must have a decision. Missing: {sorted(map(str, missing))}"
        )

    # Pre-validate that every confirmed product belongs to this restaurant.
    confirmed_decisions = [d for d in body.items if d.action == "confirm"]
    product_ids = {d.confirmed_product_id for d in confirmed_decisions if d.confirmed_product_id}
    if product_ids:
        prod_result = await session.exec(
            select(Product).where(
                Product.restaurant_id == membership.restaurant_id,
                Product.id.in_(product_ids),  # type: ignore[attr-defined]
            )
        )
        valid = {p.id for p in prod_result.all()}
        bad = product_ids - valid
        if bad:
            raise _BadConfirmRequestError(
                f"Unknown or cross-tenant product id(s): {sorted(map(str, bad))}"
            )

    stock = StockService(session)
    try:
        for decision in body.items:
            line = line_items_by_id[decision.line_item_id]
            if decision.action == "reject":
                line.status = "rejected"
                line.notes = decision.notes or line.notes
                session.add(line)
                continue

            assert decision.confirmed_product_id is not None  # guarded by schema
            assert decision.quantity is not None
            assert decision.unit is not None

            await stock.receive(
                restaurant_id=membership.restaurant_id,
                product_id=decision.confirmed_product_id,
                supplier_id=invoice.supplier_id,
                quantity=decision.quantity,
                unit=decision.unit,
                created_by_user_id=membership.user_id,
                unit_cost=decision.unit_cost,
                expiry_date=decision.expiry_date,
                notes=decision.notes,
                source=MovementSource.OCR,
            )

            line.status = "confirmed"
            line.confirmed_product_id = decision.confirmed_product_id
            line.quantity = decision.quantity
            line.unit = decision.unit
            line.unit_cost = decision.unit_cost
            line.expiry_date = decision.expiry_date
            line.batch_code = decision.batch_code or line.batch_code
            line.notes = decision.notes or line.notes
            session.add(line)

        invoice.status = "confirmed"
        invoice.confirmed_at = _utc_naive_now()
        session.add(invoice)
        await session.commit()
    except ChefTraceError:
        await session.rollback()
        raise
    except Exception as exc:
        logger.exception("Invoice confirmation failed for %s", invoice_id)
        await session.rollback()
        raise _BadConfirmRequestError(f"Confirmation failed: {exc}") from exc

    await session.refresh(invoice)
    items_after = await session.exec(
        select(InvoiceLineItem)
        .where(InvoiceLineItem.invoice_id == invoice_id)
        .order_by(InvoiceLineItem.line_number.asc())  # type: ignore[attr-defined]
    )
    items_list = list(items_after.all())
    base = InvoiceRead.model_validate(invoice).model_dump()
    return InvoiceWithItemsRead(
        **base,
        items=[InvoiceLineItemRead.model_validate(it) for it in items_list],
        raw_ocr_json=invoice.raw_ocr_json,
        download_url=None,
    )


_DELETABLE_STATUSES = ("uploaded", "needs_review")


@router.delete("/{invoice_id}", status_code=204)
async def delete_invoice(
    invoice_id: UUID,
    membership: RestaurantMembership = Depends(require_permission(Permission.MANAGE_STOCK)),
    storage: StorageProvider = Depends(get_storage_provider),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """
    Delete an invoice and its line items.

    Confirmed invoices (and rejected ones) are immutable audit records and
    cannot be deleted (409). Uploaded and needs_review invoices can be
    removed because they have not been turned into stock yet.

    Storage deletion is best-effort: if the object is already gone or the
    Storage API is briefly unavailable, the DB row is still removed so
    the user is not stuck with an undeletable invoice. The orphan file
    (if any) wastes a few KB on Storage; that is preferable to a stuck
    record pointing at it.
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
    if invoice.status not in _DELETABLE_STATUSES:
        raise ConflictError(
            f"Invoice cannot be deleted in status '{invoice.status}'. "
            "Only 'uploaded' or 'needs_review' invoices can be deleted."
        )

    file_path = invoice.file_path

    # App-level cascade: delete child line items in the same transaction
    # as the parent. The FK has no ON DELETE CASCADE so this must be
    # explicit. Anything that goes wrong here rolls back the invoice too.
    items = (
        await session.exec(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice_id))
    ).all()
    for li in items:
        await session.delete(li)
    # Flush so the child DELETEs hit the DB before the parent DELETE —
    # the FK has no ON DELETE CASCADE, so order matters.
    await session.flush()
    await session.delete(invoice)
    await session.commit()

    try:
        await storage.delete_object(bucket=settings.invoices_bucket, path=file_path)
    except Exception as exc:
        # Best-effort: log and continue. The DB row is already gone.
        logger.warning(
            "Storage delete failed for invoice %s (path=%s); object may be orphaned: %s",
            invoice_id,
            file_path,
            exc,
        )

    return Response(status_code=204)
