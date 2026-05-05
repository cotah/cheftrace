# ADR 001 — Initial stack decisions

> Status: Accepted
> Date: 2026-05-05
> Decision makers: Henrique (project owner), with technical advisory
> Supersedes: none

## Context

ChefTrace is a SaaS for restaurants in Ireland. It must support multi-tenant data isolation, batch-level inventory tracking with expiry, immutable audit logs (HACCP), invoice OCR, and POS integrations. The project owner is a solo developer with prior experience in FastAPI/Supabase/Railway from another product (SmartDocket).

This ADR captures the foundational technology decisions made before any code was written, so that future contributors can understand why each choice was made and the alternatives considered.

## Decisions

### D-001 Backend framework: FastAPI

**Decision:** Use FastAPI for the backend HTTP API.

**Alternatives considered:** Django REST Framework, Flask, Litestar.

**Rationale:**
- Native async support, critical for OCR calls and POS webhook processing.
- Pydantic-based validation aligns with our schema-first approach.
- OpenAPI generated automatically — frees us to share types with frontend later.
- Project owner already familiar from SmartDocket (zero learning curve).
- Active community, fast release cycle.

**Trade-offs accepted:**
- Smaller batteries-included scope than Django (no admin UI, no auth, no ORM bundled). We accept this because we use Supabase Auth and SQLModel.

### D-002 Python ORM: SQLModel

**Decision:** Use SQLModel for ORM and schema definitions.

**Alternatives considered:** SQLAlchemy 2.0 with separate Pydantic schemas, Tortoise ORM, Prisma Python.

**Rationale:**
- Combines SQLAlchemy 2.0 (mature, async-capable) with Pydantic v2 (already used for API).
- Single class definition for both DB model and validation reduces duplication.
- Maintained by FastAPI's author (Sebastián Ramírez), guaranteed alignment.
- Simpler mental model for solo dev than maintaining parallel SQLAlchemy + Pydantic classes.

**Trade-offs accepted:**
- Less mature than raw SQLAlchemy 2.0; some advanced patterns require dropping to SQLAlchemy directly. Acceptable since we will rarely need them.

### D-003 Authentication: Supabase Auth

**Decision:** Use Supabase Auth as the authentication provider. Backend verifies JWTs issued by Supabase but does not manage sessions.

**Alternatives considered:** Build JWT auth from scratch in FastAPI, Auth0, Clerk, AWS Cognito.

**Rationale:**
- Free tier covers up to 50,000 monthly active users — more than enough for years.
- Magic link, password reset, OAuth providers all included.
- Project owner already pays for Supabase and knows its API from SmartDocket.
- Email + password, magic link, OAuth providers, MFA available without code on our side.
- Reduces backend code by 3-5 days of development.

**Trade-offs accepted:**
- Vendor lock-in to Supabase. Mitigated by isolating auth concerns in `core/security.py` with a clean interface; could be replaced with another OIDC provider in 1-2 days if necessary.

### D-004 Database: PostgreSQL on Railway

**Decision:** PostgreSQL 16 hosted on Railway.

**Alternatives considered:** PostgreSQL on Supabase, MySQL, SQLite (rejected immediately).

**Rationale:**
- Railway is already paid by project owner (zero added cost).
- PostgreSQL is non-negotiable for the data model: we need JSONB, partial indexes, transactions, foreign keys, enum types, NUMERIC for money.
- Railway Postgres includes daily automatic backups.
- Connection pooling natively available.

**Why NOT Supabase Postgres:**
- Decoupling auth from data DB allows independent scaling and reduces blast radius. If Supabase has an outage, our DB still works.
- Avoids paying for Supabase Pro before we need to.
- Multi-tenant isolation enforced in application layer (not Supabase RLS) reduces complexity.

**Trade-offs accepted:**
- Lose Supabase Row-Level Security as a defense-in-depth layer. Mitigation: strict app-level multi-tenant filters + dedicated regression tests in CI for cross-tenant access attempts.

### D-005 Frontend framework: Next.js 15 with App Router

**Decision:** Next.js 15 with App Router, TypeScript strict mode.

