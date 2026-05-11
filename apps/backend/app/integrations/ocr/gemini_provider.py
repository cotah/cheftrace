"""Gemini 2.5 Flash OCR provider.

Uses the google-genai async client with structured-output (response_schema)
so the model is forced to return an ExtractedInvoice-shaped JSON. The
download URL is fetched via httpx (Supabase signed URL points to the
private bucket; bytes are sent inline to Gemini).
"""

import logging
from typing import Any

import httpx
from pydantic import BaseModel

from app.integrations.ocr.base import ExtractedInvoice, ExtractedLineItem, OCRProvider

logger = logging.getLogger(__name__)


_PROMPT = (
    "You are an invoice data extraction system for a restaurant procurement app. "
    "Read the attached invoice (PDF or image) and extract the structured fields. "
    "Rules:\n"
    "- supplier_name: the supplier's company name as printed.\n"
    "- invoice_number: the invoice's reference / number / id.\n"
    "- invoice_date: ISO date (YYYY-MM-DD). Convert if printed in another format.\n"
    "- total_amount and vat_amount: decimal numbers, no currency symbol.\n"
    "- For each line item, set raw_text to the verbatim product description as printed, "
    "set quantity, unit (e.g. 'kg', 'l', 'unit'), unit_cost and total_cost when visible.\n"
    "- line_number starts at 1 and follows the order printed on the invoice.\n"
    "- If a field is not visible or you are not confident, leave it null. "
    "Do NOT invent values."
)


class _GeminiLineItem(BaseModel):
    """Mirror of ExtractedLineItem with Decimal->float for Gemini schema compatibility."""

    line_number: int
    raw_text: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_cost: float | None = None
    total_cost: float | None = None


class _GeminiInvoice(BaseModel):
    supplier_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None  # ISO YYYY-MM-DD; parsed in adapter
    total_amount: float | None = None
    vat_amount: float | None = None
    line_items: list[_GeminiLineItem] = []


class GeminiOCRProvider(OCRProvider):
    """Real OCR via google-genai SDK. Lazy-imports SDK so test envs without
    GEMINI_API_KEY can import the module freely."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        http_timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._http_timeout = http_timeout

    async def extract(self, file_url: str) -> ExtractedInvoice:
        file_bytes, mime_type = await self._download(file_url)

        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_GeminiInvoice,
            temperature=0.0,
        )
        contents: list[Any] = [
            _PROMPT,
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
        ]

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        text = response.text or ""
        parsed = _GeminiInvoice.model_validate_json(text)
        return _to_extracted_invoice(parsed, raw_text=text)

    async def _download(self, file_url: str) -> tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            resp = await client.get(file_url)
            resp.raise_for_status()
            mime_type = resp.headers.get("content-type", "application/pdf")
            if ";" in mime_type:
                mime_type = mime_type.split(";", 1)[0].strip()
            return resp.content, mime_type


def _to_extracted_invoice(parsed: _GeminiInvoice, raw_text: str) -> ExtractedInvoice:
    """Convert Gemini-friendly schema back to internal ExtractedInvoice."""
    from datetime import date as _date
    from decimal import Decimal

    inv_date: _date | None = None
    if parsed.invoice_date:
        try:
            inv_date = _date.fromisoformat(parsed.invoice_date)
        except ValueError:
            logger.warning("Invalid invoice_date from Gemini: %s", parsed.invoice_date)
            inv_date = None

    def _dec(v: float | None) -> Decimal | None:
        if v is None:
            return None
        return Decimal(str(v))

    return ExtractedInvoice(
        supplier_name=parsed.supplier_name,
        invoice_number=parsed.invoice_number,
        invoice_date=inv_date,
        total_amount=_dec(parsed.total_amount),
        vat_amount=_dec(parsed.vat_amount),
        line_items=[
            ExtractedLineItem(
                line_number=li.line_number,
                raw_text=li.raw_text,
                quantity=_dec(li.quantity),
                unit=li.unit,
                unit_cost=_dec(li.unit_cost),
                total_cost=_dec(li.total_cost),
            )
            for li in parsed.line_items
        ],
        raw={"provider": "gemini", "response_text": raw_text},
    )
