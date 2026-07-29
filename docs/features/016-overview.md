# Spec 016 — Overview

## Status

Complete. Shipped 2026-07-28 in `0ddd43c`.

> **Written retrospectively on 2026-07-29**, from `0ddd43c`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## What shipped

The headline comparison: three systems, one set of numbers — trips, active
stations, date span, median trip duration with its middle half.

The common window (2017 onward, set by Vancouver) is stated in the section
lede, where a first-time viewer will look, rather than only on a methodology
page. Each system also shows its own full range, so the window is a statement
about comparability rather than a crop.

## Where the record is

- `src/App.tsx` — `#overview`
- `src/components/StatGrid.tsx`
