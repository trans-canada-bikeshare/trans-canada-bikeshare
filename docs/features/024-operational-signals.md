# Spec 024 — Operational signals

## Status

Built. 2026-07-30. Scope reshaped the same day at the owner's direction:
**Montreal is included in the comparable core.** It is the flagship system —
88M of the archive's 135.6M trips — and the first draft of this spec would have
excluded it because the scope was written around the one signal (per-bike
dwell) Montreal cannot support, rather than around the signals the trip data
supports for everyone.

## Scope

- **Sources touched:** none new. No ETL stage ran; both artifacts are new
  queries over the existing `fact_trips`.
- **Cities touched:** all three. **Tier:** 1 for rebalancing pressure, per-city
  detail for dwell.
- **Published artifacts change:** **Yes** — two new files, `rebalancing.json`
  (2.3 KB gzip) and `dwell.json` (1.2 KB gzip). Publish budget 25.0% of 320 KB,
  from 22.9% before.

## Changes

### 1. The registry split

`operational_signals` is gone. In its place:

- **`rebalancing_pressure`** — `comparable: true`, all three supported.
  Vancouver carries `qualified: true` and a note (see *Vancouver publishes only
  the hour*), the same shape Montreal already carries under `station_flows`.
  It also carries a `caveat` field, which the artifact copies and the page
  renders verbatim rather than paraphrasing.
- **`bike_dwell`** — `comparable: false`. `mtl-bixi` unsupported with the
  reason; `van-mobi` and `tor-bikeshare` supported, each with its era limits
  stated in the registry.

`make check-metrics` refused both artifacts until they were declared in
`ARTIFACT_METRIC`, which is what the gate is for. Nothing else in the
repository referenced the old key except `docs/features/009`, now amended.

### 2. Net flow by hour of day — three-city

Departures −1, returns +1, bucketed by the LOCAL hour of the event's own
timestamp. Linked trips only, so each system's twenty-four hours net to
**exactly zero** — the invariant `src/operations.test.ts` and
`pipeline/tests/test_operations.py` both pin, from opposite ends.

**Window: the common window, 2017 onward.** Decided from a measurement, not a
preference. The registry says a comparable metric defaults to the window all
three publish, and the alternative was the recent tail the rebalancing
reference values were measured over. Comparing candidate windows against
2025-onward, per system, as shares of linked trips:

| Window vs 2025+ | Montreal | Toronto | Vancouver |
| --- | --- | --- | --- |
| full archive | r=0.9928, max Δ 0.106pp | r=0.9956, 0.086pp | r=0.9922, 0.110pp |
| **common window 2017+** | r=0.9958, 0.058pp | r=0.9952, 0.087pp | r=0.9922, 0.110pp |
| recent 2024+ | r=0.9995, 0.023pp | r=0.9994, 0.040pp | r=0.9987, 0.048pp |

No hour of any system moves by more than 0.11 percentage points between the
widest and narrowest choice. The common window therefore buys 124 million
linked trips at no cost to the shape, and it is the same window for all three,
which is what like-for-like means here.

Plotted as a share of each system's own linked trips, for the reason
seasonality is: Montreal runs 8.8× Vancouver's volume and the shapes are the
comparison. The absolute per-average-day figures are in the note beneath, also
derived.

**What it says.** Every system drains through the working day and refills
overnight. The morning departure surge is the deepest hour in all three —
Montreal 07:00 (−197 bikes on an average day), Toronto and Vancouver 08:00
(−63, −14). The refill peak is **not** always the evening: Toronto's single
fullest hour is **09:00**, when the wave that left at 08:00 arrives. An earlier
version of the test asserted an evening peak for all three and failed on that
fact, which is why the page names every hour from the artifact.

### 3. Implied minimum daily rebalancing — three-city

Per station per day, net flow; summed over stations, |net| ÷ 2. Each event is
dated by its own timestamp — a departure by the day it left, a return by the
day it arrived — because that is what a dock sees.

