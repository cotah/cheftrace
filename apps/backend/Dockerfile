FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files first for better layer caching
COPY apps/backend/pyproject.toml apps/backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy application source
COPY apps/backend/ .

# Install project itself
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD sh -c "uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
