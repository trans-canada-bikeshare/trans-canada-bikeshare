# Trans-Canada Bikeshare

Canada's bike share systems, measured the same way.

One pipeline, one set of definitions, one site: trips, active stations, e-bike
share, station flows, weather-driven forecasts, and operational signals for
Canada's public bike share systems, computed from each system's published
open data and compared like for like where the sources support it — and
labelled per-city where they do not.

Sister project to [Mobi Transit Explorer](https://mobi-transit-explorer.adnanreza.com)
([source](https://github.com/adnanreza/mobi-transit-explorer)), the single-city
deep dive this project generalizes. Built and maintained by
[Adnan Reza](https://adnanreza.com).

## Status

**Live at [bikeshare.adnanreza.com](https://bikeshare.adnanreza.com).** The
pipeline ingests every year all three systems publish — 135.6M trips over a
~20 GB pinned archive — into a DuckDB star schema, and the site renders
trips, seasonality, stations, e-bike share, membership, interactive maps,
station flows, forecasts and operational signals from small committed
aggregates. Deployed 2026-07-30 to Cloudflare Pages (spec 027); the owner
decisions that gated deployment are recorded in `docs/runbook.md` and
`docs/decisions.md`.

To reproduce it, or to fold in a new month of data, follow
[`docs/runbook.md`](docs/runbook.md) — one known caveat there: Vancouver's
2022-10 source file currently 500s at origin, so a clean-room rebuild needs
the archived copy the manifest documents. The spec-by-spec record lives in
[`docs/features/`](docs/features/) and the choices that bind the work in
[`docs/decisions.md`](docs/decisions.md).

## Planned scope

**Tier 1, the like-for-like comparison (v1):**

| City | System | Open trip data since |
| --- | --- | --- |
| Vancouver | Mobi by Rogers | 2017 |
| Montreal | BIXI | 2014 |
| Toronto | Bike Share Toronto | 2017 |

Three docked systems with per-trip origin and destination records. Trips,
seasonality, duration, stations, flows, forecast and rebalancing pressure are
three-city comparisons; e-bike share and membership mix are published for
Vancouver and Toronto with Montreal labelled not-published; per-bike dwell is
era-limited and not comparable. `pipeline/mappings/metric_support.json` is the authority, and
`make check-metrics` fails a cross-city series the registry does not support.

**Tier 2, the dockless panel (v2):** Calgary and Edmonton publish shared
micromobility (e-scooter and e-bike) trip data. Locations are anonymized and
there are no docks, so these cities get a separate, clearly labelled panel
for the metrics that translate (trips, seasonality, vehicle mix). They are
not presented as like-for-like columns next to the docked systems.

## Principles (carried from the Vancouver project)

- A checksum manifest pins every source file; downloads are reproducible.
- Schema drift is mapped explicitly per source; unknown headers stop the
  pipeline. Nothing is guessed silently.
- Every row dropped or flagged is accounted for in a generated quality report.
- A release gate byte-compares committed artifacts against a fresh pipeline
  run before anything ships.
- Site copy derives from the data window. Prose can lag the data but never
  lie about it.
- Every visual encoding says what it means, somewhere a first-time viewer
  will look.
- Raw trip data is never committed. Only small generated aggregates ship.

## Licence

Code is MIT — see [`LICENSE`](LICENSE), which carries the MIT text and nothing
else. Generated data artifacts remain governed by each source system's open
data licence, credited in the manifest and on the site; every source term,
required attribution string and redistribution restriction is recorded in
[`DATA-LICENSES.md`](DATA-LICENSES.md).