**A day counts only if the system had at least one linked departure on it.**
Without that condition the archive's trailing edge invents days: Montreal's
data ends 2026-06-30, and 21 dates after it carry returns and no departures at
all. Those, with 2026-07-01 (617 returns against a ~3,000-move norm) at the
head, **diluted Montreal's mean by 3.8%**. Toronto has the same edge at
2026-04-01.

**Reconciliation with the reference values.** Measured exactly as the spec
described them — trips departing 2025 onward, no operating-day condition, no
incomplete-month exclusion — this pipeline reproduces the owner's figures to
the decimal:

| | reference | measured |
| --- | --- | --- |
| Montreal | ~2,812 /day | **2,812.2** |
| Toronto | ~1,418 /day | **1,418.0** |
| Vancouver | ~398 /day | **398.2** |

With the operating-day condition and the incomplete-month exclusion applied,
the same window gives Montreal **2,919.7**, Toronto **1,421.1**, Vancouver
**398.8** — Montreal's 3.8% being exactly the phantom days above.

The figure the site publishes is neither: it is **calendar 2025**, the latest
year the archive covers end to end for every system, so all three are read over
the same 365 days rather than over an eighteen-month tail that stops on a
different date in each city.

| 2025 | fewest moves a day | per 1,000 linked trips |
| --- | --- | --- |
| Montreal | 3,163 | 81 |
| Toronto | 1,587 | 74 |
| Vancouver | 405 | 126 |

**The per-1,000 form inverts the ranking**, which is the finding. Vancouver is
the smallest system and the most lopsided per trip, and every system's rides
have become less lopsided as it grew: Vancouver 153 → 126 (2017-2025), Montreal
112 → 81 (2015-2025), Toronto 97 → 74 (2017-2025), while absolute moves rose
with ridership.

**Five years are excluded from the yearly chart**, and the page says which and
why: the archive covers only part of Montreal 2014 and 2026, Toronto 2016 and
2026, and Vancouver 2026. A year the archive clipped cannot be told apart from
a year the system only operated part of — Montreal's 2014 opens in April
because BIXI opens in April, and its 2026 stops in June because the archive
does, and from inside the data those look identical. The flag is derived from
each system's own first and last trip, not listed.

### 4. Per-bike dwell — per-city detail

Return at a dock to that bike's next departure **from that same dock**. Chains
are built with `lead()` over `PARTITION BY system_id, bike_id, era`, ordered by
`departure_ts, return_ts, departure_station_id, return_station_id`, and three
cuts in that partition each prevent a specific wrong answer:

- **by system**, because **2,038 bike ids are shared between the Toronto and
  Vancouver namespaces**. The ids are each operator's own and nothing makes
  them globally unique.
- **by era**, because a chain that spans Vancouver's withheld 2021-2023 pairs a
  2020 return with a 2024 departure. Built without the era partition the same
  data yields intervals over a year long; the published p75 tops out at 20
  hours.
- **not by station**, which is the natural-looking cut and is wrong. Pairing a
  bike's return at a dock with its next departure *from that dock* skips every
  ride it took elsewhere in between. On Vancouver 2024 alone that reads a
  median of 7,200 s against the correct 10,800 s — a different quantity, not a
  noisier one. An interval whose next departure is from a different dock means
  something moved the bike; it is excluded and counted as `relocated`.

**Eras are measured, not listed.** A year is admitted only if ≥99% of its
trips name a bike, and contiguous admitted years form one era block. That
derivation reproduces the spec's stated limits exactly:

| System | admitted | withheld (bike-id coverage) |
| --- | --- | --- |
| Toronto | 2019-2026 | 2016, 2017, 2018 — 0.0% each |
| Vancouver | 2017-2020, 2024-2026 | 2021 (56.7%), 2022 (0.0%), 2023 (18.6%) |
| Montreal | none | every year, 0.0% |

