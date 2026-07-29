# Spec 017 — Trips over time and seasonality

## Status

Complete. Shipped 2026-07-28, revised 2026-07-29 in `c2be567`.

> **Written retrospectively on 2026-07-29**, from `0ddd43c, c2be567`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## What shipped

Monthly trips per system and the seasonal shape that distinguishes a Montreal
winter from a Vancouver one.

**Revised after review.** The first version plotted all three systems on one
linear axis spanning a 26:1 range, which made Vancouver a flat line along the
bottom. It now renders as small multiples — one panel per system, each scaled
to itself with its own declared ceiling — and seasonality is plotted as share
of each system's own year, which is the comparison actually being made.

A claim that BIXI closes mid-November to mid-April was removed: it has been
false since December 2023, and it sat directly above the chart disproving it.

## Where the record is

- `src/components/charts/SmallMultiples.tsx`, `LineChart.tsx`
- `docs/decisions.md`, 2026-07-29 review entry
