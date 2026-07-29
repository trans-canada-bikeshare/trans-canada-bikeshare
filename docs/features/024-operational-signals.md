# Spec 024 — Operational signals

## Status

**Not built.** Planned.

## Context

Rebalancing pressure, dwell, and the derived signals that read as operations
rather than dashboard chrome. The registry marks `operational_signals`
`comparable: false` — Montreal is unsupported.

## Intended scope

- **Sources:** possibly GBFS `station_status` over time, which no manifest
  currently pins. Free-floating dwell needs bike ids, which not every system
  publishes.
- **Cities:** Vancouver and Toronto. **Tier:** 1, explicitly not comparable.
- **Published artifacts change:** yes.

## Intended changes

1. Net flow by hour of day, which is where rebalancing pressure actually shows.
2. Dwell between a return and the next departure at the same station, where bike
   identity permits it.
3. Every signal labelled as derived, with the derivation stated. These are the
   metrics most easily mistaken for measurements.

## Depends On

- [Spec 022](022-station-flows.md) — shares the flow computation.