Medians, 2025: **Toronto 54m 24s** (middle half 14m 4s to 4h 10m),
**Vancouver 3h 0m** (1h 0m to 13h 0m). Toronto's median has fallen every year
since 2019 (1h 58m). Relocated share of dock-to-dock intervals, 2025:
Vancouver 18.2%, Toronto 6.6% — which corroborates the per-trip rebalancing
figure from a completely independent direction.

### 5. Vancouver publishes only the hour

Found while checking why Vancouver's dwell quartiles were 3600 / 10800 / 50400
in **every year**.

**Mobi's published `Departure` and `Return` carry an hour and nothing finer.**
Confirmed at the source, not inferred: `data-raw/van-mobi/2025-01.csv` has
62,518 rows and **24 distinct time-of-day strings**. In the warehouse, 100% of
Vancouver rows have both timestamps exactly on the hour in every era except two
files — `2019-04` and `2025-05` — against 0.000% of Montreal's and 0.003% of
Toronto's. This is a source characteristic and **not a pipeline defect**: the
published `Duration (sec.)` column is intact and is what the duration metric
uses, so no existing figure on the site is affected.

Two consequences, both stated on the page from measured artifact fields rather
than asserted:

- **Hour-of-day.** Vancouver's buckets are the source's own hour labels. The
  bucketing is real — the share of Vancouver linked trips whose return hour
  differs from their departure hour is **27.5%**, against **25.8%** predicted
  by its own published durations, in line with Montreal (22.08 vs 22.68) and
  Toronto (23.84 vs 24.31) — but whether the label is a floor or a round is not
  stated by the source and cannot be recovered from the data, so the phase
  inside the hour is unknown. The registry marks Vancouver `qualified` under
  `rebalancing_pressure` and the page renders the measured share.
- **Dwell.** 96.1% of Vancouver's published intervals are exact multiples of an
  hour, so its quartiles are hour boundaries. The page says so and says to read
  each figure as ±1 hour. The qualitative claim survives the quantisation: a
  true median somewhere in 2-4 hours is still far above Toronto's 54 minutes.

The 2026-07-30 entry in `docs/decisions.md` records this. `docs/source-audit.md`
called Vancouver "minute precision" from a sample whose rows all read `0:00`,
which is consistent with both readings and settled neither.

### 6. `LineChart` gained a signed domain

Net flow by hour is the first series on this site whose **sign is the signal**.
The chart's domain ran 0..max, so negative values mapped below the baseline and
drew outside the plot box entirely. `signed` opens the domain symmetrically
about zero and draws the zero line at full rule weight; it is off by default
and the default path is unchanged in behaviour.

Two things the headed browser caught that no test had:

- The unsigned domain's `Math.max(1, …)` floor leaked into the signed one. Net
  flow peaks at 0.63% of a system's trips, so the axis read ±1.00% and the
  lines used two thirds of the plot. Fixed for the signed path only; the
  unsigned floor stays, since it also guards an empty series.
- The resting readout said **"latest published"** on a chart whose x axis is
  the hour of the day, where it resolves to 23:00 and means nothing of the
  kind. `restLabel` now lets a chart say what its own resting state is.

Both are pinned in `src/charts.test.tsx`.

## Acceptance Criteria

- [x] Net flow by hour, per system, local hour, linked trips only, over a
      stated window, with the window choice decided from a measurement and the
      measurement recorded above
- [x] Each system's twenty-four hours net to exactly zero — pinned in vitest
      from the artifact and in pytest from the warehouse
- [x] Implied minimum daily rebalancing published as a per-year series, with
      the trend visible and the years the archive clips excluded and named
- [x] The reference values reconcile: 2,812.2 / 1,418.0 / 398.2 against
      ~2,812 / ~1,418 / ~398, and the difference from the published figure is
      explained above rather than smoothed over
- [x] Every surface showing the bound says it is one: the registry carries the
      caveat, the artifact copies it, the stat label reads "fewest moves a
      day", the detail line under each figure opens "A lower bound, not a
      count", and the note beneath renders the caveat verbatim
