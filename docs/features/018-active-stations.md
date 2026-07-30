# Spec 018 — Active stations

## Status

Complete. Shipped 2026-07-28 in `0ddd43c`.

> **Written retrospectively on 2026-07-29**, from `0ddd43c`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## What shipped

Station counts and network growth per system on a shared definition: a station
is active if it saw a trip in the last six months **of that system's own data**,
not of the archive as a whole. The three systems have different end dates, and a
shared cutoff would silently retire the ones that publish less often.

## Corrected 2026-07-29, by spec 022's review

This chart was **wrong for Vancouver and Toronto**, and had been since it
shipped. `fact_trips` counted a station reached by name separately from the
same station reached by its published id, while `dim_station` merged them — so
the yearly active count double-counted every station in the eras keyed by name.

```
van-mobi   2024  275
           2025  550  -> 286      Vancouver's network appeared to DOUBLE
           2026  370  -> 268      and then collapse
tor-bikeshare  2016  257 -> 226
               2017  471 -> 324
```

Nobody questioned it because a rising line reads as growth. It was found only
when spec 022 divided the fact by the dimension and the arithmetic stopped
making sense. The fix is a materialised `station_identity` table both tables
join — see `docs/decisions.md`, "One station identity, materialised".

Montreal was unaffected: its era bridge was applied to both tables all along,
which is why the bug survived the bridging work that was specifically about
station identity.

## Known weakness, carried

"Active" by that definition is not "in service". Spec 021's review found 28
stations the maps drew as dormant that the live GBFS feed still lists. The word
on the maps was changed to "dormant"; the overview still says "active
stations", and the two figures differ because the map counts only positioned
stations above the trip threshold.

## Where the record is

- `pipeline/sql/40_model.sql` — `is_active`
- `docs/decisions.md`, 2026-07-29 entry on "dormant, not retired"
