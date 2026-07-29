# Spec 021 — Station maps

## Status

Ready

## Context

Every station-level surface was blocked until Montreal had one identity per
station rather than three. The bridge (`pipeline/sql/35_bridge.sql`) landed
2026-07-29, GBFS coordinates are loaded for all three systems, and 2,445 of
3,412 identities are positioned. This is the first surface to spend that.

A map is also the honest way to show something the charts cannot: these three
networks have very different *shapes*. Montreal's is dense and radial around
the Plateau; Toronto's runs along the lake and up the subway lines; Vancouver's
is compact and hugs the downtown peninsula. Counting stations tells you none of
that.

## Depends On

- Spec 012 / the Montreal bridge — coordinates and canonical identity.
  Complete as of `71b2d64`.

## Scope

- **Sources touched:** none new; GBFS coordinates already pinned and loaded.
- **Cities touched:** all three. **Tier:** 1.
- **Published artifacts change:** **Yes** — adds `stations.json`
  (~57 KB gzip, taking the total to ~19% of the 320 KB budget).

## Changes

1. **`stations.json`** — one entry per station with coordinates and at least
   100 lifetime events: canonical id, name, lat, lon, lifetime events, active
   flag. Keyed compactly, since this is the largest artifact the site ships.
2. **A map per system**, MapLibre GL with the OpenFreeMap `positron` and `dark`
   styles, matching the sister project. **Loaded lazily** — the library is
   ~230 KB gzipped against a current bundle of ~62 KB, so it must not land
   until a reader scrolls to it.
3. **Station dots** sized by lifetime events and coloured by that system's
   series colour, so a station's identity on the map matches its line on every
   chart.
4. **Selection** shows the station's name, lifetime trips, and whether it is
   currently active.
5. **Inactive stations are drawn differently, not hidden.** A retired station
   is part of the network's history and the map is the only surface that can
   show where the network used to reach.

## Acceptance Criteria

- [x] Each system renders its own map, centred and zoomed to its own stations
      rather than a shared viewport — measured: distinct centres, zoom 9.99 /
      6.61 / 9.14 before the framing fix, each on its own city
- [x] MapLibre is not in the initial bundle — entry chunk 75.50 kB gzip,
      `maplibre-gl` a separate 256.53 kB chunk, `grep -c maplibre` on the entry
      chunk returns 0
- [x] Basemap follows the theme and swaps when the theme toggles — 3 `positron`
      + 3 `dark` style requests after a toggle, old instances removed
- [x] Dot colour matches that system's series colour everywhere else on the site
      — `circle-color` now resolves to `hsl(205 74% 38%)` from the same token
      the charts use. **This criterion was previously marked met while the
      layer was being rejected outright.**
- [x] Dormant stations are visibly distinct from active ones, and the caption
      says which is which
- [x] Selecting a station shows name, lifetime events, and dormancy
- [x] Stations without coordinates are stated as a count, not silently omitted
      — page figures reconcile exactly against `stations_meta.json`
- [x] Keyboard: the map is reachable and does not trap focus — Tab from the
      canvas reaches the zoom controls and exits in DOM order
- [x] No horizontal overflow at 320px in either theme —
      `scrollWidth === clientWidth` (305/305) in both
- [x] `npm test` (56), `npm run typecheck`, `npm run build` exit 0; publish
      budget 19.9% of 320 KB

- [x] **Dots confirmed drawn.** Measured in a real headed Chromium
      (`visibility: visible`, `raf: true`, WebGL via ANGLE Metal), against both
      the dev server and the production build:

      | | dev | prod | artifact |
      |---|---|---|---|
      | Vancouver | 260 | 260 | 260 |
      | Montreal | 1,102 | 1,102 | 1,152 |
      | Toronto | 972 | 972 | 972 |

      `styleLoaded: true`, 16 vector tiles, zero console errors. Montreal
      renders 1,102 of 1,152 because the framing fence keeps the Sherbrooke
      and South Shore outliers outside the opening viewport — they are drawn,
      one pan east, which the section states.

**How this was nearly missed twice.** The first attempt to verify used
headless Playwright and a backgrounded automation tab; both throttle
`requestAnimationFrame` to zero, so MapLibre never renders, never requests a
tile, and the basemap is as blank as the dots. Every reading from those
environments was consistent with "working" and with "completely broken". The
answer only came from a headed browser driven directly, which any future
render-surface spec should use from the start.

## Data Integrity Checklist

- [x] Provenance — coordinates come from the pinned GBFS feeds and Montreal's
      annual snapshots, both checksummed. `make check-manifest` ok 14/13/104
- [x] Nothing guessed — a station without coordinates is omitted from the map
      and **counted on the page**, never placed at a guessed position. No
      `fillna`, bare `except`, `COALESCE(x, 0)` or `errors="coerce"` in the
      diff; the two `coalesce` uses are commented provenance chains. The
      coordinate validator nulls BIXI's `(-1,-1)` row and 7 GBFS `(0,0)` rows
      rather than plotting them
- [x] Metrics defined identically — "lifetime events" is departures plus
      returns for every system, recomputed independently from `conformed_trips`
      and exact for all three (mtl 176,123,580 / tor 77,144,982 / van
      17,634,356)
- [x] Artifacts reproduce — "all 10 artifacts match a fresh publish run"
- [x] Copy derives from the data — station counts, the threshold, and the
      omission counts all read from the artifact. Two claims that did **not**
      derive from it were removed: a causal explanation of missing coordinates
      the data contradicted, and a Vancouver shape claim true of activity but
      not of stations
- [x] Registry gate — `stations` now calls `guard(registry, "active_stations")`
      like every other cross-city artifact. It previously skipped it
- ~~Row accounting~~ — n/a, no ETL change to trip parsing; `fact_trips` is
      unchanged at 135,598,303 across the `40_model.sql` edit
- [x] No raw data committed

## Testing

- Vitest: the artifact has coordinates within each city's plausible bounding
  box; every station's system is one of the three; the missing-coordinate count
  rendered on the page matches the artifact.
- Browser: lazy load verified in the network panel, theme swap, selection,
  320px in both themes.

## Out of Scope

- Station flows (spec 022) — this shows where stations are, not what moves
  between them
- Transit proximity, which needs each city's transit geometry

## Rollback

Single revert. `stations.json` becomes orphaned and `make check-artifacts`
reports it, which is the intended behaviour.
