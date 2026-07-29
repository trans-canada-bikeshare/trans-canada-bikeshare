# Spec 018 — Active stations

## Status

Complete. Shipped 2026-07-28 in `0ddd43c`.

> **Written retrospectively on 2026-07-29**, from `0ddd43c`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## What shipped

Station counts and network growth per system on a shared definition: a station
is active if it saw a trip in the last six months **of that system's own data**,
not of the archive as a whole. The three systems have different end dates, and a
shared cutoff would silently retire the ones that publish less often.

## Known weakness, carried

"Active" by that definition is not "in service". Spec 021's review found 28
stations the maps drew as dormant that the live GBFS feed still lists. The word
on the maps was changed to "dormant"; the overview still says "active
stations", and the two figures differ because the map counts only positioned
stations above the trip threshold.

## Where the record is

- `pipeline/sql/40_model.sql` — `is_active`
- `docs/decisions.md`, 2026-07-29 entry on "dormant, not retired"
