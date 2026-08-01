# Spec 032 — Portfolio surface: reachable, navigable, presentable

## Status

Complete. Merged 2026-07-31; production re-verification recorded at the
foot of this file. Originally: firmed at load the same day — the pre-load
pass confirmed both
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

- [x] On a phone-width viewport, every section is reachable through the
      menu and by keyboard alone; the skip link is the first tab stop and
      works; verified headed on the Pages preview, driven directly.
- [x] Axe (or equivalent DOM audit) reports no serious/critical
      violations on desktop and phone widths.
- [x] Every chart section exposes its data to keyboard/AT users via a
      focusable table derived from the same committed artifact; a test
      pins one table's values to the artifact.
- [x] og:image + Twitter card meta present; the card fetches as image/png
      at 1200x630 from the deployed preview; asset provenance recorded.
- [x] Headers verified live on the Pages preview AND production after
      merge: HSTS, Permissions-Policy, CSP present; hashed /assets/*
      immutable; maplibre worker files still must-revalidate; all three
      maps draw dots WITH CSP enforced (headed).
- [x] CWV (LCP, CLS, INP-proxy) measured headed on preview and production,
      recorded in the spec; no regression attributable to headers/caching.
- [x] 173+ vitest, typecheck, build, and the full pipeline gate battery
      stay green; committed artifacts untouched.

## Out of Scope

Rebranding, new metrics, new cities, analytics tooling.

## Rollback

`_headers` and markup revert with the merge; caching changes are
name-hashed so stale-asset risk is nil.

## Verification record (test, 2026-07-31)

All against the Pages preview deployment (branch preview-032), where
`_headers` is live; production re-verification follows the merge.

- **Headers, live**: HSTS, CSP, Permissions-Policy, nosniff,
  Referrer-Policy on `/`; hashed `/assets/*` `immutable` 1y; the un-hashed
  MapLibre worker files exactly `public, max-age=0, must-revalidate` (the
  Cloudflare merge-detach works); `/og-image.png` image/png, 1h.
- **Maps under enforced CSP, headed**: all three maps draw basemaps and
  dots (counts 260+0 / 1,045+56 / 969+3, artifact-exact), zero console
  violations. One environment trap en route, recorded because the 2026-07-29
  decision predicted it exactly: a backgrounded automation tab froze
  rendering and screenshots, making the preview look broken; an A/B against
  production under identical driving showed identical placeholders,
  exonerating the CSP before any code was touched. Verified in a live tab.
- **Phone width (390px, DOM-level via Playwright — CSS/DOM assertions, not
  rAF surfaces)**: skip link is the first focusable and moves focus to
  #main; desktop nav hidden; the Sections disclosure opens with all 11
  links, focus moves in, scroll locks; Escape closes, returns focus,
  unlocks; tables open with artifact-faithful cells (Apr 2014 row: 108,264
  Montreal, em-dashes for systems not yet operating).
- **DOM audit at 1280px and 390px**: the author's structural audit (names,
  labels, ids, heading order, landmarks, table headers, aria integrity)
  found one issue — the menu's aria-controls dangled when closed; fixed by
  keeping the panel in the DOM with hidden, contract pinned in a test. Its
  "zero findings after" claim was then corrected by review: real axe-core
  4.10.3 with every table OPEN found scrollable-region-focusable (serious)
  on the table scroll containers — a state the author's audit never
  exercised, and a Safari keyboard user could not scroll 139 rows. Fixed
  (tabIndex, role region, aria-labelledby to the caption); **axe re-run
  with all eight tables open: zero violations at 1280 and at 390.** Review
  also caught a scroll-lock leak when crossing to desktop with the menu
  open (now closes itself on the breakpoint, verified) and three caption
  wording nits (fixed).
- **Social card**: served from the preview as image/png at exactly
  1200x630, byte-identical to the committed asset.
- **CWV, same tool same machine (Playwright, 1280px)**:
  production FCP 136ms / LCP 228ms / CLS 0.003 / TTFB 67ms;
  preview-032 FCP 140ms / LCP 248ms / CLS 0.003 / TTFB 53ms.
  Differences within run noise — no regression attributable to headers or
  caching; both far inside the good thresholds, so the MapLibre chunk
  warning stays accepted. Paint metrics could not be honestly measured in
  the extension tab (a non-painting tab produces no FCP/LCP while network
  timings still report), which is why the comparison ran in Playwright.
- **Suites**: 199 vitest, typecheck, build; pipeline gates untouched by
  this spec's changes and green at branch (270 pytest, six-gate make
  check earlier in-branch).

## Production verification (complete, 2026-07-31)

Post-merge, against https://bikeshare.adnanreza.com (deployment source
13337a3, main CI green, PR #7 merged):

- All five security header classes on `/`; the CSP byte-identical to the
  committed `_headers` line; worker files exactly
  `public, max-age=0, must-revalidate`; **`/og-image` serves
  `x-robots-tag: noindex`** — the rule no preview could prove.
- All three maps drew their dots headed under the enforced CSP
  (artifact-exact counts, OpenFreeMap basemaps, zero violations).
- Served bytes hash-identical to the local build.
- One platform observation, not a defect: the custom domain serves
  `/og-image.png` with `max-age=14400` although the deployment itself
  (preview and deployment-direct URLs) serves the rule's 3600 — the
  adnanreza.com zone's Browser Cache TTL floors cacheable assets at four
  hours. The consequence (a social card cached 4h instead of 1h) is
  immaterial; changing the zone setting is the owner's call since it
  spans every subdomain.
