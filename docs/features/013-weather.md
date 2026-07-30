# Spec 013 — Weather

## Status

Complete. 2026-07-29.

## Context

Environment and Climate Change Canada publishes daily climate data per station.
[Spec 023](023-forecast.md) cannot be built without it, and it is the only way
to condition any existing series on weather.

This is the **first new external source since spec 003**, so it carries new
licence and attribution obligations. Those are stated in the manifest and in
`LICENSE` the same way every other source's are.

**Airport stations**, decided with the owner 2026-07-29. They have the longest
continuous records and are the conventional choice; a downtown station sits
closer to the riding but has shorter, patchier coverage. Verified reachable and
covering each city's full trip window before the spec was written:

| City | ECCC station | ID | Climate ID | First trip year checked |
| --- | --- | --- | --- | --- |
| Vancouver | VANCOUVER INTL A | 51442 | 1108395 | 2017 — 361/365 days with a mean temp |
| Montreal | MONTREAL INTL A | 51157 | 7025251 | 2014 — 365/365 |
| Toronto | TORONTO INTL A | 51459 | 6158731 | 2016 — 366/366 |

Vancouver's four missing days in 2017 are the point: **the record has real
gaps, and a gap must never become a zero.** A day with no observation stays
absent and is counted, never imputed — the same rule the trip pipeline follows.
0 °C is a common, legitimate value here, so a zero-fill would be
indistinguishable from data.

## Depends On

- [Spec 003](003-manifests-and-downloaders.md) — manifest and downloader. The
  ECCC years land as `reference` entries, which already carry checksum pinning
  and drift refusal, so the downloader itself needs no change.

## Scope

- **Sources touched:** **new** — ECCC daily climate, one station per city, one
  file per station-year.
- **Cities touched:** all three. **Tier:** 1.
- **Published artifacts change:** **No.** Like
  [spec 012](012-station-geography.md), this is reference data: it lands in the
  warehouse and is accounted for in the quality report.
  [Spec 023](023-forecast.md) is what publishes from it.

## Changes

1. **Manifest entries** per city: a `weather_station` block recording station
   ID, climate ID, published name and position, and the ECCC licence; plus one
   pinned `weather_<year>` reference entry per year of that city's trip window.
2. **Discovery** derives the year range from the trip data's own window rather
   than a hardcoded list, so a new trip year pulls its weather automatically.
3. **A `weather_daily` table** keyed by `(system_id, date_key)`: mean, max and
   min temperature, total precipitation, total snow, and snow on ground.
4. **Gaps are counted, not filled.** A missing observation lands as NULL and
   the count per city per year reaches the quality report.
5. **Attribution** in `LICENSE`, in each manifest, and in the site's sources
   note — in the wording the licence dictates, which is *"based on
   Environment and Climate Change Canada data"*, not a paraphrase.

## Acceptance Criteria

- [x] Every ECCC file is pinned by SHA-256 in the manifest — 36 files, and
      they inherit spec 003's drift refusal because they are ordinary
      `reference` entries; the downloader needed no change
- [x] The year range derives from the manifest's own trip periods, not a
      literal. Vancouver 2017-2026, Montreal and Toronto 2014-2026
- [x] `weather_daily` holds 12,670 days. A day ECCC does not report stays
      absent or NULL — no zero-filling, no interpolation
- [x] Coverage reaches the quality report, counted **against each system's own
      trip window** because weather outside it conditions nothing:

      | system | window days | with a row | no row | row but no mean temp |
      |---|---|---|---|---|
      | mtl-bixi | 4,460 | 4,456 | 4 | 54 |
      | tor-bikeshare | 3,735 | 3,734 | 1 | 23 |
      | van-mobi | 3,469 | 3,464 | 5 | 78 |

- [x] The ECCC licence and its required attribution are in every manifest, in
      `LICENSE`, and in the site's sources note, with the three climate IDs.
      **The licence was named wrong in the first draft** — see *Changes made
      during the build*
- [x] `make check-manifest` verifies them — file counts went 14/13/104 to
      27/26/114
- [x] `make check` green; 55 pytest (was 40), 68 vitest, typecheck 0, build 0
- [x] Nothing raw committed — 2.2 MB of CSV lives in `data-raw/`, gitignored

## Data Integrity Checklist

