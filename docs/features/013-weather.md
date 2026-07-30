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
5. **Attribution** in `LICENSE` and on the methodology page.

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

- [x] The ECCC licence and its required attribution are in every manifest and
      in `LICENSE`, with the three climate IDs
- [x] `make check-manifest` verifies them — file counts went 14/13/104 to
      27/26/114
- [x] `make check` green; 55 pytest (was 40), 68 vitest, typecheck 0, build 0
- [x] Nothing raw committed — 3.3 MB of CSV lives in `data-raw/`, gitignored

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

## Notes for the next run

ECCC exports a fixed-length calendar year, so the current year arrives padded
with rows for dates that have not happened. Keeping them would have reported
**624** missing days where the true figure is 146 — the loader drops rows with
no observation in any field.

## Rollback

Single revert plus removing the manifest entries. `weather_daily` disappears
and spec 023 becomes unbuildable, which is the stated dependency.
