# Spec 024 — Operational signals

## Status

**Not built.** Planned. Scope reshaped 2026-07-30 at the owner's direction:
**Montreal is included in the comparable core.** It is the flagship system —
88M of the archive's 135.6M trips — and the first draft of this spec would
have excluded it because the scope was written around the one signal
(per-bike dwell) Montreal cannot support, rather than around the signals the
trip data supports for everyone.

## Intended scope

Two tiers, decided by what each signal needs:

**Three-city, like-for-like (trips only — Montreal included):**

1. **Net flow by hour of day** — where rebalancing pressure actually shows.
   One query, all three systems, full archive.
2. **Implied minimum daily rebalancing** — sum over stations of |daily net
   flow| / 2: the fewest bike moves that could reset each day's imbalance.
   Measured 2025+: Montreal ~2,812 moves/day, Toronto ~1,418, Vancouver ~398.
   This is a DERIVED lower bound and must be labelled as one, everywhere it
   appears: it assumes overnight reset, ignores intra-day rebalancing, and
   excludes trips without both ends. These are the signals most easily
   mistaken for measurements.

**Per-city detail (bike ids required — Montreal labelled not-published):**

3. **Per-bike dwell** (return to next departure at the same dock).
   Toronto 2019-2026 at 100.0% bike_id coverage, unbroken. Vancouver only in
   its clean eras — 2017-2020 and 2024-2026; its 2021 (56.7%), 2022 (0%) and
   2023 (18.6%) are withheld with the gap stated, the membership discipline.
   Montreal publishes no bike ids in any era; "not published", e-bike-style.

## Registry change this requires

`operational_signals` today marks Montreal unsupported wholesale — written
when the spec was dwell-centric. Split it:

- `rebalancing_pressure`: comparable **true**, supported all three
- `bike_dwell`: comparable false; mtl-bixi unsupported (no bike ids, any era);
  van-mobi era-limited, stated

`make check-metrics` and `guard()` then enforce the split per artifact.

## Not possible, and why

- Live dock occupancy / rebalancing events: needs GBFS `station_status`
  sampled over time. No manifest pins it, no history exists, it cannot be
  backfilled. A future collector could start accumulating it.
- Montreal dwell: nothing in the record identifies a bike across trips.
  Inferring identity from behaviour would be imputation.

## Depends On

- [Spec 022](022-station-flows.md) — shares the net-flow computation. Complete.

## Rollback

Single revert; new artifacts orphan and both gates report them.
