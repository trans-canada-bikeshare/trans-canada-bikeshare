# Source Column Audit

Spec 001. What the three systems actually publish, read from the real files.

**Status: partial.** The core question — can each headline metric be computed
the same way for all three cities — is answered below and the answer is no for
two of them. Several eras remain unread; they are listed under
[Still open](#still-open) and none of them can overturn the verdicts already
reached, only add detail.

Every claim is tagged **[observed]** (read from a real file in this audit),
**[carried]** (observed by the Vancouver project's pipeline across its full
archive, which is stronger evidence than a spot check), or **[inferred]** (not
yet verified — treat as a hypothesis).

Read date: 2026-07-28.

---

## Verdicts

| README metric | Vancouver | Montreal | Toronto | Like-for-like? |
| --- | --- | --- | --- | --- |
| Trips over time | ✅ | ✅ | ✅ | **Yes** |
| Seasonality | ✅ | ✅ | ✅ | **Yes** |
| Trip duration | ✅ | ✅ | ✅ | **Yes** — derived for BIXI 2022+ |
| Active stations | ✅ | ⚠️ | ✅ | **Qualified** — see station identity |
| Station flows | ✅ | ⚠️ | ✅ | **Qualified** — 13.3% of BIXI trips have no end |
| **E-bike share** | ✅ | ❌ | ✅ | **No** — Montreal never publishes bike type |
| **Membership mix** | ✅ | ⚠️ 2014–21 only | ✅ | **No** — Montreal drops it at 2022 |
| Weather forecast | ✅ | ✅ | ✅ | **Yes** — ECCC covers all three |
| Operational signals | ✅ | ⚠️ | ✅ | **Qualified** — no bike ID for Montreal |

**Two headline metrics in the README cannot be shown as a three-city
comparison.** E-bike share and membership mix are Vancouver-and-Toronto only.
This is a product decision, not a pipeline problem — no amount of engineering
recovers a column the publisher does not ship. Options are recorded in
[Consequences](#consequences).

---

## Vancouver — Mobi by Rogers

Source: `https://www.mobibikes.ca/en/system-data`. Monthly XLSX/CSV via Google
Drive; one `ALL of 2017` workbook then monthly from 2018-01.

**[carried]** The Vancouver project maps **34 distinct raw headers across 31
layouts over 102 files**, unified to: `departure`, `return`,
`departure_station`, `return_station`, `bike`, `electric_bike`, `membership`,
`distance_m`, `duration_s`, `departure_temp`, `return_temp`, `stopover_s`,
`stopover_count`. Dropped by explicit decision: `Account`, `Manager`,
`Departure slot`, `Return slot`, and the battery-voltage pair.

This is the richest of the three schemas by a wide margin — it is the only one
with distance, per-trip temperature, and stopover behaviour.

| Canonical field | Column | Note |
| --- | --- | --- |
| departure / return ts | `Departure` / `Return` | Five distinct timestamp formats across eras **[carried]** |
| stations | `Departure station` / `Return station` | Name-prefixed IDs; parsed at conform **[carried]** |
| coordinates | — | GBFS 2.2 (Fifteen platform), not in trip files **[carried]** |
| duration | `Duration (sec.)` | **[carried]** |
| distance | `Covered distance (m)` | Unique to Vancouver **[carried]** |
| membership | `Membership type` / `Memebership type` / `Formula` | 85 raw labels, explicitly mapped **[carried]** |
| bike id | `Bike` | **[carried]** |
| **e-bike** | `Electric bike` / `Electric Bike` / `Electric` | **Present** **[carried]** |

Known quirks **[carried]**: the source page misspells `Novemeber 2021`; summer
2023 files carry invalid UTF-8 in the Squamish-language station name
`0099 šxʷƛ̓ənəq Xwtl'e7énḵ Square`; per-trip temperatures degrade to
0-sentinels after mid-2025; format drifts XLSX ↔ CSV ↔ Google Sheets across
years.

**Licence:** Mobi Data License Agreement — non-commercial analysis use.
**[carried]**, needs re-confirming against the live page.

---

## Montreal — BIXI

Source: `https://bixi.com/en/open-data/`. Annual ZIP per year, 2014–2026.
**Two incompatible eras**, and the break costs real fields.

### Era A — through 2021 **[observed]**

`Historique-BIXI-2021.zip` → `2021_donnees_ouvertes.csv` (352 MB) +
`2021_stations.csv` (45 KB).

```
start_date,emplacement_pk_start,end_date,emplacement_pk_end,duration_sec,is_member
2021-06-29 17:46:28.653,10,2021-06-29 19:33:25.700,10,6417,0
```

| Canonical field | Column | Note |
| --- | --- | --- |
| departure / return ts | `start_date` / `end_date` | `YYYY-MM-DD HH:MM:SS.mmm`, **millisecond** precision, no timezone marker |
| stations | `emplacement_pk_start` / `emplacement_pk_end` | Integer keys. Named `start_station_code` before 2021 **[inferred]** |
| coordinates | separate `2021_stations.csv` | Annual snapshot |
| duration | `duration_sec` | Explicit |
| membership | `is_member` | **0/1 boolean** — coarser than Vancouver's 85 labels |
| bike id | — | **Absent** |
| **e-bike** | — | **Absent** |

### Era B — 2022 onward **[observed]**

`DonneesOuverte2022.csv` (1.48 GB) and
`DonneesOuvertes2025_...csv` (2.80 GB) — one unsorted CSV for the entire year.

```
STARTSTATIONNAME,STARTSTATIONARRONDISSEMENT,STARTSTATIONLATITUDE,STARTSTATIONLONGITUDE,ENDSTATIONNAME,ENDSTATIONARRONDISSEMENT,ENDSTATIONLATITUDE,ENDSTATIONLONGITUDE,STARTTIMEMS,ENDTIMEMS
St-Urbain / René-Lévesque,Ville-Marie,45.507838,-73.563136,Mansfield / Ste-Catherine,Ville-Marie,45.5013987,-73.5717863,1653343831220,1653344213703
```

| Canonical field | Column | Note |
| --- | --- | --- |
| departure / return ts | `STARTTIMEMS` / `ENDTIMEMS` | **Epoch milliseconds.** Timezone basis unverified |
| stations | `STARTSTATIONNAME` / `ENDSTATIONNAME` | **Name only — the station ID is gone.** Borough in `*ARRONDISSEMENT` |
| coordinates | inline `*LATITUDE` / `*LONGITUDE` | Per trip, ~14 decimal places |
| duration | — | **Derivable** as `ENDTIMEMS - STARTTIMEMS` |
| membership | — | **Absent — lost at the 2022 break** |
| bike id | — | Absent |
| **e-bike** | — | **Absent** |

**Three consequences of the break, all load-bearing:**

1. **Station identity becomes a string.** Joining a 2021 station key to a 2022
   station name requires a name-matching bridge, and station names drift
   (`Parc Émilie-Gamelin (St-Hubert / de Maisonneuve sud)`). Any cross-era
   Montreal station series depends on that bridge being right.
2. **Membership disappears.** Member vs casual exists for 2014–2021 and not
   after. A "membership mix over time" chart for Montreal would end in 2021.
3. **13.3% of 2025 trips have no end** **[observed]** — 6,008 of 45,212 rows
   scanned have blank `ENDTIMEMS`, `ENDSTATIONNAME`, and end coordinates.
   Cause unknown. Until it is understood, every Montreal flow, duration, and
   destination metric is computed on 87% of trips, and that has to be stated
   on the chart rather than buried in methodology.

Also **[observed]**: the annual CSV is **not sorted by time** — the first 2,000
rows span 2025-01-15 to 2025-10-17. Anything assuming ordering will be wrong.

**Licence: none stated.** **[observed]** — the open-data page carries no
licence, terms, or attribution text. A third-party republication of the
2014–2021 files uses CC BY-SA 4.0, but that is *that author's* choice and is
not evidence of BIXI's terms. **`LICENSE` currently claims "BIXI Montreal open
data terms (attribution to BIXI Montreal)" — that claim is not presently
supported by anything on the source page and must be resolved before any
Montreal-derived artifact ships.**

---

## Toronto — Bike Share Toronto

Source: CKAN `bike-share-toronto-ridership-data` on `open.toronto.ca`. Annual
ZIP per year, 2014–2026, refreshed monthly. 2024–2026 were all re-published
2026-07-28 **[observed]** — the same day as this audit, which suggests a
rolling republication worth watching for silent restatement of history.

### Era A — 2017 **[observed]**

`bikeshare-ridership-2017.zip` → four **quarterly** CSVs under a `2017 Data/`
prefix.

```
trip_id,trip_start_time,trip_stop_time,trip_duration_seconds,from_station_id,from_station_name,to_station_id,to_station_name,user_type
712382,1/1/2017 0:00,1/1/2017 0:03,223,7051,Wellesley St E / Yonge St Green P,7089,Church St  / Wood St,Member
```

Note the timestamp: **`M/D/YYYY H:MM` — minute precision, no seconds.** Trip
duration is still given in seconds, so duration and timestamps disagree on
resolution. Also note the doubled space in `Church St  / Wood St` — station
names need normalizing.

### Era B — 2025 **[observed]**

`bikeshare-ridership-2025.zip` → twelve **monthly** CSVs, ~1.07 GB uncompressed
for the year.

```
Trip_Id,Trip_Duration,Start_Station_Id,Start_Time,Start_Station_Name,End_Station_Id,End_Time,End_Station_Name,Bike_Id,User_Type,Bike_Model
36767099,6946,7569,2025-06-01 00:01:56,Toronto Inukshuk Park,7753,2025-06-01 01:57:42,Toronto Inukshuk Park,5096,Casual,ICONIC
```

| Canonical field | 2017 | 2025 |
| --- | --- | --- |
| departure / return ts | `trip_start_time` / `trip_stop_time`, **minute** precision | `Start_Time` / `End_Time`, **second** precision |
| stations | `from_station_id` / `to_station_id` + names | `Start_Station_Id` / `End_Station_Id` + names |
| coordinates | — | — (GBFS only) |
| duration | `trip_duration_seconds` | `Trip_Duration` |
| membership | `user_type` | `User_Type` |
| bike id | — | `Bike_Id` |
| **e-bike** | — | **`Bike_Model`** |

**`Bike_Model` distinct values, July 2025, 91,585 rows scanned [observed]:**

| Value | Trips | Share |
| --- | ---: | ---: |
| `ICONIC` | 71,629 | 78.2% |
| `EFIT` | 11,251 | 12.3% |
| `EFIT G5` | 8,705 | 9.5% |

`EFIT` and `EFIT G5` are the e-bike models; **e-bike share ≈ 21.8%** in that
sample. Consistent with the City's reported 17% for 2024 across a full year.
`User_Type` is `Member` / `Casual` **[observed]**.

Naming, casing, timestamp precision, file granularity (quarterly → monthly),
and the column set **all** change between 2017 and 2025. The eras between are
unread.

**Licence:** the CKAN record returns a **null** licence field **[observed]**.
The portal-wide Open Government Licence – Toronto is the presumed default
**[inferred]** and must be confirmed before shipping.

---

## Consequences

**1. The README overpromises on two metrics.** E-bike share and membership mix
cannot be three-city comparisons. Three honest options, in order of preference:

- **Show them as two-city comparisons, labelled.** Vancouver and Toronto side
  by side, with Montreal explicitly marked "not published" rather than absent.
  Keeps the metric, tells the truth, and makes the gap itself informative.
- **Demote them from headline to per-city detail.** The comparison set becomes
  trips, seasonality, duration, stations, flows, forecast.
- **Drop them.** Cleanest, but discards the single most interesting trend in
  Canadian bike share — Toronto's e-bike share went from ~6% to ~22% in three
  years.

Recommendation: **the first.** A visible, explained gap is a stronger
credibility signal than a metric quietly missing a city, and it is exactly what
`README.md`'s "every visual encoding says what it means" is for.

**2. `LICENSE` needs correcting.** Its BIXI claim is unsupported by the source
page, and its Toronto claim needs confirming against the portal default.

**3. The era-map approach is validated, and needed more here than in
Vancouver.** Per-city era maps with a hard fail on unknown headers are exactly
right: Toronto renames every column between 2017 and 2025, and Montreal drops
two fields entirely at 2022.

**4. Two things need explicit handling in the model that Vancouver never
needed:** BIXI's name-only station identity after 2022, and BIXI's missing trip
ends. Both belong in spec 007 (conform) and must surface in spec 010's quality
report.

**5. Timestamp precision is not uniform** — Toronto 2017 is minute-precision,
BIXI 2021 is millisecond, BIXI 2022+ is epoch ms, Vancouver has five formats.
Any hour-of-day comparison must state the floor, and Toronto's early years
cannot support sub-minute analysis at all.

---

## Still open

None of these can overturn the verdicts above; they add detail.

- [ ] Vancouver: spot-verify one real file against the carried column map
- [ ] Montreal: 2014–2020 headers (2021 read; Goulet reports
      `start_station_code` before 2021) and the 2026 partial year
- [ ] Toronto: 2014–2015 XLSX, and the 2018–2024 eras between the two read
- [ ] The BIXI blank-end-trip cause — ongoing at export, out-of-network, or a
      publishing defect
- [ ] Timezone basis for BIXI epoch-ms and for every naive local timestamp
- [ ] GBFS `station_information` shape for all three systems
- [ ] Licence confirmation: BIXI (none found), Toronto (CKAN null), Mobi (MDLA
      re-check)
- [ ] ECCC climate station IDs for Montreal and Toronto
- [ ] SHA-256 and byte size for every sampled file — deferred to spec 003,
      which pins them into the manifest

## Method

Read over HTTP range requests rather than downloading — the ZIP central
directory is fetched from the tail, then only the needed member is streamed.
BIXI 2025 alone is 2.8 GB uncompressed; the audit read a few MB of it. The
helper is throwaway audit tooling and is deliberately not committed; the real
downloader is spec 003.
