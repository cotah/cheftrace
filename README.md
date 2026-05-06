# ChefTrace

Restaurant inventory + HACCP + invoice OCR + POS integration SaaS for Irish restaurants.

## Stack

- **Backend:** Python 3.12, FastAPI, SQLModel, Alembic, PostgreSQL 16
- **Frontend:** Next.js 16, TypeScript, Tailwind CSS, shadcn/ui
- **Auth:** Supabase Auth
- **Storage:** Supabase Storage
- **Deploy:** Railway (backend), Vercel (frontend)
- **Package managers:** uv (Python), pnpm (Node)

## Prerequisites

- Node.js 24+
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
