# Spec 032 — Portfolio surface: reachable, navigable, presentable

## Status

Ready — firmed at load 2026-07-31. The pre-load pass confirmed both
structural gaps on production (no navigation of any kind below the lg
breakpoint; no skip link) and set the verification model: header behavior
(CSP, HSTS, caching) is proven on a **Cloudflare Pages preview
deployment** of the branch before production, because `vite preview`
does not serve `_headers` — asserting CSP from local serving would be
the spec-021 class of unverified render.

## Context

Verified 2026-07-31: the section nav is `hidden … lg:flex` with no mobile
alternative (`App.tsx:187`) — below the lg breakpoint the site has no
navigation at all; there is no skip link; charts are hover-dependent and
map stations pointer-only; the footer links to nothing (no repository,
methodology, sister project, or contact); social metadata lacks `og:image`
and a Twitter card; hashed assets are cached for 4 hours rather than
immutable; HSTS/CSP/Permissions-Policy are absent. Bundle sizes are known
(371 KB main, 981 KB lazy MapLibre) but unmeasured against Core Web
Vitals — measure before optimizing.

## Depends On

028 (truthful claims before promoting them), 030 (stable section naming).
031 independent.

## Scope

Site and Pages configuration only. Published data artifacts change: No.
`index.html`, `src/`, `public/_headers`, and an `og:image` asset change.

## Changes (firmed at load)

1. Mobile navigation (disclosure menu below lg, same section list, ESC
   and outside-click close, focus-trapped while open) and a skip link as
   first focusable element; keyboard focus visible throughout.
2. Accessible alternatives for hover/pointer-only encodings: a
   visually-hidden-but-focusable data table per chart section (derived
   from the same artifact the chart renders — never a second source),
   and the existing no-hover legends verified sufficient where they
   already carry the values (spec 026).
3. Footer: repository, methodology anchor, data-quality report (repo
   path), data dictionary, sister project, adnanreza.com.
4. `og:image` (1200x630) + Twitter card meta; the image composed from
   the existing brand assets, provenance recorded per 002b; served and
   verified with a card debugger or raw fetch.
5. `public/_headers` (Cloudflare Pages syntax): immutable caching for
   hashed `/assets/*` (except the un-hashed maplibre worker files, which
   keep must-revalidate), HSTS, Permissions-Policy, and a CSP proven
   against the maps on a Pages preview deployment — `worker-src blob:`,
   OpenFreeMap tile/sprite/glyph origins in `connect-src`/`img-src`,
   no `unsafe-eval`.
6. Measure CWV headed on the preview and production; optimize only what
   measurement indicts, recording before/after. The MapLibre chunk-size
   warning stays accepted unless CWV indicts it.
7. Landing emphasis pass: deferred — owner input on which findings lead;
   not part of this spec's merge.

## Acceptance Criteria (firmed at load)

- [ ] On a phone-width viewport, every section is reachable through the
      menu and by keyboard alone; the skip link is the first tab stop and
      works; verified headed on the Pages preview, driven directly.
- [ ] Axe (or equivalent DOM audit) reports no serious/critical
      violations on desktop and phone widths.
- [ ] Every chart section exposes its data to keyboard/AT users via a
      focusable table derived from the same committed artifact; a test
      pins one table's values to the artifact.
- [ ] og:image + Twitter card meta present; the card fetches as image/png
      at 1200x630 from the deployed preview; asset provenance recorded.
- [ ] Headers verified live on the Pages preview AND production after
      merge: HSTS, Permissions-Policy, CSP present; hashed /assets/*
      immutable; maplibre worker files still must-revalidate; all three
      maps draw dots WITH CSP enforced (headed).
- [ ] CWV (LCP, CLS, INP-proxy) measured headed on preview and production,
      recorded in the spec; no regression attributable to headers/caching.
- [ ] 173+ vitest, typecheck, build, and the full pipeline gate battery
      stay green; committed artifacts untouched.

## Out of Scope

Rebranding, new metrics, new cities, analytics tooling.

## Rollback

`_headers` and markup revert with the merge; caching changes are
name-hashed so stale-asset risk is nil.
