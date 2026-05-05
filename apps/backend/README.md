# ChefTrace Backend

FastAPI backend for ChefTrace.

## Setup

```bash
cp .env.example .env
# Fill in .env with your local values
uv sync
uv run uvicorn app.main:app --reload
```

Server runs on http://localhost:8000. Health check at `/api/v1/health`.

## Common commands

```bash
uv run ruff check .
uv run ruff format .
uv run mypy app
uv run pytest
uv run alembic upgrade head
```
