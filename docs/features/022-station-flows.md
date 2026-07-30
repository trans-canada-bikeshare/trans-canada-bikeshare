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
546,270, Vancouver 74,502. Filtering to pairs with 500+ trips still leaves
33,732 for Montreal. Any pair list is a truncation, and the truncation has to
be a stated number rather than an implication.

**A top-N pair list is not like-for-like.** The 300 busiest pairs carry
**19.08%** of Vancouver's linked trips, **4.54%** of Toronto's and **3.35%** of
Montreal's. The same "top 300" describes much of Vancouver's network and almost
none of Montreal's. Three such lists side by side would imply a comparison that
does not hold.

So concentration becomes the comparable metric, and the pair lists are
explicitly per-city detail.

## Depends On

- [Spec 012](012-station-geography.md) — canonical station identity. Complete.
- [Spec 021](021-station-maps.md) — `stations.json`, `StationMap`. Complete.

## Scope

- **Sources touched:** none new. **`pipeline/sql/40_model.sql` changed** —
  `fact_trips` was believed to carry canonical station ids and did not (see
  *Changes made during the build*), so the warehouse is rebuilt.
- **Cities touched:** all three. **Tier:** 1.
- **Published artifacts change:** **Yes** — `stations.json` gains one integer
  per station; new `flows.json`.

## Changes

1. **Net flow per station**, as one integer `f` = returns − departures, added
   to each `stations.json` entry. (`n` was taken — it is the station name.) The
   rate is `f / t`, where `t` is the lifetime events already published, so the
   comparable quantity is derived in the browser rather than rounded twice.
2. **`flows.json`** carrying, per system:
   - the **8 busiest OD pairs**, with names denormalised, plus the total pair
     count and the share the shown ones carry — so the truncation is a
     published number, not a footnote. (Eight, not the 250 first drafted, and
     eight rendered: see *Changes made during the build*.)
   - **concentration**: the share of all trips carried by the busiest 10, 100
     and 1,000 pairs — defined identically for all three, and the honest
     cross-city comparison
   - **round-trip share**: trips returning to their departure station, as a
     share of all that system's trusted trips — Vancouver 11.12%, Montreal
     3.49%, Toronto 3.58%. The page uses this denominator; against *linked*
     trips the figures differ in the second decimal.
3. **Net flow on the station map** — a diverging encoding, since a rate with a
   meaningful zero needs one. Amber gives out more than it takes in, indigo
   takes in more, and the lede says which. It **clips at ±15%** — stations do
   reach ±0.44 (Vancouver) and ±0.73 (Toronto), and scaling to them would
   flatten every ordinary dock to grey — so the lede also says it clips.
   Two palettes, one per theme, because a single set failed WCAG 1.4.11 on
   the dark basemap at 1.58:1.
4. **Trips with no resolvable return station are excluded and counted**:
   272,088 Montreal, 10,824 Toronto, 10,776 Vancouver. They are real departures
   and remain in the trip totals, but a flow needs both ends.

## Acceptance Criteria

- [x] Net flow is defined identically for all three systems — one `UNION ALL`
      over departures and returns, no per-city branch
- [x] The rate is derived from published integers (`f / t`) in `flowRate()`,
      not re-rounded in the artifact
- [x] The pair list states how many pairs exist and what share the shown ones
      carry — 1,189,574 / 546,270 / 74,502 and the shown share, both rendered
      from `flows.json`
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
- [x] **Rendered output confirmed in a headed browser** — production build.
      All 260 / 1,152 / 972 shipped stations draw; the in-viewport counts are
      lower for Montreal because the Tukey fence leaves its Sherbrooke
      outliers outside the opening frame. No horizontal overflow at
      320 / 768 / 1024 / 1360 px

## What the data turned out to say

**The single busiest pair in every system is a loop** — Stanley Park's
Information Booth, Parc Jean-Drapeau, Tommy Thompson Park — a bike taken out
and returned to the same dock. That is not what "station flows" implies.

Below the top spot the three cities diverge, and an earlier draft of this spec
and of the site claimed they did not. Loops among each system's eight busiest
pairs: **Toronto 7, Vancouver 5, Montreal 4** — and Montreal's list runs to
metro stations and street corners (Métro Pie-IX → Desjardins / Ontario), which
is a last-mile commute, not a park loop. Across the top twenty the split was
sharper still: Toronto 14, Vancouver 11, Montreal 5.

The site now derives these counts from the artifact rather than asserting them,
which is the only reason this correction is a one-line edit and not a hunt.

Concentration, the comparable figure: the 1,000 busiest pairs carry **32.43%**
of Vancouver's linked trips, **9.07%** of Toronto's and **7.27%** of Montreal's.

## Changes made during the build

- **`fact_trips` and `dim_station` did not agree, and this spec divided one by
  the other.** `dim_station` collapsed a station reached by name into the same
  station reached by its published id; `fact_trips` did not. 781 Toronto keys
  (2,249,950 events) and 266 Vancouver keys (529,839) existed in the fact with
  no row in the dimension. Net flow was a partial numerator over a merged
  denominator, and Vancouver's distinct-pair count was inflated 44%, Toronto's
  5%, Montreal's not at all — the "different amount each" failure that same
  file warns is the worst kind for a side-by-side comparison. The resolution
  is now one materialised `station_identity` table both tables consume.
- **The pair list shrank from 250 to 8 per system, and gained names.** The
  first version shipped 250 bare station keys — 38 KB no surface could render,
  because resolving keys to names needs `stations.json`, which is lazily loaded
  for the maps and may never arrive. A second version shipped 20 while
  rendering 5. `flows.json` is now 1.0 KB gzip.
- **The ±15% clip was justified by an outlier that does not exist.** The lede
  said "a handful of stations reach 90%"; no station on any of these maps
  exceeds 0.735. The figure came from stations without coordinates, which are
  never drawn.
- **Unreturned trips left a phantom −1 at their origin** — 272,088 in Montreal,
  biasing that whole map amber for a gap in the data rather than a movement of
  bikes. Net flow now counts only trips with both ends recorded and sums to
  exactly zero per system, which `pipeline/tests/test_flows.py` pins.
- **`FLOW_SCALE` was typed `unknown[]` and cast `as never`.** The annotation
  was the sole cause of the error the cast suppressed, and `as never` is
  assignable to anything — so a misspelt operator would have compiled clean
  and been rejected silently at runtime, which is how spec 021 shipped three
  blank maps. Typed as MapLibre's `ExpressionSpecification`, no cast.
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
- [x] Row accounting — the ETL **did** change. `fact_trips` still holds
      135,598,303 rows and `dim_station` 3,412 across the rebuild; only the
      station keys on the fact moved, and every key now resolves to a
      dimension row (previously 1,047 did not)
- [x] No raw data committed

## Out of Scope

- Time-of-day flow, rebalancing pressure and dwell —
  [spec 024](024-operational-signals.md). Net flow over a whole archive is a
  shape, not an operational signal.
- Drawing all pairs as lines. At 1.19M pairs that is neither shippable nor
  readable.

## Rollback

Single revert; `stations.json` loses `f` and `flows.json` becomes orphaned,
which `make check-artifacts` and `make check-metrics` both report.
