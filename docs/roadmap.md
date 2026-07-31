# v1 Roadmap

> **Status as of 2026-07-31.** Merged: **001–027** (004 folded into 003; 009
> completed by 009b). 135,598,303 trips over the full pinned archive; the site
> renders trips, seasonality, stations, e-bikes, membership, maps, flows,
> forecast and operational signals from committed aggregates, all gates real,
> live at bikeshare.adnanreza.com since 2026-07-30.
>
> **In progress: 028**, the first hardening release — the trust instruments
> themselves (quality report, licence files, self-descriptions) audited and
> corrected. **029–032** follow it.
>
> This block is written by hand and has been stale three times; when it
> disagrees with `git log` or `docs/features/README.md`, they win.

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

**004 · Inventory and archive verification.** ~~Separate spec~~ — **folded into
003 (2026-07-28).** `pipeline/inventory.py` shipped there: checksum and byte
verification, monthly gap detection for Vancouver and annual for the other two,
`PENDING` separated from `MISSING`/`CORRUPT`, wired to `make check-manifest`.
Splitting this into its own spec would have been padding, not work.

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

## Known gaps, carried

- ~~Montreal ships 35 physical docks as 70 identities~~ — **fixed 2026-07-29.**
  `35_bridge.sql` gained a fourth matcher for pk-era stations the live GBFS
  feed has since dropped, reached through the 2021 snapshot in
  `conformed_stations`. 53 more identities bridge (41 by name, 12 by position);
  duplicate-name pins fall from 71 in 35 groups to 2 in 1. The name match is
  distance-guarded, because `bridge_name` drops the parenthetical cross-streets
  and would otherwise have merged `Parc MacDonald (Earnscliffe / Dupuis)` with
  `Parc MacDonald (Clanranald / Isabella)` 321 m away — two docks at one park.
  Where the snapshot has no usable position (`Smith / Peel` at -1,-1) the full
  published names must match exactly instead.
  **Remaining:** one pair, `Drummond / Ste-Catherine`, 0 m apart.
- ~~A literal `"NULL"` station name is treated as a station~~ — **fixed
  2026-07-30** by the audit. `norm_key`/`norm_name` null the exact token; the
  identity is gone and its 7,947 trips carry a NULL station rather than a
  phantom one. Seven *positioned-id* stations whose latest trip label is the
  literal 'NULL' remain in `dim_station` under that name; none has
  coordinates, so none ships.
- **The name bridge can pick a mislabelled larger station.**
  `tor-bikeshare:name:hanlan's point ferry dock` (22 events) resolves to
  station 8030, which is Centre Island — because 8030's own last-writer-wins
  trip label is "hanlan's point ferry dock". `arg_max` by events protects
  against a small noisy station but not a large one. 22 events in 77M; noted
  because the mechanism could bite harder elsewhere.
- **`check-artifacts` cannot prove the warehouse rebuilds from raw.** It
  compares committed JSON against a publish run over the *existing* warehouse.
  Spec 022's review closed the load-bearing part by hand — `station_identity`
  and `fact_trips` were recomputed from the committed SQL and matched — but
  stages 10–30 remain unverified against raw by any command in this repo.

Recorded here rather than in a comment nobody reads, because each is a place
the project's own principles are not yet fully met.

- ~~`van-mobi` 2022-10 missing~~ — **recovered 2026-07-29** from the sister
  project's archive with an independently verified checksum, since Drive
  still 500s. 110,198 trips. Provenance recorded in the manifest.
- ~~~31,000 rows discarded before landing~~ — **fixed 2026-07-29 by repair,
  not by tolerance.** Line-level UTF-8 repair recovered all 31,315; nothing is
  discarded on encoding any more. The committed quality report went on
  describing this as an open gap until spec 028, because that paragraph was
  hardcoded prose rather than a derived figure — the loss was fixed in the
  code and left standing in the document that reports on the code.
- ~~`rows_landed` not reconciled against source record counts~~ — **fixed
  2026-07-29.** `raw_file_audit` compares them per file and aborts on
  mismatch. It runs inside extract, so a warehouse already built is not
  re-checked by any `make` target; **promoting it to a standing gate is spec
  029**, with the checksum-keyed caching that makes re-running extraction
  cheap enough to be routine.
- ~~Montreal station identity spans three key spaces~~ — **closed
  2026-07-29.** `pipeline/sql/35_bridge.sql` reconciles them through GBFS;
  identities 3,490 -> 1,776 against a live network of 1,107, with 88.1% of
  Montreal trip volume resolving to a canonical station and the residue
  counted in the quality report.
- ~~The trips chart plots a 26:1 range on one linear axis~~ — **fixed
  2026-07-29.** Small multiples, each panel scaled to itself; seasonality
  replotted as share of each system's own year.

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
