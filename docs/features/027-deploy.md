# Spec 027 — Deploy

## Status

**Not built, deliberately.** Written as a runbook and never executed.

The instruction for the autonomous build was to stop before deployment. The
steps are recorded in `docs/runbook.md` so that deploying is a decision someone
makes, not something that happened.

## Blocked on owner decisions

Three things must be settled first, and none is technical:

1. **The BIXI licence.** The source page states no terms, no licence, and no
   attribution requirement. The site says so plainly, which is honest, but
   publishing Montreal data is a decision to take deliberately. If terms arrive
   that forbid it, the fix is one publish run — Montreal drops out of
   `src/data/generated/` and the site renders it as unavailable.
2. **Trademark clearance** on the logo and favicon. The reasoning in
   `docs/features/002b-brand-identity.md` is not legal advice.
3. **A canonical URL.** `og:url` and the canonical link are absent because no
   domain is committed to.

## Intended changes

Static build to Cloudflare Pages, matching the sister project. Custom domain.
The monthly-refresh runbook is already written.

## Where the record is

- `docs/runbook.md` — rebuild, gates, monthly refresh, and the deploy steps
