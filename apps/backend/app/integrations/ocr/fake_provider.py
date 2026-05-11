"""In-memory fake OCR provider for tests and local development.

Returns a fixed canned invoice when no override is set, or whatever the
test injects via `set_response`. Records every file_url it was asked
to extract.
"""

from datetime import date
from decimal import Decimal

from app.integrations.ocr.base import ExtractedInvoice, ExtractedLineItem, OCRProvider

_DEFAULT_RESPONSE = ExtractedInvoice(
    supplier_name="Fresh Foods Ltd",
    invoice_number="INV-2026-001",
    invoice_date=date(2026, 5, 11),
    total_amount=Decimal("123.45"),
    vat_amount=Decimal("28.39"),
    line_items=[
        ExtractedLineItem(
            line_number=1,
            raw_text="Tomatoes Cherry 500g",
            quantity=Decimal("2.000"),
            unit="kg",
            unit_cost=Decimal("3.5000"),
            total_cost=Decimal("7.00"),
        ),
        ExtractedLineItem(
            line_number=2,
            raw_text="Chicken Breast Fillet 1kg",
            quantity=Decimal("5.000"),
            unit="kg",
            unit_cost=Decimal("12.5000"),
            total_cost=Decimal("62.50"),
        ),
    ],
    raw={"provider": "fake"},
)


class FakeOCRProvider(OCRProvider):
    def __init__(self, response: ExtractedInvoice | None = None) -> None:
        self._response = response or _DEFAULT_RESPONSE
        self.calls: list[str] = []

    def set_response(self, response: ExtractedInvoice) -> None:
        self._response = response

    async def extract(self, file_url: str) -> ExtractedInvoice:
        self.calls.append(file_url)
        return self._response
