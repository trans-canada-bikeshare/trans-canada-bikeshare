# Spec 021 — Station maps

## Status

Ready

## Context

Every station-level surface was blocked until Montreal had one identity per
station rather than three. The bridge (`pipeline/sql/35_bridge.sql`) landed
2026-07-29, GBFS coordinates are loaded for all three systems, and 2,451 of
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

- [ ] Each system renders its own map, centred and zoomed to its own stations
      rather than a shared viewport
- [ ] MapLibre is not in the initial bundle — verified by checking the built
      chunks and by a network trace that shows it loading only on demand
- [ ] Basemap follows the theme and swaps when the theme toggles
- [ ] Dot colour matches that system's series colour everywhere else on the site
- [ ] Retired stations are visibly distinct from active ones, and the legend
      says which is which
- [ ] Selecting a station shows name, lifetime trips, and active state
- [ ] Stations without coordinates are stated as a count, not silently omitted
- [ ] Keyboard: the map is reachable and does not trap focus
- [ ] No horizontal overflow at 320px in either theme
- [ ] `npm test`, `npm run typecheck`, `npm run build` exit 0; the publish
      budget still passes

## Data Integrity Checklist

- [ ] Provenance — coordinates come from the pinned GBFS feeds and Montreal's
      annual snapshots, both checksummed
- [ ] Nothing guessed — a station without coordinates is omitted from the map
      and **counted on the page**, never placed at a guessed position
- [ ] Metrics defined identically — "lifetime events" is departures plus
      returns for every system
- [ ] Artifacts reproduce — `make check-artifacts` covers the new file
- [ ] Copy derives from the data — station counts and the missing-coordinate
      count come from the artifact
- ~~Row accounting~~ — n/a, no ETL change
- [ ] No raw data committed

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