- [x] Dwell in permitted eras only, derived from measured bike-id coverage and
      reproducing the spec's stated limits exactly
- [x] Montreal absent from dwell as a labelled gap with its reason, and present
      as a full column of the comparable metric in the same section
- [x] Bike ids never joined across systems (2,038 collide), events ordered by
      time within the chain, and a relocated bike excluded rather than counted
- [x] Registry split, `guard()` called for both metrics, both artifacts
      declared in `ARTIFACT_METRIC`
- [x] Every number in the new JSX derives from an artifact. No count,
      percentage, hour or city name is typed into the section
- [x] `npm test` (113), `npm run typecheck`, `npm run build` exit 0;
      `pytest pipeline/tests` 71 passed, 0 skipped; `make check-metrics`,
      `make check-manifest` and `pipeline/check_freshness.py` green — all 14
      artifacts reproduce
- [x] **Rendered output confirmed in a headed browser**, production build,
      `visibilityState === "visible"`: three lines and 72 points drawn, the
      zero line at full weight, the axis reading −0.63% / 0.00% / +0.63%, the
      three stat figures matching the artifact, the dwell columns rendering
      every era and every withheld year, and no horizontal overflow at 320 /
      768 / 1024 / 1360 px in either theme, with no console errors

## Data Integrity Checklist

- [x] Provenance — no new sources; both artifacts derive from `fact_trips`
- [x] Nothing guessed — a year whose bike-id coverage falls below the threshold
      is withheld and stated, never partially chained; a day the system did not
      operate is dropped and the reason recorded; a relocated bike is excluded
      rather than assigned a dwell
- [x] Metrics defined identically — one query per signal across all three
      systems, no per-city branch. Where a source differs (Vancouver's
      hour-only timestamps) the registry marks it `qualified` and the page
      states the measured share
- [x] Registry — split as the spec mandates; the gate refused both artifacts
      until declared
- [x] Artifacts reproduce — `check_freshness` matches all 14, and the twelve
      pre-existing files are byte-identical to before this change apart from
      `meta.json`'s volatile timestamp
- [x] Row accounting — dwell publishes `intervals`, `relocated` and
      `out_of_order` separately, so every dock-to-dock pair is accounted for;
      rebalancing publishes `days`, `months`, `abs_net` and `linked_trips` as
      exact integers and every ratio is derived in the browser
- [x] Copy derives from the data — every figure, hour, share and city name in
      the section reads from `rebalancing.json` or `dwell.json`
- [x] No raw data committed

## Not possible, and why

- **Live dock occupancy and actual rebalancing events.** Needs GBFS
  `station_status` sampled over time. No manifest pins it, no history exists,
  it cannot be backfilled. A future collector could start accumulating it, and
  until one does, every number here stays a lower bound.
- **Montreal dwell.** Nothing in the record identifies a bike across trips, in
  any era. Inferring identity from behaviour would be imputation.
- **Vancouver dwell finer than an hour.** The source does not publish it.

## Known limits, stated rather than fixed

- **A trip whose bike id is missing breaks the chain silently.** Vancouver's
  admitted years run 99.93-100% coverage, so roughly one interval in a thousand
  pairs a return with a departure two trips later. The threshold bounds this;
  it does not remove it.
- **`relocated` is not a count of rebalancing trips.** A trip missing from the
  archive looks exactly the same. The page says so.
- **The hourly profile mixes nine years of network growth.** The measurement
  above shows the shape barely moves, but it is an average over the window, not
  a snapshot of today.
- **Dwell has no upper cut.** A bike returned in November and next taken out in
  March is one interval of four months. That is real dwell rather than a
  defect, and the quartiles absorb it, but the mean would not and none is
  published.

## Rollback

Single revert. `rebalancing.json` and `dwell.json` orphan, which
`make check-artifacts` and `make check-metrics` both report, and the registry
returns to a single `operational_signals` key.
