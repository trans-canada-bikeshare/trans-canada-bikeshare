# Spec 032 — Portfolio surface: reachable, navigable, presentable

## Status

Draft — written light 2026-07-31; firmed at load against a fresh headed
accessibility pass.

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

1. Mobile navigation and a skip link; keyboard focus visible throughout.
2. Accessible alternatives for hover/pointer-only encodings: keyboard
   chart exploration or equivalent data tables per section.
3. Footer: repository, methodology anchor, data-quality report, sister
   project, contact.
4. `og:image` + Twitter card; image asset provenance recorded per 002b.
5. `_headers`: immutable caching for hashed assets, HSTS, a CSP compatible
   with MapLibre workers/blobs, Permissions-Policy.
6. Measure CWV headed on production; optimize only what measurement
   indicts, recording before/after.
7. If pursuing the Mobi conversation: a landing emphasis pass — lead with
   findings, then method, then source link and invitation (owner input on
   which findings lead).

## Acceptance Criteria (firmed at load)

- [ ] Every section reachable and operable by keyboard alone on a phone
      viewport and desktop; verified headed, driven directly.
- [ ] Axe (or equivalent) reports no serious/critical violations.
- [ ] Social card renders correctly in a preview debugger.
- [ ] Headers verified live: immutable hashed assets, HSTS, CSP that does
      not break maps (headed map check after enabling).
- [ ] CWV measured and recorded; regressions from the header/caching work
      ruled out.

## Out of Scope

Rebranding, new metrics, new cities, analytics tooling.

## Rollback

`_headers` and markup revert with the merge; caching changes are
name-hashed so stale-asset risk is nil.
