"""OCR provider abstraction.

The Pydantic schemas below define the structured output contract that
every provider (Gemini, Fake, future Document AI/AWS Textract, etc.)
must satisfy. Business code only depends on these types — never on any
concrete provider directly.
"""

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class ExtractedLineItem(BaseModel):
    line_number: int
    raw_text: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None


class ExtractedInvoice(BaseModel):
    supplier_name: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    total_amount: Decimal | None = None
    vat_amount: Decimal | None = None
    line_items: list[ExtractedLineItem] = []
    raw: dict[str, Any] = {}


class OCRProvider(ABC):
    """Read an invoice file (PDF or image) and return structured data."""

    @abstractmethod
    async def extract(self, file_url: str) -> ExtractedInvoice:
        """Download the file at file_url and extract its contents."""
