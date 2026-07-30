# Spec 009 — Metric support registry

## Status

**Shipped half-built.** The registry landed 2026-07-28 in `cb10b98`. Its
enforcement did not, and was completed 2026-07-29 as
[spec 009b](009b-metric-gate.md).

> **Written retrospectively on 2026-07-29**, from `cb10b98`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## Context

Three systems with three schema histories. Spec 001 established that Montreal
publishes no bike-type field in any era and loses `is_member` at the 2022
format break, so two of the README's headline metrics cannot be three-city
comparisons. That fact needed to live somewhere a test could read.

## What shipped

`pipeline/mappings/metric_support.json` — a committed declaration, per metric,
of which systems support it and under exactly what definition: units, trip
filter, window, null handling. Nine metrics: `trips`, `seasonality`,
`duration`, `active_stations`, `station_flows`, `ebike_share`,
`membership_mix`, `forecast`, `operational_signals`.

**Ten since 2026-07-30.** [Spec 024](024-operational-signals.md) split
`operational_signals` into `rebalancing_pressure` (comparable, all three) and
`bike_dwell` (not comparable; Montreal unsupported). One key could only ever be
as narrow as its narrowest signal, and this one had marked Montreal unsupported
wholesale for a bike identifier that only dwell needs.

Each metric carries a `comparable` flag. Each unsupported system carries the
reason it is unsupported, because a gap the site shows and explains is worth
more than a metric quietly missing a city.

`guard()` in `pipeline/publish.py` raises `UnsupportedSeries` when a published
series contains a system the registry excludes.

## What did not ship

The file's own comment claimed enforcement by `make check-metrics`. That target
was a stub until 2026-07-29 — it printed a message and exited 0, so `make check`
reported success without running it. Spec 021 then published a three-city
station series having called `guard()` for neither of its artifacts, and every
gate passed.

The lesson is recorded in `009b`: `guard()` is opt-in per call site, so it
cannot catch the artifact nobody thought to guard.

## Where the record is

- `pipeline/mappings/metric_support.json`
- `pipeline/publish.py` — `supported_systems()`, `guard()`
- `docs/decisions.md`, 2026-07-28 entry on two-city comparisons
