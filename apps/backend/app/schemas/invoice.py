from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class InvoiceUploadRequest(BaseModel):
    """Initiated by frontend; backend creates invoice row + signed upload URL."""

    filename: str
    mime_type: str = "application/pdf"


class InvoiceUploadResponse(BaseModel):
    invoice_id: UUID
    upload_url: str
    file_path: str
    expires_in: int = 300


class InvoiceLineItemRead(BaseModel):
    id: UUID
    invoice_id: UUID
    line_number: int
    raw_text: str | None = None
    suggested_product_id: UUID | None = None
    confirmed_product_id: UUID | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    expiry_date: date | None = None
    batch_code: str | None = None
    status: str
    notes: str | None = None

    model_config = {"from_attributes": True}


class InvoiceRead(BaseModel):
    id: UUID
    restaurant_id: UUID
    supplier_id: UUID | None = None
    file_path: str
    status: str
    uploaded_by_user_id: UUID
    processed_at: datetime | None = None
    confirmed_at: datetime | None = None
    supplier_name_raw: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    total_amount: Decimal | None = None
    vat_amount: Decimal | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvoiceWithItemsRead(InvoiceRead):
    items: list[InvoiceLineItemRead] = []
    raw_ocr_json: dict[str, Any] | None = None
    download_url: str | None = None
