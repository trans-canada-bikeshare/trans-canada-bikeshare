# v1 Roadmap

Full parity with the Vancouver project across three docked systems. Twenty-seven
specs in eight phases, each one small enough to load, build, review, and merge on
its own.

**Decided 2026-07-28:** the warehouse ingests every year each city publishes
(Toronto and Montreal from 2014, Vancouver from 2017); cross-city comparisons
default to the **2017+ common window** and say so on the chart, while per-city
views show that city's full range. v1 carries the whole feature set — maps,
flows, weather-driven forecast, and operational signals — for all three systems.

## The three systems

| Key | City | System | Open trip data | Shape |
| --- | --- | --- | --- | --- |
| `van-mobi` | Vancouver | Mobi by Rogers | 2017– | Monthly XLSX/CSV via Google Drive |
| `mtl-bixi` | Montreal | BIXI | 2014– | Annual ZIP of monthly CSVs |
| `tor-bikeshare` | Toronto | Bike Share Toronto | 2014– | Annual ZIP of monthly CSVs (CKAN) |

Every fact and dimension carries `system_id`. There is one manifest and one
column-era map per city. No metric is published across cities until the metric
registry (spec 009) says all three define it the same way.

## Why 001 comes before everything

Three systems, three schema histories, and at least one known incompatible break
(BIXI's format changes at 2022, and `start_station_code` becomes
`emplacement_pk_start` in 2021). Whether the site's headline metrics are even
derivable — e-bike share above all — is currently unknown for two of the three
cities. Specs 005 through 008 cannot be written honestly until real headers have
been read, so they stay deliberately thin here until 001 lands.

---

## Phase 0 — Verify

**001 · Source column audit and feasibility map.** Download one real period from
each city, read the actual headers, and write a verified column-by-column map:
timestamps and their precision, station identity and coordinates, membership
fields, trip duration and distance, and whether a bike-type or e-bike flag
exists. Confirm each source's licence. Output is a document, not code. Every
later spec depends on it.

## Phase 1 — Acquire

**002 · Repo scaffold.** Python 3.11 pipeline skeleton with DuckDB, Vite + React
+ TypeScript + Tailwind app, Vitest and pytest harnesses, and the portfolio
design tokens ported from the Vancouver project. No data yet.

**003 · Per-city manifest and downloaders.** One manifest per city pinning every
source file to a SHA-256 and byte size. Idempotent downloads that skip files
already matching. Format detection by magic bytes, never by extension. A
re-download whose content differs fails unless explicitly accepted.

**004 · Inventory and archive verification.** Verify the archive against the
manifests: gaps in the expected period run, undersized files, checksum
mismatches. Exits non-zero so it can gate the pipeline.

## Phase 2 — Warehouse

**005 · Extract.** Every file lands as VARCHAR in `raw_trips` with headers
unified through a per-city era map. An unmapped header aborts the run. Depends
entirely on 001.

**006 · Clean.** Typing, timestamp parsing across every observed format, hard
drops for blank stations and unparseable timestamps, exact-duplicate removal.
Every drop counted by reason into `etl_metrics`.

**007 · Conform.** Station identity per system, canonical departure month,
quality flags that mark suspect rows without deleting them.

**008 · Model.** Kimball star schema: `fact_trips`, `dim_system`, `dim_station`,
`dim_date`, `dim_membership`. The system dimension is what makes every
downstream query comparable or explicitly not.

**009 · Metric support registry.** A committed declaration of which metrics each
system supports and under what definition — units, trip filter, window, null
handling. Publishing a cross-city series for a metric the registry does not mark
supported in all three is an error, not a judgement call. This is what turns
"measured the same way" from a promise into something a test can fail on.

**010 · Quality report.** Generated per-city and combined accounting: stage
funnel, drop reasons, flag counts, membership mapping, trips per month.
Committed, regenerated, never hand-edited.

**011 · Freshness gate.** `make check-artifacts` byte-compares committed
artifacts against a fresh publish run and exits non-zero on drift. Wires the
review gate's reproducibility item to an exit code instead of a judgement.

## Phase 3 — Reference data

**012 · Station geography.** GBFS `station_information` per system, plus city
boundary and rapid-transit geometry from each city's open data portal. Feeds
coordinates, capacity, and transit proximity.

**013 · Weather.** Environment and Climate Change Canada daily climate data for
one representative station per city, pinned by station ID into the manifest.
Required by both the forecast model and any weather-conditioned metric.

## Phase 4 — Publish

**014 · Publish aggregates.** Typed JSON artifacts to `src/data/generated/`
under an enforced size budget. Per-city artifacts plus comparison artifacts. No
per-trip data ever reaches the browser.

## Phase 5 — Site foundation

**015 · App shell.** Nav, scrollspy, light and dark parity, the eyebrow and
hairline system, reveal motion. Design tokens are the Vancouver project's
verbatim; new components extend the language rather than departing from it.

**016 · Overview.** The headline comparison: three systems, one set of numbers,
with the common window stated where a first-time viewer will look.

## Phase 6 — Comparison surfaces

**017 · Trips over time and seasonality.** The core like-for-like series, plus
the seasonal shape that distinguishes a Montreal winter from a Vancouver one.

**018 · Active stations.** Station counts and network growth per system, on a
shared definition of what "active" means.

**019 · E-bike share.** Gated on 001. If a system cannot support it from open
data, it is absent and labelled, never estimated.

**020 · Membership mix.** Member versus casual, where each system publishes it.
Raw labels mapped explicitly, unmapped labels surfaced in the quality report.

## Phase 7 — Per-city depth

**021 · Station maps.** Per-city interactive map, MapLibre, themed basemap,
station detail on selection.

**022 · Station flows.** Origin-destination pairs and net flow per station — the
most visually distinctive surface in the Vancouver project, and the one that
gains the most from three cities side by side.

**023 · Forecast.** A ridership model per system trained on weather and calendar
features, with the out-of-range guard the Vancouver project already proved it
needs.

**024 · Operational signals.** Rebalancing pressure, dwell, and the derived
signals that read as operations rather than dashboard chrome.

## Phase 8 — Trust and ship

**025 · Methodology and data quality.** The generated methodology surface plus
the committed quality report, sources, licences, and limitations stated plainly.

**026 · Accessibility and responsive pass.** Keyboard, focus, contrast,
reduced-motion, and a cross-engine width sweep in both themes.

**027 · Deploy.** Static build to Cloudflare Pages, custom domain, and the
monthly-refresh runbook.

---

## Sequencing notes

- 001 blocks 005–008 and 019. Nothing in phase 2 should be written in detail
  before it lands.
- 009 blocks every cross-city surface in phase 6. Build it before, not after,
  the first comparison chart — retrofitting a comparability contract onto
  shipped charts means re-auditing all of them.
- 011 should land before the first committed artifact, so no artifact ever
  exists without a gate watching it.
- 013 blocks 023 only. It can slip without stalling the comparison work.
- Phases 6 and 7 are parallelizable across specs once 014 is stable; phase 8
  is strictly last.