**Alternatives considered:** Vite + React, Remix, SvelteKit, plain React Router.

**Rationale:**
- App Router enables Server Components and Server Actions — reduces JS bundle on landing pages and admin views that don't need interactivity.
- TypeScript strict catches integration bugs with backend API at compile time.
- Vercel deploy is one click, free tier sufficient for years.
- Project owner has prior Next.js experience (SmartDocket landing).
- App Router future-proof; old Pages Router being phased out.

**Trade-offs accepted:**
- App Router has steeper learning curve than Pages Router. Acceptable; documentation is excellent now.

### D-006 Storage: Supabase Storage

**Decision:** Supabase Storage for invoice files, HACCP report PDFs, and other user uploads.

**Alternatives considered:** AWS S3, Cloudflare R2, Backblaze B2.

**Rationale:**
- Free tier 1 GB, sufficient for first months.
- Pre-signed URL generation native, removes need for our backend to proxy file uploads.
- Same Supabase project as auth — single provider for client-facing storage.
- Pricing competitive when scaling ($0.021/GB/month after free tier).

**Trade-offs accepted:**
- Vendor lock-in. Mitigation: storage interactions isolated in `integrations/storage/supabase_storage.py` with abstract base class. Migration to S3 or R2 would take 1 day.

### D-007 OCR + LLM: Gemini 2.5 Flash with structured output

**Decision:** Use Google Gemini 2.5 Flash for OCR and LLM normalization of invoices in Phase 2.

**Alternatives considered:** Google Document AI, AWS Textract + Claude/GPT, Anthropic Claude direct, OpenAI GPT-4o.

**Rationale:**
- Gemini 2.5 Flash combines vision + LLM in one call — cheaper and lower latency than two-step (Document AI then GPT-4o).
- Structured output via Pydantic schema = no JSON parsing errors.
- Cost ~10% of GPT-4o for similar quality on invoice tasks.
- Free tier in Google AI Studio for early testing.

**Trade-offs accepted:**
- Vendor lock-in. Mitigation: OCR interactions isolated behind `integrations/ocr/base.py` abstract provider. Concrete implementations in `gemini_provider.py` and `fake_provider.py` (for tests). Switching providers takes 1-2 days.

### D-008 Python package manager: uv

**Decision:** Use `uv` (Astral) for Python dependency management.

**Alternatives considered:** pip + requirements.txt, Poetry, Pipenv, pdm.

**Rationale:**
- 10-100x faster than pip and Poetry.
- Single tool replaces pip, virtualenv, pip-tools, poetry.
- Native lockfile format (`uv.lock`) reproducible across systems.
- Built in Rust by Astral (same team as ruff). Aggressive maintenance.
- Adopted by FastAPI core team.

**Trade-offs accepted:**
- Newer tool (released 2024), less battle-tested than Poetry. Mitigation: fallback to pip is straightforward if needed.

### D-009 Node package manager: pnpm

**Decision:** Use `pnpm` for Node dependency management with workspaces.

**Alternatives considered:** npm, Yarn, Bun.

**Rationale:**
- Disk space efficient via content-addressed store (critical for monorepo).
- Native workspace support, simpler than Yarn workspaces.
- Strict by default (no phantom dependencies).
- Faster than npm and Yarn.
- Project owner already uses pnpm in SmartDocket.

**Trade-offs accepted:**
- Some packages with bad postinstall scripts misbehave. Rare in our stack.

### D-010 Repository structure: monorepo

**Decision:** Single repository `cheftrace` containing both backend and frontend, organized as monorepo with pnpm workspaces.

**Alternatives considered:** Polyrepo (separate `cheftrace-backend` and `cheftrace-web` repos).

**Rationale:**
- Single source of truth for shared types (TypeScript types generated from FastAPI OpenAPI).
- Single PR can change backend API and frontend consumer atomically — no out-of-sync deploys.
- Solo dev: less context switching, less infrastructure (one CI, one set of secrets).
- Can split later if necessary; reverse is harder.

