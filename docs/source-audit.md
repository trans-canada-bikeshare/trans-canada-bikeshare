# Source Column Audit

Spec 001. What the three systems actually publish, read from the real files.

Every claim is tagged **[observed]** (read from a real file in this audit),
**[carried]** (observed by the Vancouver project's pipeline across its full
archive — stronger evidence than a spot check), or **[inferred]** (not yet
verified; treat as a hypothesis).

Read date: 2026-07-28.

---

## Verdicts

| README metric | Vancouver | Montreal | Toronto | Like-for-like? |
| --- | --- | --- | --- | --- |
| Trips over time | ✅ | ✅ | ✅ | **Yes** |
| Seasonality | ✅ | ✅ | ✅ | **Yes** |
| Trip duration | ✅ | ✅ | ✅ | **Yes** — derived for BIXI 2022+ |
| Active stations | ✅ | ⚠️ | ✅ | **Qualified** — the GBFS bridge below is designed but **NOT BUILT**; Montreal's counts span three unbridged key spaces |
| Station flows | ✅ | ⚠️ | ✅ | **Qualified** — BIXI has unterminated trips |
| **E-bike share** | ✅ | ❌ | ✅ | **No** — Montreal never publishes bike type |
| **Membership mix** | ✅ | ⚠️ 2014–21 | ✅ | **No** — Montreal drops it at 2022 |
| Weather forecast | ✅ | ✅ | ✅ | **Yes** — ECCC covers all three |
| Operational signals | ✅ | ⚠️ | ✅ | **Qualified** — no bike ID for Montreal |