- [x] Provenance — every weather file has a manifest entry with a checksum and
      a stated licence
- [x] Nothing guessed — no `fillna`, no forward-fill, no interpolation. A test
      asserts NULLs *survive* the load, because the failure is silent in the
      other direction: real 0 °C days are common, so a filled gap could not be
      found by looking for zeros
- [x] Metrics defined identically — the same station type, fields and units for
      all three cities
- [x] Row accounting — window days versus observed days, per city, in the
      quality report
- ~~Artifacts reproduce~~ — n/a, publishes nothing to `src/data/generated/`
- [x] Attribution ships with the data
- [x] No raw data committed

## Testing

15 pytest cases. Beyond the year derivation and manifest pinning, the ones that
matter are the physical checks a shifted or mis-parsed column would fail:
min never exceeds max, precipitation is never negative, temperatures stay
within −50…45 °C, one row per system per day, and every retained row carries at
least one observation so ECCC's calendar padding is not stored as data.

The zero-fill check is inverted deliberately. Real 0 °C days are common, so a
filled gap cannot be found by looking for zeros — the test asserts that NULLs
*exist*, since any fill would have removed them all.

## Out of Scope

- Hourly data. The forecast is daily; hourly would be ~24x the volume for no
  gain at this granularity.
- A weather surface on the site. This is reference data; spec 023 publishes.

## Changes made during the build

- **The licence was misidentified.** The first draft named the "Environment and
  Climate Change Canada Data Servers End-use Licence" with a URL and a
  checked-on date. That instrument is real but governs MSC Datamart/GeoMet, not
  `climate.weather.gc.ca`; its name appears nowhere on the linked page, and the
  attribution string invented with it matched neither instrument. The governing
  licence is the **Licence Agreement for Use of Environment and Climate Change
  Canada Data**, it requires the exact words *"based on Environment and Climate
  Change Canada data"*, and it carries **redistribution restrictions no other
  source here has**. Recorded in `docs/decisions.md`, because the error
  understated the obligations one spec before 023 publishes under them.
- **The site did not carry the attribution** although `LICENSE` said it did.
  Added, and a test now pins the literal string.
- **The current year is pinned but `volatile`.** ECCC is still writing 2026, so
  its checksum moves daily; refusing it would have made `--accept-changes`
  routine and stripped the flag of meaning for the closed years. Only the open
  year may advance.
- **The quality report's "row but no mean temp" column double-counted the "no
  row" column** — a bare `IS NULL` over a LEFT JOIN also matches days with no
  row. Published 54/23/78 where rows-present-but-null is 50/22/73; the two
  columns could not be added without counting 10 days twice.
- **The loader now asserts the CSV's own Climate ID matches the manifest.** A
  mis-set `stationID` in the bulk URL was the one error this ingest could not
  otherwise detect — it would have silently stored another city's weather.
- The tests gained the only assertion that compares the warehouse to its
  source, plus `min <= mean <= max`, which is the sharpest available detector
  of a shifted column.

## Notes for the next run

ECCC exports a fixed-length calendar year, so the current year arrives padded
with rows for dates that have not happened. Keeping them would have reported
**624** days with no mean temperature where the table-wide figure is **146** —
the loader drops rows carrying none of the six stored measures.

Two figures are easy to confuse and both are right: **146** is table-wide rows
with a NULL mean temperature; **155** is in-window days with no mean
temperature (54+23+78). 624 = 146 + 478 padding rows.

For [spec 023](023-forecast.md):

- `temp_mean_c` is exactly `(min+max)/2` on all 12,670 rows — ECCC's own
  definition. It carries no information beyond the other two.
- `snow_ground_cm` is NULL on 96% of Vancouver's days, 75% of Toronto's and
  66% of Montreal's. NULL means **not reported**, never "no snow". Treating it
  as 0 is precisely the substitution this spec exists to prevent.
- The airport stations sit 10.6 km (Vancouver), 13.5 km (Montreal) and
  **19.3 km (Toronto)** from each system's trip-weighted centroid. Pearson is
  the weakest proxy of the three — colder and snowier than the lake-moderated
  core where Bike Share Toronto actually operates. Worth stating wherever a
  weather-conditioned number appears.

## Rollback

Single revert plus removing the manifest entries. `weather_daily` disappears
and spec 023 becomes unbuildable, which is the stated dependency.
