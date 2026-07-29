# Spec 019 — E-bike share

## Status

Complete, as a **two-city** comparison. Shipped 2026-07-28 in `0ddd43c`.

> **Written retrospectively on 2026-07-29**, from `0ddd43c`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## Context

Spec 001 established that Montreal publishes no bike-type field in any era.
This metric therefore cannot be a three-city comparison, and the registry marks
it `comparable: false` with `mtl-bixi` unsupported and the reason stated.

## What shipped

E-bike share for Vancouver and Toronto, with Montreal **explicitly marked "not
published"** rather than absent. A visible, explained gap is more informative
than a quietly missing city.

Toronto's e-bike share reaching roughly 22% is the most interesting trend in
the data. Dropping the metric to keep a tidy three-column grid would have been
the wrong trade.

## Where the record is

- `pipeline/publish.py` — `guard(registry, "ebike_share", ...)`
- `docs/decisions.md`, 2026-07-28 entry on two-city comparisons
