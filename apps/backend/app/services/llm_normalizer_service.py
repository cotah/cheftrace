"""LLM normalizer — fuzzy match OCR-extracted line items to existing products.

The OCR layer returns raw vendor strings ("Tomates Cherry 500g" or
"CHKN BREAST 1KG"). This service maps each raw_text to the best matching
active product for the given restaurant, using rapidfuzz token-based
ratios. Match decisions are *suggestions* only — the human review step
in /process → /confirm is what creates StockLots.

Match algorithm:
  1. Lowercase + strip accents + collapse whitespace.
  2. Use fuzz.WRatio (handles short / long string mismatches well).
  3. Anything below settings.ocr_match_threshold (default 70) → no match.

The service is multi-tenant: it never reads products outside the supplied
restaurant_id.
"""

import unicodedata
from dataclasses import dataclass
from uuid import UUID

from rapidfuzz import fuzz, process
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.integrations.ocr.base import ExtractedLineItem
from app.models.product import Product


@dataclass(frozen=True)
class MatchResult:
    """Result of matching a single line item against the product catalogue."""

    line: ExtractedLineItem
    suggested_product_id: UUID | None
    score: float


def normalize_name(s: str) -> str:
    """Lowercase + strip diacritics + collapse internal whitespace."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(no_accents.lower().split())


class LLMNormalizerService:
    """Map OCR-extracted line items to existing products via fuzzy matching."""

    def __init__(self, session: AsyncSession, threshold: float | None = None) -> None:
        self._session = session
        self._threshold = threshold if threshold is not None else settings.ocr_match_threshold

    async def _load_products(self, restaurant_id: UUID) -> list[Product]:
        """Return active products for the restaurant."""
        result = await self._session.exec(
            select(Product)
            .where(Product.restaurant_id == restaurant_id)
            .where(Product.is_active == True)  # noqa: E712 — SQLModel needs == True
        )
        return list(result.all())

    def _best_match(self, query: str, choices: dict[str, UUID]) -> tuple[UUID | None, float]:
        """Return the best (product_id, score) for query against choices, or
        (None, 0) when below threshold or no choices."""
        if not query or not choices:
            return None, 0.0
        match = process.extractOne(query, list(choices.keys()), scorer=fuzz.WRatio)
        if not match:
            return None, 0.0
        name, score, _idx = match
        if score < self._threshold:
            return None, float(score)
        return choices[name], float(score)

    async def match_line_items(
        self, restaurant_id: UUID, items: list[ExtractedLineItem]
    ) -> list[MatchResult]:
        """For each line item, suggest a product id (or None) plus the score.

        - Empty or whitespace-only raw_text → None.
        - No active products in catalogue → all None.
        - Score below threshold → None (score still returned for telemetry).
        """
        products = await self._load_products(restaurant_id)
        # Build choices keyed on the *normalized* product name so that
        # accents and case never affect ranking. If two products normalise
        # to the same key, last one wins — acceptable for MVP.
        choices: dict[str, UUID] = {}
        for p in products:
            key = normalize_name(p.name)
            if key and p.id is not None:
                choices[key] = p.id

        results: list[MatchResult] = []
        for item in items:
            raw = (item.raw_text or "").strip()
            if not raw:
                results.append(MatchResult(line=item, suggested_product_id=None, score=0.0))
                continue
            query = normalize_name(raw)
            pid, score = self._best_match(query, choices)
            results.append(MatchResult(line=item, suggested_product_id=pid, score=score))
        return results
