# Phase 0 Brief — ChefTrace

> Document version: 1.0
> Last updated: 2026-05-05
> Owner: Henrique
> Status: Ready for execution

This is the executable brief for Phase 0 of the ChefTrace project. Phase 0 sets up the foundational repository structure, dev environment, CI/CD pipeline, and deployment infrastructure. No business logic is implemented in this phase — only the skeleton.

## Context

ChefTrace is a SaaS for restaurants in Ireland providing inventory management with batch-level expiry tracking, HACCP digital records, invoice OCR, and POS integration. Phase 0 deliverable is a working monorepo with FastAPI backend and Next.js frontend, both deployed and CI-verified, ready for Phase 1 to start building features.

## Stack — DECIDED, do not deviate

| Layer | Technology | Version |
|---|---|---|
| Backend language | Python | 3.12 |
| Backend framework | FastAPI | latest stable |
| ORM | SQLModel | latest |
| Migrations | Alembic | latest |
| Python package manager | uv | latest |
| Backend logger | structlog | latest |
| Backend tests | pytest + pytest-asyncio + httpx | latest |
| Backend lint/format | ruff | latest |
| Backend type check | mypy (strict) | latest |
| Database | PostgreSQL | 16 (Railway) |
| Auth | Supabase Auth | n/a (managed) |
| Storage | Supabase Storage | n/a (managed) |
| Frontend framework | Next.js | 15 (App Router) |
| Frontend language | TypeScript | 5.x (strict) |
| CSS | Tailwind CSS | 3.x |
| UI components | shadcn/ui | latest |
| Server state | TanStack Query | 5.x |
| Forms | React Hook Form + Zod | latest |
| Frontend lint | ESLint + Prettier | latest |
| Frontend tests | Vitest + React Testing Library | latest |
| Node package manager | pnpm | 9+ |
| Backend deploy | Railway | n/a |
| Frontend deploy | Vercel | n/a |
| CI | GitHub Actions | n/a |

Constraint from project owner: NO emojis in folder names, file names, paths, or technical identifiers. Reason: Windows compatibility issues with Node tooling.

## Goal

By the end of Phase 0, the following must be true:

1. Repository `cotah/cheftrace` contains a working monorepo skeleton.
2. Backend responds to `GET /health` with `200 OK` both locally and in Railway production.
3. Frontend renders a placeholder landing page both locally (`localhost:3000`) and in Vercel production.
4. CI pipeline runs lint, type-check, and tests on every PR. All green.
5. README in repo root explains setup in under 5 minutes for a new developer.
6. ADR-001 documents all stack decisions.
7. `.env.example` files for backend and frontend list every required environment variable.

## Repository structure

Target structure at end of Phase 0:

```
cheftrace/
|-- .github/
|   `-- workflows/
|       |-- ci-backend.yml
|       `-- ci-web.yml
|-- apps/
|   |-- backend/
|   |   |-- alembic/
|   |   |   |-- versions/
|   |   |   |-- env.py
|   |   |   `-- script.py.mako
|   |   |-- app/
|   |   |   |-- __init__.py
|   |   |   |-- main.py
|   |   |   |-- core/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- config.py
|   |   |   |   |-- database.py
|   |   |   |   `-- logging.py
|   |   |   |-- api/
|   |   |   |   |-- __init__.py
|   |   |   |   `-- v1/
|   |   |   |       |-- __init__.py
|   |   |   |       |-- router.py
|   |   |   |       `-- endpoints/
|   |   |   |           |-- __init__.py
|   |   |   |           `-- health.py
|   |   |   |-- models/
|   |   |   |   |-- __init__.py
|   |   |   |   `-- base.py
|   |   |   `-- schemas/
|   |   |       `-- __init__.py
|   |   |-- tests/
|   |   |   |-- __init__.py
|   |   |   |-- conftest.py
|   |   |   `-- test_health.py
|   |   |-- alembic.ini
|   |   |-- Dockerfile
|   |   |-- pyproject.toml
|   |   |-- railway.toml
|   |   |-- .env.example
|   |   |-- .python-version
|   |   `-- README.md
|   `-- web/
|       |-- app/
|       |   |-- (marketing)/
|       |   |   `-- page.tsx
|       |   |-- layout.tsx
|       |   `-- globals.css
|       |-- components/
|       |   `-- ui/
|       |-- lib/
|       |   `-- utils.ts
|       |-- public/
|       |-- .env.example
|       |-- .eslintrc.json
|       |-- .prettierrc
|       |-- components.json
|       |-- next.config.ts
|       |-- package.json
|       |-- postcss.config.js
|       |-- tailwind.config.ts
|       |-- tsconfig.json
|       `-- README.md
|-- packages/
|   `-- shared/
|       |-- package.json
|       `-- tsconfig.json
|-- docs/
|   |-- adr/
|   |   `-- 001-stack-decisions.md
|   `-- PHASE-0-BRIEF.md
|-- .editorconfig
|-- .gitignore
|-- .nvmrc
|-- package.json
|-- pnpm-workspace.yaml
|-- README.md
`-- LICENSE
```

## Tasks (execute in order)

### Task 1: Monorepo skeleton

Create files at repo root:

**`.gitignore`**
```
# Node
node_modules/
.next/
dist/
.turbo/
*.log
.pnpm-store/
.pnpm-debug.log*

# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
venv/
htmlcov/
.coverage

# Env
.env
.env.local
.env.*.local
!.env.example

# IDE
.vscode/
.idea/
*.swp
.DS_Store
Thumbs.db

# Build
build/
*.egg
```

**`.editorconfig`**
```ini
root = true

[*]
indent_style = space
indent_size = 2
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.py]
indent_size = 4

[Makefile]
indent_style = tab
```

**`.nvmrc`**
```
20
```

**`pnpm-workspace.yaml`**
```yaml
packages:
  - 'apps/*'
  - 'packages/*'
```

**`package.json`** (root)
```json
{
  "name": "cheftrace",
  "version": "0.1.0",
  "private": true,
  "description": "Restaurant inventory + HACCP + invoice OCR + POS integration SaaS",
  "scripts": {
    "dev:web": "pnpm --filter web dev",
    "build:web": "pnpm --filter web build",
    "lint:web": "pnpm --filter web lint",
    "test:web": "pnpm --filter web test",
    "typecheck:web": "pnpm --filter web typecheck"
  },
  "engines": {
    "node": ">=20",
    "pnpm": ">=9"
  },
  "packageManager": "pnpm@9.0.0"
}
```

### Task 2: Backend setup (apps/backend)

Use `uv` for Python package management. uv is significantly faster than pip/poetry and is the modern standard.

**Initialize:**
```bash
cd apps/backend
uv init --name cheftrace-backend --no-readme
```

**`apps/backend/.python-version`**
```
3.12
```

**`apps/backend/pyproject.toml`** (replace generated content)
```toml
[project]
name = "cheftrace-backend"
version = "0.1.0"
description = "ChefTrace backend API"
requires-python = ">=3.12"
dependencies = [
    "fastapi[standard]>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlmodel>=0.0.22",
    "asyncpg>=0.30.0",
    "alembic>=1.13.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "structlog>=24.4.0",
    "python-jose[cryptography]>=3.3.0",
    "httpx>=0.27.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.7.0",
    "mypy>=1.13.0",
    "factory-boy>=3.3.0",
    "freezegun>=1.5.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM", "RUF"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/alembic/*"]
```

**`apps/backend/app/main.py`**
```python
"""FastAPI application entry point."""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("application.startup", env=settings.environment)
    yield
    logger.info("application.shutdown")


app = FastAPI(
    title="ChefTrace API",
    version="0.1.0",
    description="Restaurant inventory + HACCP + invoice OCR API",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
```

**`apps/backend/app/core/config.py`**
```python
"""Application configuration using pydantic-settings."""
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = Field(..., description="PostgreSQL connection string")

    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_anon_key: str = Field(..., description="Supabase anon public key")
    supabase_jwt_secret: str = Field(..., description="Supabase JWT secret for token verification")

    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()  # type: ignore[call-arg]
```

**`apps/backend/app/core/database.py`**
```python
"""Database session management."""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**`apps/backend/app/core/logging.py`**
```python
"""Structured logging configuration with structlog."""
import logging
import sys

import structlog

from app.core.config import settings


def configure_logging() -> None:
    """Configure structlog for the application."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.environment == "development":
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

**`apps/backend/app/api/v1/router.py`**
```python
"""API v1 router aggregator."""
from fastapi import APIRouter

from app.api.v1.endpoints import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
```

**`apps/backend/app/api/v1/endpoints/health.py`**
```python
"""Health check endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(
        status="ok",
        service="cheftrace-backend",
        version="0.1.0",
    )
```

**`apps/backend/tests/conftest.py`**
```python
"""Pytest configuration and shared fixtures."""
import os

# Load test environment before any app imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("ENVIRONMENT", "development")
```

**`apps/backend/tests/test_health.py`**
```python
"""Health endpoint tests."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_ok():
    """Health endpoint returns 200 with expected payload."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "cheftrace-backend"
    assert "version" in data
```

**`apps/backend/.env.example`**
```env
# Application
ENVIRONMENT=development
LOG_LEVEL=INFO

# Database (Railway provides DATABASE_URL automatically in production)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/cheftrace

# Supabase
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-anon-key-from-supabase-dashboard
SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase-dashboard

# CORS (comma-separated origins)
CORS_ORIGINS=["http://localhost:3000"]
```

**`apps/backend/Dockerfile`**
```dockerfile
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies first (better caching)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy application
COPY . .

# Install project itself
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`apps/backend/railway.toml`**
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "apps/backend/Dockerfile"

[deploy]
startCommand = "uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/api/v1/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

**Initialize Alembic:**
```bash
cd apps/backend
uv run alembic init -t async alembic
```

Then edit `apps/backend/alembic.ini`:
- Set `sqlalchemy.url = ` (leave empty, will be loaded from env)

Edit `apps/backend/alembic/env.py` to load from settings:
```python
# Add at top
from app.core.config import settings
from sqlmodel import SQLModel

# Replace target_metadata = None with:
target_metadata = SQLModel.metadata

# In run_migrations_online(), replace config.get_section() call with:
config.set_main_option("sqlalchemy.url", settings.database_url)
```

**Install dependencies and verify:**
```bash
cd apps/backend
uv sync
uv run ruff check .
uv run mypy app
uv run pytest
uv run uvicorn app.main:app --reload
```

Expected: backend running on `localhost:8000/api/v1/health` returning 200 OK.

### Task 3: Frontend setup (apps/web)

**Bootstrap Next.js 15:**
```bash
cd apps
pnpm create next-app@latest web --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*" --use-pnpm --no-turbopack
```

When prompted, accept all defaults except where the flags above already specified.

**Update `apps/web/package.json`** add scripts:
```json
{
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

**Install additional dependencies:**
```bash
cd apps/web
pnpm add @supabase/ssr @supabase/supabase-js @tanstack/react-query react-hook-form zod @hookform/resolvers
pnpm add -D vitest @vitejs/plugin-react @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom prettier prettier-plugin-tailwindcss
```

**Setup shadcn/ui:**
```bash
cd apps/web
pnpm dlx shadcn@latest init
```

When prompted: TypeScript yes, default style, base color slate, CSS variables yes.

Install initial components:
```bash
pnpm dlx shadcn@latest add button card input label
```

**`apps/web/.env.example`**
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**`apps/web/.prettierrc`**
```json
{
  "semi": true,
  "singleQuote": false,
  "tabWidth": 2,
  "trailingComma": "all",
  "printWidth": 100,
  "plugins": ["prettier-plugin-tailwindcss"]
}
```

**`apps/web/app/(marketing)/page.tsx`** (landing placeholder)
```tsx
export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="max-w-2xl text-center">
        <h1 className="mb-4 text-5xl font-bold tracking-tight">ChefTrace</h1>
        <p className="text-xl text-muted-foreground">
          Restaurant inventory, HACCP records, and invoice automation for Irish kitchens.
        </p>
        <p className="mt-8 text-sm text-muted-foreground">Coming soon.</p>
      </div>
    </main>
  );
}
```

**Verify frontend:**
```bash
cd apps/web
pnpm dev
```

Expected: page rendering at `localhost:3000` with placeholder text.

### Task 4: CI setup

**`.github/workflows/ci-backend.yml`**
```yaml
name: Backend CI

on:
  push:
    paths:
      - 'apps/backend/**'
      - '.github/workflows/ci-backend.yml'
  pull_request:
    paths:
      - 'apps/backend/**'

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        working-directory: apps/backend
        run: uv sync --frozen

      - name: Lint
        working-directory: apps/backend
        run: uv run ruff check .

      - name: Format check
        working-directory: apps/backend
        run: uv run ruff format --check .

      - name: Type check
        working-directory: apps/backend
        run: uv run mypy app

      - name: Run tests
        working-directory: apps/backend
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test
          SUPABASE_URL: https://test.supabase.co
          SUPABASE_ANON_KEY: test-anon-key
          SUPABASE_JWT_SECRET: test-jwt-secret
          ENVIRONMENT: development
        run: uv run pytest --cov=app --cov-report=term
```

**`.github/workflows/ci-web.yml`**
```yaml
name: Web CI

on:
  push:
    paths:
      - 'apps/web/**'
      - 'packages/**'
      - '.github/workflows/ci-web.yml'
  pull_request:
    paths:
      - 'apps/web/**'
      - 'packages/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'pnpm'

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Lint
        run: pnpm --filter web lint

      - name: Type check
        run: pnpm --filter web typecheck

      - name: Test
        run: pnpm --filter web test

      - name: Build
        env:
          NEXT_PUBLIC_SUPABASE_URL: https://test.supabase.co
          NEXT_PUBLIC_SUPABASE_ANON_KEY: test-anon-key
          NEXT_PUBLIC_API_URL: http://localhost:8000
        run: pnpm --filter web build
```

### Task 5: Documentation

**`README.md`** (root)
```markdown
# ChefTrace

Restaurant inventory + HACCP + invoice OCR + POS integration SaaS for Irish restaurants.

## Stack

- **Backend:** Python 3.12, FastAPI, SQLModel, Alembic, PostgreSQL 16
- **Frontend:** Next.js 15, TypeScript, Tailwind CSS, shadcn/ui
- **Auth:** Supabase Auth
- **Storage:** Supabase Storage
- **Deploy:** Railway (backend), Vercel (frontend)
- **Package managers:** uv (Python), pnpm (Node)

## Prerequisites

- Node.js 20+
- pnpm 9+
- Python 3.12+
- uv (https://docs.astral.sh/uv/)
- PostgreSQL 16 (or Docker)

## Local development setup

### 1. Clone and install

```bash
git clone https://github.com/cotah/cheftrace.git
cd cheftrace
pnpm install
```

### 2. Backend

```bash
cd apps/backend
cp .env.example .env
# Fill in .env with your local values (see docs/setup-env.md)
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Backend runs at http://localhost:8000

### 3. Frontend

```bash
cd apps/web
cp .env.example .env.local
# Fill in .env.local with your Supabase values
pnpm dev
```

Frontend runs at http://localhost:3000

## Project structure

See docs/PHASE-0-BRIEF.md for full structure.

## Deployment

- Backend deploys automatically to Railway on push to main
- Frontend deploys automatically to Vercel on push to main

## Documentation

- `docs/adr/` — Architecture Decision Records
- `docs/PHASE-0-BRIEF.md` — Phase 0 specification
- `docs/runbooks/` — Operational runbooks (added as needed)

## License

Proprietary. All rights reserved.
```

**`docs/adr/001-stack-decisions.md`** — see separate ADR document.

### Task 6: Initial commit and push

```bash
cd cheftrace
git add .
git commit -m "feat: phase 0 setup - monorepo skeleton, FastAPI backend, Next.js frontend, CI pipeline"
git push origin main
```

### Task 7: Manual deployment steps (Henrique only)

These cannot be automated by Claude Code — Henrique must do them through web dashboards.

**Railway:**
1. Open Railway dashboard, project `cheftrace`.
2. Click "+ New" → "GitHub Repo" → connect `cotah/cheftrace`.
3. In service settings:
   - Root directory: `/` (monorepo root)
   - Watch paths: `apps/backend/**`
4. Add environment variables from `apps/backend/.env.example` (use real values).
5. Generate domain: Settings → Networking → "Generate Domain" — copy URL.
6. Verify: visit `https://<your-railway-url>/api/v1/health` — must return 200.

**Vercel:**
1. Open vercel.com → "Add New" → "Project" → import `cotah/cheftrace`.
2. Framework preset: Next.js
3. Root directory: `apps/web`
4. Build command: `cd ../.. && pnpm install && pnpm --filter web build`
5. Install command: `pnpm install`
6. Output directory: `.next` (default)
7. Add environment variables from `apps/web/.env.example`:
   - `NEXT_PUBLIC_API_URL` = Railway URL from previous step
8. Deploy.
9. Verify: open Vercel URL — must show "ChefTrace - Coming soon" landing.

**Cloudflare DNS (after both deploys are live):**
1. cloudflare.com → Add Site → enter `cheftrace.com`.
2. Free plan.
3. Cloudflare scans existing DNS, then gives you 2 nameservers (e.g., `nina.ns.cloudflare.com`).
4. Go to your domain registrar (where you bought cheftrace.com).
5. Replace nameservers with Cloudflare's. Save.
6. Wait up to 24h for propagation (usually 5-15 min).
7. In Cloudflare DNS panel, add records:
   - `A` record `@` (root) → Vercel IP (Vercel will tell you)
   - `CNAME` record `www` → `cheftrace.com`
   - `CNAME` record `app` → `cname.vercel-dns.com` (if you want app.cheftrace.com)
   - `CNAME` record `api` → Railway URL
8. In Vercel: Project Settings → Domains → add `cheftrace.com` and `www.cheftrace.com`.
9. In Railway: Service Settings → Networking → Custom Domain → add `api.cheftrace.com`.

This step can be deferred to end of Phase 1 if you prefer to use Vercel/Railway default URLs first.

## Acceptance criteria — Phase 0 done when ALL true

- [ ] Repo `cotah/cheftrace` has structure matching the tree above.
- [ ] `pnpm install` at root succeeds with no errors.
- [ ] `cd apps/backend && uv sync` succeeds with no errors.
- [ ] `cd apps/backend && uv run pytest` shows all tests pass.
- [ ] `cd apps/backend && uv run ruff check .` shows zero issues.
- [ ] `cd apps/backend && uv run mypy app` shows zero issues.
- [ ] `cd apps/backend && uv run uvicorn app.main:app --reload` starts and `GET http://localhost:8000/api/v1/health` returns `{"status":"ok",...}`.
- [ ] `cd apps/web && pnpm dev` starts and `http://localhost:3000` renders the landing placeholder.
- [ ] `cd apps/web && pnpm typecheck` shows zero errors.
- [ ] `cd apps/web && pnpm lint` shows zero errors.
- [ ] `cd apps/web && pnpm build` succeeds.
- [ ] PR to main triggers both CI workflows. Both green.
- [ ] Railway backend live at `<railway-url>/api/v1/health` returning 200.
- [ ] Vercel frontend live at `<vercel-url>` rendering landing.
- [ ] README in repo root explains setup in under 5 min.
- [ ] `docs/adr/001-stack-decisions.md` committed.
- [ ] All `.env.example` files committed (actual `.env` files NOT committed — verify with `git ls-files | grep env`).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| `uv` not installed on Henrique's machine | Pre-flight check above; install command provided |
| Windows path issues with pnpm/Python | Use forward slashes in scripts; avoid spaces in folder names |
| Supabase JWT secret leaked to repo | `.gitignore` covers `.env`; CI does not log secrets; pre-commit hook recommended in Phase 1 |
| Railway deploy fails on first push | Verify Dockerfile builds locally first: `docker build -t cheftrace-backend apps/backend/` |
| Vercel monorepo build fails | Use `pnpm` in build command; ensure `pnpm-workspace.yaml` is committed before deploying |
| CI passes locally but fails in GitHub Actions | Pin all action versions; use exact dependency versions in lockfiles (`uv.lock`, `pnpm-lock.yaml`) |

## Next steps after Phase 0

Phase 1 begins immediately after acceptance criteria are met. Phase 1 deliverables:
- Multi-tenant auth (users, restaurants, memberships)
- Products + categories + suppliers CRUD
- Stock lots with expiry + FEFO consumption
- Stock movements (immutable)
- Equipment + temperature logs
- HACCP checklist templates and runs
- Dashboard with alerts
- HACCP PDF export

Phase 1 brief will be issued as a separate document upon Phase 0 sign-off.
