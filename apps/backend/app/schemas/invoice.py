from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


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


class InvoiceConfirmLineItem(BaseModel):
    """One decision per OCR'd line item.

    action='confirm' creates a StockLot via StockService.receive — requires
    confirmed_product_id, quantity and unit. unit_cost / expiry_date / batch_code
    are optional (forwarded if present).

    action='reject' just marks the line item as rejected. No fields required
    beyond line_item_id.
    """

    line_item_id: UUID
    action: Literal["confirm", "reject"]
    confirmed_product_id: UUID | None = None
    quantity: Decimal | None = Field(default=None, ge=0)
    unit: str | None = None
    unit_cost: Decimal | None = Field(default=None, ge=0)
    expiry_date: date | None = None
    batch_code: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _require_fields_when_confirming(self) -> "InvoiceConfirmLineItem":
        if self.action == "confirm":
            missing: list[str] = []
            if self.confirmed_product_id is None:
                missing.append("confirmed_product_id")
            if self.quantity is None or self.quantity <= 0:
                missing.append("quantity (>0)")
            if not self.unit:
                missing.append("unit")
            if missing:
                raise ValueError(
                    f"action='confirm' requires {', '.join(missing)} for line {self.line_item_id}"
                )
        return self


class InvoiceConfirmRequest(BaseModel):
    """Bulk decisions for all OCR'd line items in an invoice."""

    items: list[InvoiceConfirmLineItem] = Field(..., min_length=1)
