# Spec 022 — Station flows

## Status

Complete. 2026-07-29.

## Context

Origin-destination pairs and net flow per station. Blocked until Montreal had
one identity per station rather than three; the bridge landed with
[spec 012](012-station-geography.md), and [spec 021](021-station-maps.md)
established the coordinate artifact and the map component this builds on.

Measured before designing, because two facts constrain the whole surface:

**The OD matrix cannot ship.** Distinct pairs: Montreal **1,189,574**, Toronto
575,736, Vancouver 107,530. Filtering to pairs with 500+ trips still leaves
33,732 for Montreal. Any pair list is a truncation, and the truncation has to
be a stated number rather than an implication.

**A top-N pair list is not like-for-like.** The 300 busiest pairs carry
**18.56%** of Vancouver's trips, **4.43%** of Toronto's and **3.35%** of
Montreal's. The same "top 300" describes most of Vancouver's network and almost
none of Montreal's. Three such lists side by side would imply a comparison that
does not hold.

So concentration becomes the comparable metric, and the pair lists are
explicitly per-city detail.

## Depends On

- [Spec 012](012-station-geography.md) — canonical station identity. Complete.
- [Spec 021](021-station-maps.md) — `stations.json`, `StationMap`. Complete.

## Scope

- **Sources touched:** none new. `fact_trips` already carries canonical
  departure and return station ids.
- **Cities touched:** all three. **Tier:** 1.
- **Published artifacts change:** **Yes** — `stations.json` gains one integer
  per station; new `flows.json`.

## Changes

1. **Net flow per station**, as one integer `n` = returns − departures, added
   to each `stations.json` entry. The rate is `n / t`, where `t` is the
   lifetime events already published — so the comparable quantity is derived in
   the browser rather than rounded twice in the artifact.
2. **`flows.json`** carrying, per system:
   - the **top 250 OD pairs** by trip count, with the share of system volume
     they represent, so the truncation is a published number and not a footnote
   - **concentration**: the share of all trips carried by the busiest 10, 100
     and 1,000 pairs — defined identically for all three, and the honest
     cross-city comparison
   - **round-trip share**: trips returning to their departure station.
     Vancouver 11.14%, Montreal 3.50%, Toronto 3.57%
3. **Net flow on the station map** — a diverging encoding, since a rate with a
   meaningful zero needs one. Stations that take more bikes than they give sit
   on one side of neutral, and the legend says which.
4. **Trips with no resolvable return station are excluded and counted**:
   272,088 Montreal, 10,824 Toronto, 10,776 Vancouver. They are real departures
   and remain in the trip totals, but a flow needs both ends.

## Acceptance Criteria

- [x] Net flow is defined identically for all three systems — one `UNION ALL`
      over departures and returns, no per-city branch
- [x] The rate is derived from published integers (`f / t`) in `flowRate()`,
      not re-rounded in the artifact
- [x] The pair list states how many pairs exist and what share the shown ones
      carry — 1,189,574 / 575,736 / 107,530, all rendered from `flows.json`
- [x] Concentration is presented as the cross-city comparison and the pair
      lists are labelled per-city detail, in the section's own words
- [x] Round trips are counted once and their treatment stated — they cancel in
      net flow, and the page says so
- [x] Trips with no return station are counted on the page: 272,088 / 10,824 /
      10,776
- [x] The diverging encoding is explained in the lede, including that it
      **clips at ±15%** — an encoding that saturates has to say so
- [x] Publish budget passes: 23.0% of 320 KB (was 19.9%)
- [x] `npm test` (68), `npm run typecheck`, `npm run build` exit 0;
      `make check` green, all 11 artifacts reproduce
- [x] **Rendered output confirmed in a headed browser** — production build,
      3 flow-mode maps drawing 260 / 1,102 / 972 dots, 15 pair rows, 0 console
      errors. No horizontal overflow at 320 / 768 / 1024 / 1360 px

## What the data turned out to say

The busiest pairs in **all three cities are round trips at recreational
destinations** — Stanley Park, Parc Jean-Drapeau, Tommy Thompson Park, the
Centre Island ferry dock. The single busiest flow in each system is a loop that
starts and ends at the same dock. That is not what "station flows" implies, and
it is the same shape in three cities that otherwise differ in every respect.

Concentration, the comparable figure: the 1,000 busiest pairs carry **31.6%**
of Vancouver's linked trips, **8.8%** of Toronto's and **7.3%** of Montreal's.

## Changes made during the build

- **The pair list shrank from 250 to 20 per system, and gained names.** The
  first version shipped 250 bare station keys — 38 KB no surface could render,
  because resolving keys to names needs `stations.json`, which is lazily loaded
  for the maps and may never arrive. `flows.json` went from 6.3 KB gzip to 1.7.
- **The nav breakpoint moved from `md` to `lg`.** At 768 px a seventh nav item
  pushed the theme toggle 22 px past the viewport. The overflow was
  pre-existing; adding "Flows" is what tipped it over.
- **The per-map caption lost the encoding sentence**, which the lede already
  carries — printing it under each of three maps was noise.

## Data Integrity Checklist

- [x] Provenance — no new sources; flows derive from `fact_trips`
- [x] Nothing guessed — a trip with no return station is excluded and counted,
      never assigned a destination. A top pair with an unnamed endpoint aborts
      the publish rather than rendering a blank row
- [x] Metrics defined identically — net flow, concentration and round-trip
      share use one query each across all three systems
- [x] Registry — **`make check-metrics` refused `flows.json` on its first
      publish run**, because nothing had declared it. That is precisely the
      spec 021 failure the gate was built for, caught automatically one commit
      after it landed
- [x] Artifacts reproduce — all 11 match a fresh publish run
- [x] Copy derives from the data — every count, share and truncation figure in
      the section reads from `flows.json`
- ~~Row accounting~~ — n/a, no ETL change
- [x] No raw data committed

## Out of Scope

- Time-of-day flow, rebalancing pressure and dwell —
  [spec 024](024-operational-signals.md). Net flow over a whole archive is a
  shape, not an operational signal.
- Drawing all pairs as lines. At 1.19M pairs that is neither shippable nor
  readable.

## Rollback

Single revert; `stations.json` loses `n` and `flows.json` becomes orphaned,
which `make check-artifacts` and `make check-metrics` both report.
