# Synthetic fixture archive

**Every byte in this directory is invented.** Nothing here was published by
BIXI, by Mobi by Rogers, by Bike Share Toronto, or by Environment and Climate
Change Canada. No source licence reaches it, no attribution is owed, and the
repository invariant that raw trip data never enters git is not in tension with
committing it — these are not trips that happened.

The markers are deliberate and load-bearing: every station is named
`FIXTURE …`, every station id sits outside the range its real system uses,
every coordinate is a made-up point inside the right city's bounding box, every
weather station carries a `FIXTURE` climate id, and every manifest URL is
`synthetic://`. If any of that ever appears in the real archive or on the site,
something has crossed a boundary it should not have.

What is *real* is the shape. The column headers are the ones the published
files actually carry — misspellings, doubled spaces, degree signs and all —
because `etl.plan` aborts on any header the era map does not know, and a
fixture spelling `Memebership type` correctly would prove nothing about the
map. The checksums in `manifests/` are true sha256 sums of the files beside
them, because `etl.require_sha` aborts on an entry without one and
`inventory.py` recomputes every one of them.

## Layout

```
archive/                     copied to <run>/data-raw by make check-fixture
  van-mobi/2024-01.csv … 2024-12.csv
  van-mobi/reference/{gbfs_station_information.json,weather_2024.csv}
  mtl-bixi/{2024-A.csv,2024-D.csv}          era A and era D
  tor-bikeshare/{2024-H1.csv,2024-H2.csv}   two column vocabularies
manifests/                   copied to <run>/manifests
generate_fixtures.py         how the bytes were made; regenerates them
```

The directory is `archive/` and not `data-raw/` for one dull reason: the
repository's `.gitignore` excludes `data-raw` at any depth, so a fixture tree
under that name could not be committed. `make check-fixture` copies it into a
scratch `<run>/data-raw` and points `BIKESHARE_DATA_ROOT` at the scratch tree,
which moves the archive, the warehouse and the manifests together.

## Scale and window

One calendar year, 2024, every day of it, roughly 800 trips per system —
2,401 rows in total across 16 files.

The year is not decoration. `forecast.reference_year` anchors the published
model on the most recent calendar year in which **every** system has all twelve
months covered by at least twenty usable days, and the incomplete-month rule
excludes a trailing month that is not observed on every one of its days. A
one-month fixture publishes fourteen artifacts and then aborts on the
fifteenth. So the fixture covers 2024-01-01 to 2024-12-31 with no gaps.

## What the fixtures exercise

| Surface | How |
| --- | --- |
| Era-map coverage | Two header vocabularies per system, taken verbatim from the real maps — including `Memebership type`, `Electric Bike`, `Return temperature (deg C)` and Toronto's doubled-space `Trip  Duration` |
| Date-order derivation (`15_dates.sql`) | Toronto's second half is `MM/DD/YYYY`; first fields never exceed 12, second fields do, so the file proves month-first from its own values and needs no declaration |
| Timezone derivation (`17_timezones.sql`) | Every file is under the 5,000-row threshold, so all land as `unknown` and are left as published — the deliberate no-guess branch |
| Epoch-millisecond ingest | Montreal era D publishes UTC milliseconds; the generator computes them *from* the intended `America/Montreal` wall clock, so a broken conversion moves the day |
| Hour-only source resolution | Vancouver's timestamps are all on `:00`, as Mobi's really are — `rebalancing.hourly_basis.on_hour_grid` reads 864 of 864 for Vancouver and 0 for the other two |
| Station identity bridge (`35_bridge.sql`) | Montreal names the same six docks two incompatible ways — four-digit codes in era A, station names in era D — joined only through the pinned GBFS feed, which carries `short_name` beside the id. `fixture_run.py` asserts the result is six docks, not twelve |
| Vancouver id-prefixed names | `0901 FIXTURE Cambie & 2nd`, split by `van_id`/`van_label` at conform |
| Membership mapping | Every label is one `pipeline/mappings/membership_groups.csv` carries; an unmapped one stops `publish.py` |
| Membership as a partial metric | Montreal's era D drops `is_member` exactly as BIXI's 2022 break does, so its published series covers January-June and stops — and it ships under `membership.partial`, never as a third comparable column |
| E-bike partial coverage | Toronto's first half carries `Bike_Model`, its second does not, so half the year fails publish's "most of the month must be classified" rule |
| Dwell | Vancouver and Toronto publish a bike id and the fleet stays where it was parked, so same-dock intervals exist; Montreal publishes none and `bike_dwell` refuses it |
| Weather + forecast | One synthetic ECCC year per city, with snow non-zero on some winter days and zero on others so the design matrix is not rank-deficient |
| Row accounting | One exact duplicate pair (Vancouver, the only deduplicated system), one row with no departure time (Toronto), one with no departure station (Montreal) — so every named drop reason is non-zero and the funnel closes over branches that were actually taken |
| Unterminated trips | ~1 in 60 Montreal era-D rows records no return at all |

## What they deliberately do not cover

- **XLSX, zips and nested zips.** The fixtures are CSV-only, and that is the
  point: `read_xlsx` needs DuckDB's `excel` extension, which is not bundled in
  the wheel and would be fetched from the network. A CSV-only tree runs with
  `BIKESHARE_ALLOW_EXTENSION_INSTALL=0` and an empty extension directory. The
  archive-unpacking paths (`_unpack`, `sheets_in`, the nested-zip recursion)
  are exercised by the real archive and by the unit tests, not here.
- **Encoding repair.** Every fixture file is valid UTF-8, so `ensure_utf8`
  makes no copy and `lines_repaired` is zero everywhere. Planting cp1252 bytes
  would mean committing a deliberately malformed file whose checksum then has
  to be maintained by hand.
- **The Toronto 2016 Excel date transposition**, the withheld
  2021-10..2023-12 membership era, `etl.EXCLUDED`, and Montreal's annual
  station snapshots. All are era-specific to years outside the fixture window.
- **Anything about the real numbers.** These fixtures test that the pipeline
  parses, accounts, resolves and publishes. They say nothing about whether
  Toronto's e-bike share is 22%. That is what the full-archive gates are for,
  and they stay local — see `docs/runbook.md`.

## Regenerating

```bash
.venv/bin/python pipeline/tests/fixtures/generate_fixtures.py
make check-fixture
```

The generator rewrites `archive/` and `manifests/` together, so the checksums
stay true. `pipeline/tests/test_fixtures.py` fails if they ever stop being.
