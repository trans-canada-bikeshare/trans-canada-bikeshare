# Data Pipeline

Offline tooling that acquires and processes the published open data for the
three tier-1 systems. The shipped site never runs any of this: the pipeline runs
locally and publishes small static artifacts that are committed.

Raw trip data and the warehouse are never committed. The manifests and the
generated aggregates are.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r pipeline/requirements.txt
```

## Commands

Only the test suite exists today. Each line below arrives with its spec, and
this list grows in the order the pipeline runs.

```bash
# Tests (no network)
.venv/bin/python -m pytest pipeline/tests

# spec 003  refresh manifests + download every pinned source, per system
# spec 004  verify the archive: gaps, short files, checksum mismatches
# spec 005  extract -> raw_trips, unified through per-city era maps
# spec 006  clean: typing, timestamps, hard drops, dedupe
# spec 007  conform: station identity, canonical month, quality flags
# spec 008  model: fact_trips + dim_system/station/date/membership
# spec 010  regenerate the committed data quality report
# spec 013  Environment and Climate Change Canada daily weather, per city
# spec 014  publish typed JSON aggregates under the size budget
```

## Gates

```bash
make check-manifest    # spec 003/004 — archive matches the manifests
make check-metrics     # spec 009 — no cross-city series for an unsupported metric
make check-artifacts   # spec 011 — committed artifacts match a fresh run
make check             # all three
```

These are stubs until their specs land, and each says so when run.

## Systems

| `system_id` | City | System | Open data since |
| --- | --- | --- | --- |
| `van-mobi` | Vancouver | Mobi by Rogers | 2017 |
| `mtl-bixi` | Montreal | BIXI | 2014 |
| `tor-bikeshare` | Toronto | Bike Share Toronto | 2014 |

One manifest and one column-era map per system. `system_id` is carried by every
fact and dimension row.

**Read `docs/source-audit.md` before writing any extraction code.** It records
the real headers per system per era, and the traps: Toronto renames every column
twice and reorders them once, `Trip  Duration` carries a double space, Toronto
dates are month-first, BIXI changes station key space twice and drops
`is_member` at 2022, and no system's period label can be trusted as its content
month.
