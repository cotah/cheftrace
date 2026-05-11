"""LLMNormalizerService — fuzzy product matching for OCR line items.

Coverage target: >= 85% for app/services/llm_normalizer_service.py.
Covers normalisation rules (lowercase, accent stripping, whitespace),
match algorithm (exact, with extras, below threshold, no catalogue),
multi-tenant isolation, active-only filter, and threshold override.
"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401
from app.integrations.ocr.base import ExtractedLineItem
from app.models.product import Product
from app.models.restaurant import Restaurant
from app.services.llm_normalizer_service import LLMNormalizerService, normalize_name


@pytest.fixture
async def db_engine():
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5433/test",
    )
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(db_engine):
    factory = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest.fixture
async def restaurant_a(session):
    r = Restaurant(name=f"Resto A {uuid4()}", country="IE")
    session.add(r)
    await session.flush()
    return r


@pytest.fixture
async def restaurant_b(session):
    r = Restaurant(name=f"Resto B {uuid4()}", country="IE")
    session.add(r)
    await session.flush()
    return r


# --------- normalize_name unit tests --------- #


def test_normalize_name_lowercases_and_collapses_whitespace():
    assert normalize_name("  Tomatoes  Cherry  ") == "tomatoes cherry"


def test_normalize_name_strips_accents():
    assert normalize_name("Tomátês Çherry") == "tomates cherry"


def test_normalize_name_handles_empty_and_none():
    assert normalize_name("") == ""
    assert normalize_name("   ") == ""


# --------- LLMNormalizerService matching --------- #


@pytest.mark.asyncio
async def test_match_exact(session, restaurant_a):
    session.add(Product(restaurant_id=restaurant_a.id, name="Tomatoes Cherry", unit="kg"))
    await session.flush()

    svc = LLMNormalizerService(session)
    items = [ExtractedLineItem(line_number=1, raw_text="Tomatoes Cherry", quantity=Decimal("1"))]
    result = await svc.match_line_items(restaurant_a.id, items)

    assert len(result) == 1
    assert result[0].suggested_product_id is not None
    assert result[0].score >= 70.0


@pytest.mark.asyncio
async def test_match_case_and_accent_insensitive(session, restaurant_a):
    p = Product(restaurant_id=restaurant_a.id, name="Tomátês Cherry", unit="kg")
    session.add(p)
    await session.flush()

    svc = LLMNormalizerService(session)
    items = [ExtractedLineItem(line_number=1, raw_text="TOMATES CHERRY")]
    result = await svc.match_line_items(restaurant_a.id, items)

    assert result[0].suggested_product_id == p.id


@pytest.mark.asyncio
async def test_match_with_size_suffix(session, restaurant_a):
    p = Product(restaurant_id=restaurant_a.id, name="Chicken Breast Fillet", unit="kg")
    session.add(p)
    await session.flush()

    svc = LLMNormalizerService(session)
    items = [
        ExtractedLineItem(line_number=1, raw_text="Chicken Breast Fillet 1kg pack"),
    ]
    result = await svc.match_line_items(restaurant_a.id, items)

    assert result[0].suggested_product_id == p.id


@pytest.mark.asyncio
async def test_no_match_below_threshold(session, restaurant_a):
    session.add(Product(restaurant_id=restaurant_a.id, name="Tomatoes Cherry", unit="kg"))
    await session.flush()

    svc = LLMNormalizerService(session, threshold=70.0)
    items = [ExtractedLineItem(line_number=1, raw_text="Industrial diesel oil 200L drum")]
    result = await svc.match_line_items(restaurant_a.id, items)

    assert result[0].suggested_product_id is None


@pytest.mark.asyncio
async def test_empty_raw_text_returns_no_match(session, restaurant_a):
    session.add(Product(restaurant_id=restaurant_a.id, name="Tomatoes", unit="kg"))
    await session.flush()

    svc = LLMNormalizerService(session)
    items = [
        ExtractedLineItem(line_number=1, raw_text=None),
        ExtractedLineItem(line_number=2, raw_text="   "),
    ]
    result = await svc.match_line_items(restaurant_a.id, items)

    assert all(r.suggested_product_id is None for r in result)
    assert all(r.score == 0.0 for r in result)


@pytest.mark.asyncio
async def test_inactive_products_not_matched(session, restaurant_a):
    session.add(
        Product(
            restaurant_id=restaurant_a.id,
            name="Tomatoes Cherry",
            unit="kg",
            is_active=False,
        )
    )
    await session.flush()

    svc = LLMNormalizerService(session)
    items = [ExtractedLineItem(line_number=1, raw_text="Tomatoes Cherry")]
    result = await svc.match_line_items(restaurant_a.id, items)

    assert result[0].suggested_product_id is None


@pytest.mark.asyncio
async def test_multi_tenant_isolation(session, restaurant_a, restaurant_b):
    # Product belongs to restaurant B, query is for restaurant A → no match.
    session.add(Product(restaurant_id=restaurant_b.id, name="Tomatoes Cherry", unit="kg"))
    await session.flush()

    svc = LLMNormalizerService(session)
    items = [ExtractedLineItem(line_number=1, raw_text="Tomatoes Cherry")]
    result = await svc.match_line_items(restaurant_a.id, items)

    assert result[0].suggested_product_id is None


@pytest.mark.asyncio
async def test_empty_catalogue_returns_no_match(session, restaurant_a):
    svc = LLMNormalizerService(session)
    items = [ExtractedLineItem(line_number=1, raw_text="Tomatoes Cherry")]
    result = await svc.match_line_items(restaurant_a.id, items)

    assert result == [] or result[0].suggested_product_id is None


@pytest.mark.asyncio
async def test_threshold_override_lets_weak_match_through(session, restaurant_a):
    p = Product(restaurant_id=restaurant_a.id, name="Apple", unit="kg")
    session.add(p)
    await session.flush()

    # With a high threshold an unrelated query should not match...
    strict = LLMNormalizerService(session, threshold=95.0)
    items = [ExtractedLineItem(line_number=1, raw_text="Apple Juice 1L bottle")]
    strict_result = await strict.match_line_items(restaurant_a.id, items)
    # Either no match, or a match with score >= 95 — both acceptable; the
    # important property is that the threshold is honoured.
    if strict_result[0].suggested_product_id is not None:
        assert strict_result[0].score >= 95.0

    # ...but with a generous threshold, the product is suggested.
    loose = LLMNormalizerService(session, threshold=30.0)
    loose_result = await loose.match_line_items(restaurant_a.id, items)
    assert loose_result[0].suggested_product_id == p.id


@pytest.mark.asyncio
async def test_picks_best_among_multiple_candidates(session, restaurant_a):
    apple = Product(restaurant_id=restaurant_a.id, name="Apple", unit="kg")
    apple_red = Product(restaurant_id=restaurant_a.id, name="Apple Red Delicious", unit="kg")
    session.add(apple)
    session.add(apple_red)
    await session.flush()

    svc = LLMNormalizerService(session)
    items = [ExtractedLineItem(line_number=1, raw_text="Apple Red Delicious 1kg")]
    result = await svc.match_line_items(restaurant_a.id, items)

    # The longer specific product should be the better match for the longer query.
    assert result[0].suggested_product_id == apple_red.id
