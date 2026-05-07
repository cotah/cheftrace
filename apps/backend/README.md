# ChefTrace Backend

FastAPI backend for ChefTrace — a SaaS for restaurants in Ireland that handles
food expiry, stock with FEFO consumption, HACCP digital logs, equipment
temperature monitoring, purchase lists, and HSE-style PDF reports.

## Prerequisites

- **Python 3.12** (3.13 not yet validated)
- **uv** — `pip install uv` or [astral.sh/uv](https://docs.astral.sh/uv/)
- **PostgreSQL 16** for production (Railway-hosted) — locally any reachable Postgres works
- **Docker** (recommended) — used for the local test database on port 5433

## Install and run locally

```bash
# Inside apps/backend/
cp .env.example .env
# Edit .env — at minimum set DATABASE_URL, SUPABASE_*

uv sync
uv run uvicorn app.main:app --reload
```

Server: `http://localhost:8000`. Health check at `/api/v1/health`.
OpenAPI docs at `/docs`.

## Environment variables

Set in `apps/backend/.env`. Names only — no real values in this README.

| Variable | Required | Notes |
|---|---|---|
| `ENVIRONMENT` | yes | `development` / `staging` / `production` |
| `LOG_LEVEL` | yes | `INFO` is fine for dev |
| `DATABASE_URL` | yes | `postgresql+asyncpg://user:pass@host:port/db` |
| `TEST_DATABASE_URL` | no | Used by the test suite when present (default: `localhost:5433`) |
| `SUPABASE_URL` | yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | yes | Supabase anon publishable key |
| `SUPABASE_JWT_SECRET` | yes | JWT signing secret (used for HS256 fallback) |
| `CORS_ORIGINS` | yes | JSON array of origins, e.g. `["http://localhost:3000"]` |

## Tests

The DB-dependent tests use `TEST_DATABASE_URL` (default `localhost:5433`).
Start a throwaway Postgres in Docker:

```bash
docker run -d --name cheftrace-test \
  -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test \
  -p 5433:5432 postgres:16
```

Run the suite:

```bash
uv run pytest                                  # all tests
uv run pytest -v --tb=short                    # verbose
uv run pytest tests/test_permissions.py        # without DB
uv run pytest --cov=app                        # with coverage
```

PDF tests skip on Windows (WeasyPrint native libs are Linux/macOS only) and
run on CI/Docker.

## Migrations

Two helper scripts in `scripts/`:

```bash
./scripts/migrate-local.sh      # apply against local Postgres on :5433
./scripts/migrate-railway.sh    # apply against Railway (uses .env DATABASE_URL)
```

Or call alembic directly:

```bash
uv run alembic upgrade head     # apply latest
uv run alembic current          # show current revision
uv run alembic downgrade -1     # roll back one revision
uv run alembic history          # full history
```

Always test a new migration locally first with `migrate-local.sh`, including a
`downgrade -1` round-trip, before applying to Railway.

## Quality checks

```bash
uv run ruff check .         # lint
uv run ruff format .        # auto-format
uv run mypy app             # type check (strict)
uv run pytest               # tests
```

## Project layout

```
app/
├── api/v1/endpoints/        # FastAPI routers (one per resource)
├── core/                    # config, security, permissions, exceptions
├── models/                  # SQLModel ORM
├── schemas/                 # Pydantic request/response schemas
├── services/                # business logic (StockService, HACCPService, ...)
└── templates/pdf/           # Jinja2 templates for WeasyPrint reports
alembic/versions/            # database migrations
tests/                       # pytest suite
scripts/                     # ops helpers (migrations, etc.)
```