**Trade-offs accepted:**
- Larger repo. Acceptable; modern tools (GitHub, IDE) handle it well.
- CI must use path filters to avoid running both pipelines on every commit. Implemented in `.github/workflows/` via `paths:` filters.

### D-011 Testing strategy

**Decision:**
- Backend: pytest + pytest-asyncio + httpx + factory-boy.
- Frontend: Vitest + React Testing Library + Playwright (E2E in Phase 1+).
- Coverage targets: 75% global, 90% on critical services (`stock_service`, `invoice_service`).
- Required regression tests in every PR: multi-tenant isolation, FEFO correctness, POS idempotency, stock movement immutability.

**Rationale:**
- Solo dev cannot manually regression test a SaaS with this scope. Tests are the only safety net.
- E2E tests (Playwright) cover critical user journeys that unit tests miss.
- Critical services warrant higher coverage because bugs there cause customer financial damage (incorrect stock, lost food, failed inspection).

### D-012 Email: Zoho Mail (transactional via Resend)

**Decision:**
- Human email (`henrique@cheftrace.com`, `hello@cheftrace.com`): Zoho Mail Free tier.
- System email (signup confirm, password reset, alerts): Resend (separate account, free tier 3000/month).

**Alternatives considered:** Google Workspace ($6/user/mo), Fastmail ($5/mo), SendGrid (transactional), Postmark.

**Rationale:**
- Cost: Zoho free tier sufficient for solo founder. Resend free tier covers thousands of users.
- Separation: human inbox (Zoho) vs deliverability-critical transactional (Resend) avoids accidental reputation damage.
- Resend has best DX (developer experience) of transactional providers.

### D-013 DNS: Cloudflare

**Decision:** Use Cloudflare as DNS provider (free tier).

**Alternatives considered:** Stay on registrar's default DNS, Route53, NS1.

**Rationale:**
- Free DDoS protection (registrar default does not include).
- CDN included, speeds up the landing page globally.
- Better admin panel than registrars'.
- Industry standard for SaaS.

### D-014 Naming: project codename `cheftrace`, commercial brand `ChefTrace`

**Decision:** Use `cheftrace` as the technical identifier (repo, packages, schemas, env var prefixes) and `ChefTrace` as the commercial brand (UI, marketing).

**Domains owned:**
- `cheftrace.com` (primary)
- `cheftrace.ie` planned but not yet purchased

**Trade-offs accepted:**
- Did not secure `.app` or other TLDs. Risk: speculator may register them. Mitigation: trademark `ChefTrace` once revenue justifies it (~6 months).

## Decisions explicitly deferred

- **Background job runner (Celery / RQ / Arq):** not needed in Phase 0-1. FastAPI BackgroundTasks suffice. Revisit when invoice OCR queue exceeds 10/min.
- **Caching layer (Redis):** not needed in Phase 0-1. Postgres handles current load.
- **Search engine (Meilisearch / Postgres FTS):** not needed until product catalog exceeds 10K rows.
- **Mobile app (React Native):** explicit non-goal until after V1.0 with paying customers.
- **Multi-region deployment:** Ireland-only until customer demand justifies it.

## Consequences

These decisions optimize for:
1. **Time to first paying customer.** Stack chosen lets us ship Phase 0 in 1 week, Phase 1 in 4 weeks.
2. **Solo developer productivity.** Familiar tools, minimal infrastructure to maintain.
3. **Future flexibility via abstractions.** OCR, POS, storage, and email all behind interfaces.

These decisions do NOT optimize for:
1. **Maximum scale.** This stack handles thousands of restaurants, not millions. Revisit when approaching 1000 paying customers.
2. **Multi-region resilience.** Single-region (Ireland) acceptable for IE-focused product.
3. **Compliance certifications (SOC 2, HIPAA).** Out of scope. Add when enterprise customers require.

## Review schedule

This ADR should be reviewed:
- At end of Phase 1 (after first 5 paying customers).
- When approaching 100 paying customers.
- When approaching 1000 paying customers.
- Whenever a major dependency reaches end-of-life or has a CVE.

Subsequent decisions should be captured as new ADRs (`002-...`, `003-...`) rather than editing this one.
