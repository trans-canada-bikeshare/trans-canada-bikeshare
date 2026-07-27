# Decisions

A short log of choices that shape the project, oldest first. Feature specs
live in docs/features/ once implementation starts, following the same
NNN-name.md convention as the Vancouver project.

## 2026-07-26: Name

**Trans-Canada Bikeshare.** Coined here; at the time of writing there were no
web or GitHub uses of the name. "Trans-Canada" follows the national
convention (Highway, Trail) rather than "Trans Canadian". The descriptive
form ("comparing Canada's bike share systems") lives in taglines, not the
name. Considered and passed on: "Trans Canadian Bikeshare Systems" (long,
clinical ending), "Canadian Bike Share Systems" (generic, hard to own).

## 2026-07-26: Separate repository from mobi-transit-explorer

The Vancouver project stays untouched as the single-city deep dive: it is
live, stable, personally voiced, and built around the Mobi Data License
Agreement. This project copies its patterns (manifest, era maps, staged
DuckDB SQL, freshness gate, contract tests, quality report, derived copy)
but designs for multiple systems from the first commit: a system dimension
in the star schema, one manifest and one era map per city, per-city publish
artifacts plus comparison artifacts. No shared library between the repos;
the READMEs cross-reference instead.

## 2026-07-26: Tier 1 before tier 2

v1 compares the three docked systems with per-trip OD data (Vancouver,
Montreal, Toronto). Calgary and Edmonton (dockless micromobility, anonymized
locations, no stations) arrive in v2 as a visibly separate panel, because
presenting fuzzed scooter trips as comparable to dock-to-dock rides would
undermine the honesty the methodology depends on.

## Next

Spec 001: download one real month from BIXI and Bike Share Toronto, read the
actual headers, and write a verified column-by-column feasibility map
(especially: e-bike flags, membership fields, station coordinates, timestamp
precision) before any pipeline code.
