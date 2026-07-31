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

The pipeline is built end to end. These run in this order; `docs/runbook.md` is
the operational truth for a full rebuild or a monthly refresh.

```bash
# Tests (no network)
.venv/bin/python -m pytest pipeline/tests

.venv/bin/python pipeline/discover.py        # refresh manifests from the source pages
.venv/bin/python pipeline/weather.py         # derive the ECCC years from the trip window
.venv/bin/python pipeline/download.py        # ~20 GB, resumable, checksum-pinned
.venv/bin/python pipeline/inventory.py       # verify the archive: gaps, sizes, checksums
.venv/bin/python pipeline/census.py          # header layouts, to maintain the era maps
.venv/bin/python pipeline/etl.py --stage all # extract -> clean -> conform -> model
.venv/bin/python pipeline/publish.py         # typed JSON aggregates to src/data/generated/
.venv/bin/python pipeline/quality_report.py  # docs/data-quality-report.md
```

`forecast.py` is a library, not a script: `publish.py` calls it to fit one
weather-and-calendar model per system.

## Gates

```bash
make check-manifest    # spec 003/004 — archive matches the manifests
make check-metrics     # spec 009/009b — no cross-city series for an unsupported
                       #   metric, and no system-keyed artifact left undeclared
make check-artifacts   # spec 011 — committed artifacts match a fresh publish run
make check             # all of them
```

All of these are real and exit non-zero on a violation. `check-metrics` printed
"stub" and exited 0 until 2026-07-29 while `metric_support.json` claimed it was
enforced; spec 009b closed that, and `pipeline/tests/` plants a violation per
rule so a gate that cannot fail is caught by the suite.

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
