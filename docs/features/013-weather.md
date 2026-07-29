# Spec 013 — Weather

## Status

**Not built.** Planned.

## Context

Environment and Climate Change Canada publishes daily climate data per station.
The forecast (spec 023) cannot be built without it, and any weather-conditioned
metric depends on it.

## Intended scope

- **Sources:** ECCC daily climate data, one representative station per city,
  pinned by station ID into each manifest with a checksum like every other
  source.
- **Cities:** all three. **Tier:** 1.
- **Published artifacts change:** yes — a daily weather series per city.

## Intended changes

1. A representative station per city, chosen and justified in writing — airport
   stations have the longest records but are not always where the riding is.
2. Manifest entries with station ID, date range, and licence.
3. Daily temperature, precipitation, and snow depth, joined to `dim_date`.
4. Missing days accounted for explicitly. A gap in the climate record must not
   silently become a zero — that is the failure mode this project exists to
   avoid, and weather data has real gaps.

## Depends On

Nothing. It can be built at any time.

## Blocks

Spec 023 (forecast) only. It can slip without stalling comparison work.
