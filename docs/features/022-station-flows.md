# Spec 022 — Station flows

## Status

**Not built.** Planned. The next surface to build.

## Context

Origin-destination pairs and net flow per station — the most visually
distinctive surface in the Vancouver project, and the one that gains most from
three cities side by side.

Blocked until Montreal had one identity per station rather than three. That
bridge landed with [spec 012](012-station-geography.md), so this is now
unblocked.

## Intended scope

- **Sources:** none new. `fact_trips` already carries canonical departure and
  return station ids.
- **Cities:** all three. **Tier:** 1. The registry marks `station_flows`
  supported for all three.
- **Published artifacts change:** yes, and this is the size risk — an OD matrix
  is quadratic in stations. Montreal has 1,152 mapped stations, so the full
  matrix is not shippable and the artifact must be a top-N or thresholded
  extract, with the truncation stated on the page.

## Intended changes

1. Net flow per station: returns minus departures, which reads as rebalancing
   pressure without modelling anything.
2. Top OD pairs per system, count stated and truncation disclosed.
3. Trips with no return station excluded and counted — 272,088 Montreal,
   10,824 Toronto, 10,776 Vancouver. They are real departures and are in the
   trip totals, but they cannot appear in a flow.

## Depends On

- [Spec 012](012-station-geography.md) — canonical station identity. Complete.
- [Spec 021](021-station-maps.md) — shares the coordinate artifact and the
  map component.
