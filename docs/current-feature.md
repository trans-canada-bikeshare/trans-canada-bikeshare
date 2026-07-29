# Current Feature: 002b Brand identity assets

## Status

In Progress — branch `feature/002b-brand-identity`

## Lifecycle

<!-- Each action stamps its own line with the date it ran. `/feature complete`
     refuses to proceed while `review` is unstamped. -->

- [x] load — 2026-07-28
- [x] start — 2026-07-28
- [x] test — 2026-07-28
- [x] review — 2026-07-28

## Goals

- `public/favicon.svg` renders the eight-spoke wheel with a red leaf hub and
  inverts its rim under `prefers-color-scheme: dark`
- The wheel is legible at 32px and its silhouette survives at 16px
- `favicon.ico` contains 16, 32 and 48 pixel images and is a valid ICO
- `apple-touch-icon.png` is 180×180 with an opaque background
- `icon-192.png` and `icon-512.png` exist and are referenced by the manifest
- `index.html` references the SVG icon, ICO fallback, apple-touch icon and
  manifest; no request 404s
- The header renders `logo.svg` and the footer carries the non-affiliation line
- No console errors or failed requests on load
- The placeholder favicon from spec 002 is gone
- `npm test`, `npm run typecheck`, `npm run build` all exit 0
- Provenance for both source assets is recorded in the repo

## Notes

**Depends on:** spec 002 (`7093bac`). No data, no cities, no artifact change.

**Two marks, because one cannot do both jobs.** Logo = StVO pictogram + canonical
flag leaf (wide, mud below ~64px). Favicon = eight-spoke wheel with the leaf at
the hub (square, legible at 16).

**Provenance.** Bicycle: German StVO 1992 *Sinnbild Radfahrer*, public domain
(`PD-VzKat`, §5(1) UrhG) — no attribution required. Leaf: National Flag of
Canada, usable per Order in Council P.C. 1965-1623 s.4 subject to good taste, no
exclusivity claimed, no preventing others' use.

**Why the favicon is a spoked wheel and not a leaf in a ring.** A bare leaf
centred in an open ring is Air Canada's *rondelle*. Air Canada was formerly
Trans-Canada Air Lines; this is transport; the name starts "Trans-Canada". Those
three facts together make that composition a real conflict, so the rim, eight
spokes and hub are load-bearing, not decorative. A test fails if they are ever
removed.

### Test (2026-07-28)

**45 vitest** (4 files, 13 new) · typecheck 0 · build 0. All eight asset paths
return 200. Browser load: **zero console errors**.

- The favicon's dark-mode rule was confirmed the hard way — QuickLook rendered
  the first PNG with `prefers-color-scheme: dark` applied, producing a nearly
  invisible rim. That proved the media query fires, and forced separate
  fixed-colour raster sources, since PNG and ICO cannot adapt.
- The ICO was **verified by re-reading its bytes** — header, image count, and
  each directory entry's dimensions checked against the embedded PNG's own IHDR
  — rather than trusting the encoder that had just written it.

### Review (2026-07-28)

| Item | Verdict |
| --- | --- |
| No raw data in the diff | **pass** — no data touched; `app.png` screenshot caught and removed before staging |
| Attribution | **pass** — both sources' terms recorded in the spec and in SVG comments; neither requires attribution, and that fact is written down rather than assumed |
| Nothing guessed silently | **pass** — the ICO is verified, not asserted |
| Provenance / row accounting / artifacts / metrics / copy / encodings | n/a — no data, no ETL, no artifacts, no metrics, no data-derived copy |

**Noted, not fixed:** the header logo sits at 44×18, which makes the bicycle
small. Acceptable for a scaffold surface that spec 015 replaces wholesale.

**Standing caveat:** none of the rights reasoning is legal advice. A Canadian
trademark agent should clear both marks before any commercial use.

**Verdict: ready to complete.**

## History

<!-- Appended by `/feature complete`, oldest first. ONE LINE per feature:
     `YYYY-MM-DD` `<sha>` — what shipped. Spec path.
     The detail lives in the merge commit; `git show <sha>` is the record.
     Keep this file cheap to load — it enters context every session. -->

- 2026-07-28 `5425262` — spec 001: source column audit across all three systems.
  E-bike share and membership mix confirmed **not** three-city comparable;
  BIXI and Toronto era maps and the BIXI station bridge established.
  `docs/features/001-source-column-audit.md` → `docs/source-audit.md`
- 2026-07-28 `7093bac` — spec 002: repo scaffold. Python pipeline skeleton,
  Vite/React/Tailwind site, design tokens ported verbatim from the Vancouver
  project (26 pinned tests), `make check` gate stubs. 32 vitest + 7 pytest.
  `docs/features/002-repo-scaffold.md`
