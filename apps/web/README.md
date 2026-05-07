# ChefTrace Web

Next.js 16 + TypeScript frontend for ChefTrace. Talks to the FastAPI backend
under `apps/backend/`. Auth via Supabase. Deployed on Vercel.

## Prerequisites

- **Node.js 20+**
- **pnpm 9+** — `npm install -g pnpm`
- A running ChefTrace backend (default `http://localhost:8000`)
- A Supabase project (free tier is enough)

## Install and run locally

```bash
# From the monorepo root (recommended — uses workspace install)
pnpm install
pnpm --filter web dev

# Or inside apps/web/
cp .env.example .env.local
# Edit .env.local with your Supabase + backend URL
pnpm dev
```

App: `http://localhost:3000`.

## Environment variables

Set in `apps/web/.env.local` (or `.env`). Names only — no real values.

| Variable | Required | Notes |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | yes | Supabase project URL — same one used by backend |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | yes | Supabase anon publishable key |
| `NEXT_PUBLIC_API_URL` | yes | Backend base URL (e.g. `http://localhost:8000` for local) |

The `NEXT_PUBLIC_` prefix is required by Next.js to expose the value to the
browser. None of these are secrets — the JWT signing secret stays on the
backend.

## Quality checks

```bash
pnpm --filter web typecheck    # TypeScript strict
pnpm --filter web lint         # ESLint
pnpm --filter web test run     # Vitest (one-shot)
pnpm --filter web build        # Next.js production build
```

All four must pass before commit.

## Production build (smoke check)

```bash
pnpm --filter web build
pnpm --filter web start        # serves the production build on :3000
```

## Project layout

```
app/
├── (auth)/                  # signin, signup
├── app/                     # authenticated app shell
│   ├── layout.tsx           # auth + restaurant context guard
│   └── [restaurantId]/      # all multi-tenant routes
├── onboarding/              # 4-step wizard
└── (marketing)/             # landing page
components/
├── nav/                     # sidebar
├── onboarding/              # wizard step components
└── ui/                      # shadcn/ui primitives
hooks/                       # use-auth, use-restaurant, use-token
lib/
├── api/                     # client, types, resources (one object per backend tag)
├── pdf-download.ts          # bearer-auth blob download helper
└── supabase/                # client + server helpers
proxy.ts                     # Next.js middleware (Supabase auth guard)
```

## Notes

- This is **not** a stock create-next-app — `params` are awaited
  via `React.use(params)` in client components (Next 16 convention).
- Routes under `/app/[restaurantId]/...` assume an authenticated user with at
  least one restaurant. The middleware redirects unauthenticated users to
  `/signin`; the layout shows a loading state while `useAuth` and
  `useRestaurant` resolve.
- All shadcn/ui components are tracked in git under `components/ui/`. Add
  more with `pnpm dlx shadcn@latest add <component>`.
