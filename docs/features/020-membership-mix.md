# Spec 020 — Membership mix

## Status

Complete. 2026-07-30.

## Context

Spec 001 established that Montreal carries `is_member` until the 2022 format
break and loses it after. Measured before building:

| system | trips labelled | shape |
| --- | --- | --- |
| tor-bikeshare | 100.0% | every year 2016-2026 |
| van-mobi | 98.9% | 100% except 2025 at 92.3% |
| mtl-bixi | 39.7% | **100% for 2014-2021, then 0% from 2022** |

**"Not published" would be false for Montreal.** It has 35,027,074 labelled
trips — eight complete years. That is a third case beyond supported and
unsupported, and the registry already anticipated it:
`membership_mix.mtl-bixi` carries `partial_until: "2021"` and
`display: "published to 2021 only"`, written in spec 009 and never used until
now.

The e-bike precedent does not transfer. There, Montreal publishes no bike-type
field in any era, so "not published" is exactly true and a blank column is
honest. Here a blank column would hide eight years of real data, and a full
column would imply a comparison that stops five years before the others do.

## Depends On

- Spec 008 — `dim_membership`. Complete: 93 labels mapped, **zero unmapped**.
- Spec 009 — the registry, including the unused `partial_until` field.

## Scope

- **Sources touched:** none new.
- **Cities touched:** all three, in two different roles. **Tier:** 1.
- **Published artifacts change:** **Yes** — new `membership.json`.

## Changes

1. **`membership.json`**: member/casual share per system per month for the two
   systems the registry marks supported, plus Montreal's real series in a
   separate `partial` key that ends where its data ends.
2. **The metric gate learns `partial_until`.** `guard()` and
   `check_metrics.py` currently know only supported/unsupported, so publishing
   Montreal at all would fail. A system with `partial_until` may appear, and
   `check-metrics` reports it distinctly from a fully supported one — the
   registry's own vocabulary, finally enforced.
3. **The chart states the asymmetry where it is read**, not only in
   methodology: Montreal's line stops in 2021 and the section says why.
4. **An unmapped label stops the pipeline.** Already true; this spec adds the
   test that would catch it regressing.

## What the build found

**Bike Share Toronto's member label dies inside an entire era.** Caught by the
test asserting every share is above zero, then traced to the source.

```
2016-01..2017-12   {Member, Casual}                74.6%, 78.0% member
2018-01..2023-12   {Annual Member, Casual Member}  81.8% -> 6.4%
2024-01..2026-03   {Member, Casual}                77.2%, 72.6%, 88.9%
```

"Annual Member" decays to nothing inside the middle era — 50,961 trips in March
2023, 12,226 in July, 138 in August, absent from September — while ridership is
at its yearly peak.

It is Toronto's defect and it cannot be recovered: the raw CSVs carry the same
header and column with the values decaying inside; CKAN reports the 2023
resource last modified 2024-01-09 and never corrected; no summary dataset
carries the counts; the readme documents only the 2014-2016 schemas. Imputing
from behaviour would be inventing data.

**The whole era is withheld**, with the vocabulary as the boundary rather than
a chosen month. See `docs/decisions.md`. What survives is coherent: on a
trip-weighted yearly basis Toronto reads 74.6%/78.0% before the break and
77.2%/72.6%/88.9% after, in the same range as Vancouver's yearly figures.
Vancouver's *monthly* share swings 59.2-93.4% with the seasons, so any
comparison has to state which basis it is on.

## Acceptance Criteria

- [x] Member/casual share per month for Vancouver and Toronto, one query, no
      per-city branch
- [x] Montreal's 63 months (2014-04..2021-11) shown on their own axis, labelled
      "published to 2021 only" from the registry
- [x] The share is derived from published integers in `memberShare()`, against
      **labelled** trips — an unlabelled trip is unknown, not casual
- [x] `partial_until` is enforced by `make check-metrics`, which reports
      `[partial: mtl-bixi to 2021]`; a system that is neither supported nor
      partial still fails, verified against `ebike_share`
- [x] Zero unmapped labels — publish aborts if one appears
- [x] Withheld months ship in `label_lost` with the basis for each, and the
      page explains the gap from that artifact
- [x] Publish budget 24.4% of 320 KB; 12 artifacts reproduce
- [x] 78 vitest, 60 pytest, typecheck 0, build 0, `make check` green
- [x] Rendered headed: 2 charts, nav entry, gap sentence reading "has a gap
      from 2018-01 to 2023-12", 0 console errors, 0 overflow

## Data Integrity Checklist

- [x] Provenance — no new sources; labels come from the trip files
- [x] Nothing guessed — an unmapped label stops the run; "Maintenance" maps to
      `operational`, not to member or casual, because it is neither. Nothing is
      imputed for the withheld era
- [x] Metrics defined identically for the two comparable systems
- [x] Like-for-like holds — Montreal is not a comparable column and the gate
      enforces it; Toronto's unreliable era is withheld rather than drawn
- [x] Copy derives from the data — the gap dates, month count and trip total in
      the note all read from `label_lost`
- [x] Row accounting — no ETL change, and the **21,182,323** trips in the
      withheld era remain in every other series; only their membership is
      unknown. (An earlier draft of this line said 7.8M, wrong by 2.7x, on
      the row-accounting line of all places. The site always rendered the
      right figure because it derives it.)
- [x] No raw data committed

## Out of Scope

- Pass-type detail. Vancouver publishes 87 named products; grouping them to
  member/casual is what makes the metric comparable at all, and the grouping is
  committed in `pipeline/mappings/membership_groups.csv`.
- Inferring membership for Montreal after 2022. There is nothing to infer from,
  and inventing one is the failure this project exists to avoid.

## Rollback

Single revert; `membership.json` becomes orphaned, which `check-artifacts` and
`check-metrics` both report.
