# ADR 002 — Accept Next.js 16, downgrade Tailwind CSS to 3.x

> Status: Accepted
> Date: 2026-05-06
> Decision makers: Henrique (project owner)
> Supersedes: ADR-001 D-005 (frontend framework and CSS versions only)

## Context

Phase 0 scaffold used create-next-app@latest, which installed Next.js 16.2.4
and Tailwind CSS 4 instead of the versions in ADR-001 (Next.js 15, Tailwind 3.x).
This ADR documents the post-analysis decision on each divergence.

## Decisions

### Next.js: Accept 16.x

Decision: Accept Next.js 16.x. No downgrade. Lock to ^16 in package.json.

Rationale: Backward-compatible superset of 15. App Router API unchanged.
Turbopack stable in 16. No breaking changes affect Phase 1-4 architecture.
No technical benefit to downgrading.

Trade-offs accepted: Docs reference "Next.js 15" — will be updated at Phase 1
sprint 1. No functional impact in the interim.

### Tailwind CSS: Downgrade to 3.x

Decision: Downgrade Tailwind 4 to 3.x. Pin ^3. Restore tailwind.config.ts.

Rationale: Tailwind 4 replaces tailwind.config.ts with CSS-based configuration,
diverging from all public tutorials, shadcn/ui docs, and community examples
the solo developer uses as reference. shadcn/ui designed and tested against
Tailwind 3. Ecosystem (tutorials, blog posts, copy-paste examples) overwhelmingly
v3. Official upgrade guide exists when ready to migrate.

Trade-offs accepted: Tailwind 3 in maintenance mode (bug fixes and security
only). Acceptable for 6-12 month window. Migration to v4 estimated at 1-2 days
when ecosystem matures.

## Review schedule

Revisit Tailwind version at Phase 3 start or when shadcn/ui officially declares
Tailwind 4 as stable default — whichever comes first.
