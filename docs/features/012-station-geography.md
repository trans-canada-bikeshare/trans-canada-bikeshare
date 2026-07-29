# Spec 012 — Station geography

## Status

Complete. Shipped 2026-07-29 in `71b2d64`.

> **Written retrospectively on 2026-07-29**, from `71b2d64`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## Context

Spec 001 found that Montreal's trip files carry three different station key
spaces across their eras: 2014-2020 station codes, 2021 `emplacement_pk`, and
2022+ names. Counting distinct departure stations gave ~3,490 identities for a
network of about 1,200 docks. Every station-level surface was blocked on this.

## What shipped

**GBFS `station_information` per system**, pinned in each manifest with a
checksum and a `downloaded_at`, loaded into `gbfs_station`.

**`pipeline/sql/35_bridge.sql`** — the Montreal bridge. Four matchers in
descending confidence: era code to GBFS `short_name`, `emplacement_pk` to GBFS
`station_id`, name to GBFS name, then geographic proximity (within 50 m, with
the runner-up beyond 100 m so an ambiguous match is refused rather than
guessed).

Result: identities 3,490 to 1,776 against a live network of 1,107, with 88.1%
of Montreal trip volume resolving to a canonical station and the residue
counted in the quality report.

## Not built

City boundary and rapid-transit geometry, which the roadmap also lists under
this number. Transit proximity is not used by any shipped surface; it belongs
with spec 024.

## Where the record is

- `pipeline/sql/35_bridge.sql`, `pipeline/sql/40_model.sql`
- `docs/source-audit.md` — the three key spaces, and BIXI's reach beyond Montreal