**Two headline metrics cannot be shown as three-city comparisons.** E-bike share
and membership mix are Vancouver-and-Toronto only. No amount of engineering
recovers a column the publisher does not ship. See [Consequences](#consequences).

---

## Vancouver — Mobi by Rogers

`https://www.mobibikes.ca/en/system-data`. One `ALL of 2017` workbook, then
monthly from 2018-01. XLSX / CSV / Google Sheets via Google Drive.

**[carried]** 34 distinct raw headers across 31 layouts over 102 files, unified
to `departure`, `return`, `departure_station`, `return_station`, `bike`,
`electric_bike`, `membership`, `distance_m`, `duration_s`, `departure_temp`,
`return_temp`, `stopover_s`, `stopover_count`. Dropped by explicit decision:
`Account`, `Manager`, the slot pair, the battery-voltage pair.

The richest of the three schemas — the only one with distance, per-trip
temperature, and stopover behaviour.

| Canonical field | Column |
| --- | --- |
| timestamps | `Departure` / `Return` — five formats across eras |
| stations | `Departure station` / `Return station` — name-prefixed IDs |
| duration | `Duration (sec.)` |
| distance | `Covered distance (m)` — unique to Vancouver |
| membership | `Membership type` / `Memebership type` / `Formula` — 85 raw labels |
| bike id | `Bike` |
| **e-bike** | `Electric bike` / `Electric Bike` / `Electric` — **present** |

### Direct verification **[observed]**

One real file downloaded in full — period `2025-01`, 8,043,465 bytes:

```
Departure,Return,Bike,Electric bike,Departure station,Return station,Membership type,Covered distance (m),Duration (sec.),Departure temperature (C),Return temperature (C),Stopover duration (sec.),Number of stopovers
2025-02-01 0:00,2025-02-01 0:00,30575,TRUE,0069 7th & Granville,0310 Jervis & Robson,UBC Inclusive Corporate Pass,3857,760,0,3,0,0
```

All thirteen headers match the carried map exactly. `Electric bike` is present
and carries `TRUE` — e-bike derivability for Vancouver is now observed, not
inherited. Station format `0069 7th & Granville` confirms the name-prefixed ID.

Its SHA-256 is `eaa0f34e3bb596e47f37313b578d6bbdef17da7d3043482a0c765a1ec68862bd`
and byte size 8,043,465 — **both identical to the Vancouver project's pinned
manifest entry.** An independent download three weeks later reproduces the
source byte for byte, which is exactly the property the manifest exists to
guarantee.

Two things the download surfaced that the carried map does not capture:

1. **Vancouver timestamps here are minute precision** — `2025-02-01 0:00`, no
   seconds. Same floor as Toronto's pre-2025 files.
2. **The period label is not the content month.** The file published as
   `2025-01` contains rows dated `2025-02-01`. The Vancouver project handles
   this by deriving a canonical departure month at conform rather than trusting
   the filename — spec 007 must do the same, for all three cities.

Quirks **[carried]**: the page misspells `Novemeber 2021`; summer 2023 files
carry invalid UTF-8 in `0099 šxʷƛ̓ənəq Xwtl'e7énḵ Square`; per-trip temperatures
degrade to 0-sentinels after mid-2025 — and `Departure temperature (C)` already
reads `0` in this January 2025 file.

---

## Montreal — BIXI

`https://bixi.com/en/open-data/`. Annual ZIP per year, 2014–2026.
**Four eras**, and the 2022 break costs real fields.

### Era A — 2014 to ~2019 **[observed: 2014]**

`Historique-BIXI-2014.zip` → monthly `BixiMontrealRentals2014/OD_2014-MM.csv`.

```
start_date,start_station_code,end_date,end_station_code,duration_sec,is_member
2014-04-15 00:01,6209,2014-04-15 00:18,6436,1061,1
```

Timestamps are **minute precision**, no seconds.

### Era B — 2020 **[observed]**

`Historique-BIXI-2020.zip` → single `OD_2020.csv` + `stations.csv`. Same six
columns as era A, but timestamps gain **seconds**: `2020-04-15 06:00:04`.

### Era C — 2021 **[observed]**

`Historique-BIXI-2021.zip` → `2021_donnees_ouvertes.csv` + `2021_stations.csv`.
Station keys are **renamed and renumbered**:

```
start_date,emplacement_pk_start,end_date,emplacement_pk_end,duration_sec,is_member
2021-06-29 17:46:28.653,10,2021-06-29 19:33:25.700,10,6417,0
```

Timestamps gain **milliseconds**. Codes go from 4-digit (`6209`) to small
integers (`10`) — a different key space, not a renaming of the same values.

### Era D — 2022 onward **[observed: 2022, 2025]**

One unsorted CSV for the entire year — 1.48 GB for 2022, 2.80 GB for 2025.

```
STARTSTATIONNAME,STARTSTATIONARRONDISSEMENT,STARTSTATIONLATITUDE,STARTSTATIONLONGITUDE,ENDSTATIONNAME,ENDSTATIONARRONDISSEMENT,ENDSTATIONLATITUDE,ENDSTATIONLONGITUDE,STARTTIMEMS,ENDTIMEMS
St-Urbain / René-Lévesque,Ville-Marie,45.507838,-73.563136,Mansfield / Ste-Catherine,Ville-Marie,45.5013987,-73.5717863,1653343831220,1653344213703
```

| Field | Era A–C | Era D |
| --- | --- | --- |
| timestamps | local naive, min → sec → ms | **epoch milliseconds** |
| stations | integer key | **name string only** |
| coordinates | separate stations file | **inline per trip** |
| borough | — | `*ARRONDISSEMENT` |
| duration | `duration_sec` | **derivable** from the two timestamps |
| membership | `is_member` 0/1 | **absent — lost at the break** |
| bike id / e-bike | absent | absent |

**Unterminated trips.** Some era-D rows have blank `ENDTIMEMS`, end station, and
end coordinates, with a valid start. In 213,684 rows scanned from the head of
the 2025 file, 6,008 (2.8%) were unterminated **[observed]**. **Do not quote
that rate as the year's.** The file is not randomly ordered and unterminated
rows cluster heavily toward the front — an earlier 45,212-row scan gave 13.3%,
and the rate fell as the scan grew. Quantifying it needs a full pass, which
belongs to spec 006. What is established: **unterminated trips exist, they are
not rare, and every Montreal flow and duration metric must exclude them
explicitly and say so.**

Also **[observed]**: era-D files are **not sorted by time** — the first 2,000
rows of the 2025 file span 2025-01-15 to 2025-10-17, and a row with a
2026-01 start appears in the 2025 file. Anything assuming order will be wrong.

---

## Toronto — Bike Share Toronto

CKAN `bike-share-toronto-ridership-data` on `open.toronto.ca`. Annual ZIP per
year, 2014–2026, refreshed monthly. **Four layouts observed**, and every column
is renamed at least once.

| Era | File granularity | Header |
| --- | --- | --- |
| **2017** | quarterly, `2017 Data/` | `trip_id,trip_start_time,trip_stop_time,trip_duration_seconds,from_station_id,from_station_name,to_station_id,to_station_name,user_type` |
| **2018** | quarterly, `bikeshare2018/` | same nine columns, **reordered** — `trip_id,trip_duration_seconds,from_station_id,trip_start_time,from_station_name,trip_stop_time,to_station_id,to_station_name,user_type` |
| **2020, 2022** | monthly | `Trip Id,Trip  Duration,Start Station Id,Start Time,Start Station Name,End Station Id,End Time,End Station Name,Bike Id,User Type` |
| **2025** | monthly | `Trip_Id,Trip_Duration,Start_Station_Id,Start_Time,Start_Station_Name,End_Station_Id,End_Time,End_Station_Name,Bike_Id,User_Type,Bike_Model` |

Three things in that table will break a naive loader **[observed]**:

1. **`Trip  Duration` carries a double space** in the 2020/2022 layout. It must
   be mapped verbatim, not trimmed into `Trip Duration`.
2. **2018 keeps the 2017 column names but changes their order.** A positional
   reader survives 2017→2018; a lazy one that assumes order is stable across
   the rename at 2020 does not.
3. **Naming convention changes twice** — `snake_case` → `Title Case` →
   `Title_Snake` — and `from_/to_` becomes `Start_/End_`.

**Timestamp formats.**

| Era | Format | Precision |
| --- | --- | --- |
| 2017, 2018 | `1/1/2017 0:00` | **minute** |
| 2020, 2022 | `01/24/2022 08:41` | **minute** |
| 2025 | `2025-06-01 00:01:56` | **second** |

**Month-first, confirmed empirically [observed]:** in the 2022-01 file — which
covers January only — the first date field is pinned to `01` while the second
ranges 1–24. `01/24/2022` settles it. This mattered: `01/01/2022` alone is
ambiguous, and guessing wrong silently transposes days and months for eleven
months of every year.

**`User_Type` labels drift [observed]:** `Member` in 2017; `Annual Member` /
`Casual Member` in 2018 and 2022; `Member` / `Casual` in 2025. Needs an
explicit label map, like Vancouver's 85.

**`Bike_Model`, July 2025, 91,585 rows [observed]:**

| Value | Trips | Share |
| --- | ---: | ---: |
| `ICONIC` | 71,629 | 78.2% |
| `EFIT` | 11,251 | 12.3% |
| `EFIT G5` | 8,705 | 9.5% |

`EFIT` and `EFIT G5` are the e-bikes — **e-bike share ≈ 21.8%** in that sample,
consistent with the City's reported 17% across all of 2024.

Station coordinates are absent from every era; GBFS is the only source.

---

## Station identity bridge

The one genuinely hard modelling problem, and it resolves cleanly **[observed]**.

BIXI's GBFS carries **both** legacy key systems at once:

```
station_id=1   short_name=6001   Drummond / de Maisonneuve
station_id=2   short_name=6002   Ste-Catherine / Dézéry
```

| BIXI era | Trip-file key | Joins to |
| --- | --- | --- |
| 2014–2020 | `start_station_code` = 6209, 6436, 6212, 6250 | GBFS **`short_name`** — all four confirmed present |
| 2021 | `emplacement_pk_start` = 10, 188 | GBFS **`station_id`** — absent from `short_name` |
| 2022+ | station **name** only | name match, with drift risk |

So Montreal station identity is **recoverable** across all eras, using a
different join key per era plus name matching for 2022+.

> **Status 2026-07-29: BUILT** (`pipeline/sql/35_bridge.sql`). Three matchers,
> strongest first — the code and pk key spaces join to GBFS exactly, era-D
> names match GBFS names, and whatever the name misses is resolved by position
> when the nearest dock is within 50 m and the runner-up is over 100 m away, so
> two adjacent stations cannot merge. Montreal's identities fall from ~3,490 to
> 1,776 against a live network of 1,107, and **88.1% of Montreal trip volume**
> resolves to a canonical station. The residue is mostly stations retired
> before the current GBFS snapshot, which a current-state feed cannot know
> about; those keep their era-local identity and are counted in
> `docs/data-quality-report.md` rather than dropped. That is a spec 007 concern and
must be counted in the quality report — a name that fails to match is a
silently dropped station, exactly the kind of thing this project promises not
to do.

## Reference data

**GBFS `station_information` [observed]** — all three are GBFS with different
vendor extensions over a common core of `station_id`, `name`, `lat`, `lon`,
`capacity`:

| System | Stations | Notable extras |
| --- | ---: | --- |
| Mobi (Fifteen) | 261 | `vehicle_type_capacity`, `is_charging_station`, `is_virtual_station` |
| BIXI | 1,107 | `short_name`, `external_id`, `is_charging`, `electric_bike_surcharge_waiver` |
| Bike Share Toronto | 1,055 | `physical_configuration`, `altitude`, `obcn`, `groups`, `nearby_distance` |

Feeds: `gbfs.kappa.fifteen.eu/gbfs/2.2/mobi/en/station_information.json` ·
`gbfs.velobixi.com/gbfs/2-2/en/station_information.json` ·
`toronto.publicbikesystem.net/customer/gbfs/v2/en/station_information`

All three are **current-state only** — a station retired before today is not in
the feed, so historical coverage comes from the trip files themselves.

**ECCC daily climate [observed]** — same bulk endpoint the Vancouver project
uses, returning `Date/Time`, `Mean Temp (°C)`, `Total Precip (mm)`:

| City | stationID | Station name |
| --- | --- | --- |
| Vancouver | 888 | VANCOUVER HARBOUR CS **[carried]** |
| Toronto | 31688 | TORONTO CITY |
| Montreal | 30165 | MONTREAL/PIERRE ELLIOTT TRUDEAU INTL |

Vancouver and Toronto are downtown. **Montreal's is the airport, ~20 km west of
the network core** — the Vancouver project deliberately chose a downtown station
"matching where most riding happens", and 30165 does not meet that bar. A
downtown Montreal station should be chosen in spec 013.

## Licences

| System | Status |
| --- | --- |
| Vancouver | Mobi Data License Agreement — non-commercial analysis **[carried]**, re-confirm at 003 |
| Montreal | **None stated** **[observed]** — the open-data page carries no licence, terms, or attribution text |
| Toronto | **Open Government Licence – Toronto** **[observed]** — portal-wide default, permits commercial use |

Toronto requires this attribution verbatim: *"Contains information licensed
under the Open Government Licence – Toronto."*

**`LICENSE` needs two corrections.** Its Toronto claim is right but is missing
the required attribution wording. Its BIXI claim — "BIXI Montreal open data
terms (attribution to BIXI Montreal)" — **is not supported by anything on the
source page**. The CC BY-SA 4.0 seen elsewhere belongs to a third party's
republication of the 2014–2021 files, not to BIXI. Resolve before any
Montreal-derived artifact ships.

---

## Consequences

**1. Two README metrics overpromise.** E-bike share and membership mix cannot be
three-city comparisons. Options, in order of preference:

- **Show them as two-city comparisons, labelled.** Vancouver and Toronto side by
  side with Montreal explicitly marked "not published". Keeps the metric, tells
  the truth, and makes the gap itself informative.
- **Demote to per-city detail.** The comparison set becomes trips, seasonality,
  duration, stations, flows, forecast.
- **Drop them** — cleanest, but discards the most interesting trend in Canadian
  bike share: Toronto's e-bike share reaching ~22%.

Recommendation: **the first.**

**2. The era-map approach is validated and more necessary here than in
Vancouver.** Toronto renames every column twice and reorders them once; Montreal
changes station key space twice and drops two fields. A hard fail on unmapped
headers is the only safe posture.

**3. Timestamp precision is not uniform** — Toronto is minute-precision through
2022, BIXI minute → second → millisecond → epoch ms, Vancouver five formats and
minute precision in the file sampled. Any hour-of-day comparison must state the
floor; only Toronto 2025 and BIXI 2020–2021 support sub-minute analysis at all.

**4. Three things need handling Vancouver never needed:** BIXI's per-era station
key bridge, BIXI's unterminated trips, and Toronto's month-first dates.

**5. No city's period label can be trusted as its content month.** Vancouver's
`2025-01` file holds February rows; BIXI's annual files are unsorted and the
2025 file holds a 2026 row. The canonical month must be derived from the
timestamp at conform, for every system.

## Still open

- [x] ~~Vancouver: spot-verify one real file against the carried column map~~ —
      done, byte-identical to the pinned manifest
- [ ] Montreal: 2015–2019 and 2026 (2014, 2020, 2021, 2022, 2025 read; the
      unread years sit inside observed eras)
- [ ] Toronto: 2014–2015 XLSX, and 2019/2021/2023/2024 (2017, 2018, 2020, 2022,
      2025 read)
- [ ] Unterminated-trip rate across a full BIXI year, and the cause — spec 006
- [ ] Timezone basis for BIXI epoch-ms and for all naive local timestamps
- [ ] A downtown Montreal ECCC station to replace 30165 — spec 013
- [ ] Licence resolution for BIXI; MDLA re-confirmation for Mobi
- [ ] SHA-256 per file — **deferred to spec 003 by amendment**, see below

## Full-archive census (2026-07-28, spec 005)

Spec 001 sampled. `pipeline/census.py` then read the header of **every** file in
the acquired archive, and found three things sampling missed. All **[observed]**.

**1. Toronto 2017 is two layouts, not one.** Q1 and Q2 carry station IDs; **Q3
and Q4 do not** — they ship `trip_id, trip_start_time, trip_stop_time,
trip_duration_seconds, from_station_name, to_station_name, user_type`, seven
columns, names only. **2016 uses that same name-only layout.** Spec 001 read Q1
and generalised; that was wrong. Station identity for Toronto 2016 and half of
2017 must be resolved by name, like BIXI's 2022+ era.

**2. Toronto 2014–2015 is not trip data.** `bikeshare-ridership-2014-2015.xlsx`
is a 16-sheet workbook of **pre-aggregated origin–destination matrices** — one
sheet per month, each `Start Terminal | End Terminal | Casual | Registered |
Total`, plus `Station Key`, hourly summaries and a `Demographics` sheet. There
are no timestamps and no per-trip rows.

It cannot enter `fact_trips`: the grain is wrong, and mixing grains is exactly
what this project must not do. **Toronto's trip-level history therefore begins
in 2016, not 2014.** The file stays pinned in the manifest and is a candidate
source for a future flows or membership comparison at its own grain. The common
window across all three systems is unaffected — Vancouver still sets it at 2017.

**3. Montreal ships historical station coordinates.** Every pre-2022 annual ZIP
contains a `Stations_YYYY.csv`, so Montreal has per-year station positions for
2014–2021 rather than depending on the current-state GBFS feed. Their headers
drift too: `code` (2014–2018, 2020), **`Code`** capitalised (2019), and `pk`
(2021).

Layout counts across the acquired archive: **Montreal 6** (3 trip, 3 station),
**Toronto 5 and counting**.

## Method and corrections

Read over HTTP range requests rather than downloading: the ZIP central directory
is fetched from the tail, then only the needed member is streamed. BIXI 2025
alone is 2.8 GB uncompressed and this audit read tens of MB of it. The helper is
throwaway audit tooling, deliberately not committed; the real downloader is spec
003.

**Amendment.** Spec 001 asked for a SHA-256 per sampled file. Range reads never
materialize a whole file, so no digest was computable. Deferred to spec 003,
which downloads in full and pins checksums into the manifest — the right home for
a reproducibility contract. Recorded in the spec.

**Correction.** An earlier draft of this audit reported the BIXI unterminated
rate as 13.3%, from a 45,212-row scan. A 213,684-row scan gives 2.8%, and the
rate keeps falling as the scan grows because the file is not randomly ordered.
Neither figure is the year's rate. The claim is now stated as existence and
significance, not as a percentage.
