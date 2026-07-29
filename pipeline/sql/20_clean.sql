-- Stage 20: type the values and drop only what is genuinely unusable.
--
-- Cleaning philosophy, carried from the Vancouver project: flag suspect rows,
-- drop only the unusable. A row is unusable here if we cannot say WHEN it
-- started or WHERE it started. Everything else survives to be flagged at
-- conform, where the reasons are counted.
--
-- Deliberately NOT dropped: trips with no recorded end. BIXI's 2022+ files
-- contain them in quantity, and a trip with a known start and an unknown end is
-- still a departure. Dropping them would understate Montreal's ridership;
-- keeping them unflagged would corrupt every duration and flow metric. They are
-- kept, marked, and excluded by name wherever an ending is required.

-- Excel serial dates. Both Mobi's XLSX months and Toronto's 2016 workbook ship
-- raw serials — "43313" is 1 August 2018, not a number. The 20000-80000 guard
-- (1954-2119) keeps real text timestamps out; they fail the cast anyway,
-- having separators.
CREATE OR REPLACE MACRO excel_ts(s) AS
  CASE WHEN try_cast(s AS DOUBLE) BETWEEN 20000 AND 80000
       THEN TIMESTAMP '1899-12-30 00:00:00'
            + to_microseconds(CAST(round(try_cast(s AS DOUBLE) * 86400000000) AS BIGINT))
  END;

-- Month-first and ISO-ish formats. Used for every file except those the
-- date-order table proves are day-first.
CREATE OR REPLACE MACRO parse_month_first(s) AS try_strptime(
  s,
  [
    -- Dash-separated ISO first: unambiguous.
    '%Y-%m-%d %H:%M:%S.%f',   -- BIXI 2021, milliseconds
    '%Y-%m-%d %H:%M:%S',      -- BIXI 2019-2020, Toronto 2025+
    '%Y-%m-%d %H:%M',         -- BIXI 2014-2018, Mobi
    -- Month-first BEFORE slash-ISO. %Y happily matches a two-digit year, so
    -- '%Y/%m/%d' was reading '4/1/19' as year 4 — putting the M/D/Y forms
    -- first fixes it, and they fail harmlessly on a real '2025/05/24'
    -- because month 2025 is invalid.
    '%m/%d/%Y %H:%M:%S',
    '%m/%d/%Y %H:%M',         -- Toronto 2018-2023
    '%-m/%-d/%Y %-H:%M',      -- Mobi 2019, unpadded, two-digit year
    '%Y/%m/%d %H:%M:%S',      -- Mobi 2025+, slash-separated
    '%Y/%m/%d %H:%M'
  ]
);

-- A text timestamp a file published in UTC -> that system's local time.
-- Files classified 'local' (and 'unknown', which is left alone deliberately)
-- pass through untouched. See 17_timezones.sql for how the basis is derived.
CREATE OR REPLACE MACRO as_local(sys, ts, basis) AS
  CASE WHEN ts IS NULL THEN NULL
       WHEN basis = 'utc' THEN timezone(
         CASE sys
           WHEN 'mtl-bixi'      THEN 'America/Montreal'
           WHEN 'tor-bikeshare' THEN 'America/Toronto'
           WHEN 'van-mobi'      THEN 'America/Vancouver'
         END,
         ts AT TIME ZONE 'UTC')
       ELSE ts END;

-- Epoch milliseconds -> that system's local wall-clock time.
CREATE OR REPLACE MACRO to_local(sys, ms) AS
  CASE WHEN try_cast(ms AS BIGINT) IS NOT NULL THEN
    timezone(
      CASE sys
        WHEN 'mtl-bixi'      THEN 'America/Montreal'
        WHEN 'tor-bikeshare' THEN 'America/Toronto'
        WHEN 'van-mobi'      THEN 'America/Vancouver'
      END,
      epoch_ms(try_cast(ms AS BIGINT))::TIMESTAMP AT TIME ZONE 'UTC')
  END;

CREATE OR REPLACE MACRO parse_day_first(s) AS try_strptime(
  s,
  ['%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%-d/%-m/%Y %-H:%M']
);

-- Two-digit years. Mobi's 2019-04 file ships '4/20/19' and the whole of
-- Toronto's 2017 Q4 uses M/D/YY. strptime's %Y cheerfully matches '19' and
-- yields the year 19, so 421,805 rows landed in the first century — an entire
-- quarter of Toronto among them. Rather than fight the format list, correct
-- after the fact: nothing in this archive is genuinely from year 19.
CREATE OR REPLACE MACRO fix_short_year(ts) AS
  CASE WHEN ts IS NOT NULL AND year(ts) < 100
       THEN ts + INTERVAL 2000 YEAR ELSE ts END;

-- Context-aware: Excel serial, then the file's proven date order, then the
-- general list. `ord` comes from file_date_order (stage 15).
CREATE OR REPLACE MACRO parse_ts_ord(s, ord) AS fix_short_year(coalesce(
  excel_ts(s),
  CASE WHEN ord = 'day' THEN parse_day_first(s) END,
  parse_month_first(s)
));

-- Kept for ad-hoc queries and the accounting in etl.py, where per-file order is
-- not to hand. Do not use it inside clean_trips.
CREATE OR REPLACE MACRO parse_ts(s) AS fix_short_year(coalesce(excel_ts(s), parse_month_first(s)));

CREATE OR REPLACE TABLE clean_trips AS
WITH
-- Deduplication, scoped by measurement rather than applied blindly.
--
-- Measured rates over the full archive (pipeline/census + a hash count, ~10s):
--   van-mobi       2.812%  (252,772)  documented cross-file spillover
--   mtl-bixi       0.030%  ( 26,066)
--   tor-bikeshare  0.020%  (  7,773)
--
-- Only Vancouver's rate changes a published figure — leaving it would overstate
-- Vancouver's ridership by nearly 3%. So Vancouver is deduplicated exactly, and
-- the other two carry a measured, stated residual of ~0.02-0.03% reported in
-- the quality report.
--
-- Why not dedupe all three: exact dedupe means grouping 135M rows into ~134.9M
-- groups — nearly one group per row, the worst case for hash aggregation. It
-- ran past 18 GB of spill without finishing. Scoping it to the 9M rows where it
-- is material costs seconds. `SELECT DISTINCT *` is not an option either: it
-- never matches, because source_file is part of the row and the duplicates
-- differ in exactly that column.
--
-- This is a deliberate, quantified trade — not an oversight. Revisit if a
-- future metric becomes sensitive at the 0.03% level.
dedupe_keep AS (
  SELECT min(rowid) AS keep_rid
  FROM raw_trips
  WHERE system_id = 'van-mobi'
  GROUP BY
    departure_raw, departure_ms, return_raw, return_ms,
    departure_station_key, return_station_key,
    departure_station_name, return_station_name,
    bike_id, duration_s
),
typed AS (
  SELECT
    r.rowid                                                     AS rid,
    r.system_id,
    r.source_period,
    r.source_file,
    nullif(trim(r.trip_id), '')                                   AS trip_id,

    -- Text timestamp where one exists, epoch milliseconds otherwise. No system
    -- publishes both, so coalesce is unambiguous.
    -- BIXI's 2022+ epoch milliseconds are UTC; every other era and system
    -- publishes LOCAL time. Read naively they shift Montreal +4/+5 hours: the
    -- peak departure hour moved 17:00 -> 21:00 exactly at the format break
    -- while Toronto and Vancouver held at 17:00, and the 02:00-05:59 share
    -- leapt from 2.2% to 10.4%. 8.9M rows landed on the wrong local DAY, which
    -- corrupts date_key, trip_month and is_weekend. Converting per zone also
    -- gets EDT/EST right, which a flat -4 would not.
    -- Text timestamps land as published here; the handful of files that turn
    -- out to be UTC are corrected in 25_localise.sql. Applying the conversion
    -- inline evaluated ICU across all 135M rows and segfaulted DuckDB, for the
    -- benefit of the ~1.3M that need it.
    coalesce(parse_ts_ord(r.departure_raw, o.date_order),
             to_local(r.system_id, r.departure_ms))               AS departure_ts,
    coalesce(parse_ts_ord(r.return_raw, o.date_order),
             to_local(r.system_id, r.return_ms))                  AS return_ts,

    nullif(trim(r.departure_station_key), '')                     AS departure_station_key,
    nullif(trim(r.return_station_key), '')                        AS return_station_key,
    nullif(trim(r.departure_station_name), '')                    AS departure_station_name,
    nullif(trim(r.return_station_name), '')                       AS return_station_name,
    nullif(trim(r.departure_borough), '')                         AS departure_borough,
    nullif(trim(r.return_borough), '')                            AS return_borough,

    try_cast(r.departure_lat AS DOUBLE)                           AS departure_lat,
    try_cast(r.departure_lon AS DOUBLE)                           AS departure_lon,
    try_cast(r.return_lat    AS DOUBLE)                           AS return_lat,
    try_cast(r.return_lon    AS DOUBLE)                           AS return_lon,

    try_cast(r.duration_s  AS DOUBLE)::BIGINT                     AS duration_s,
    try_cast(r.distance_m  AS DOUBLE)::BIGINT                     AS distance_m,
    nullif(trim(r.membership_raw), '')                            AS membership_raw,
    nullif(trim(r.bike_id), '')                                   AS bike_id,
    nullif(trim(r.bike_model), '')                                AS bike_model,
    nullif(trim(r.electric_bike), '')                             AS electric_bike,
    try_cast(r.departure_temp AS DOUBLE)                          AS departure_temp_c,
    try_cast(r.return_temp    AS DOUBLE)                          AS return_temp_c,
    try_cast(r.stopover_s     AS DOUBLE)::BIGINT                  AS stopover_s,
    try_cast(r.stopover_count AS DOUBLE)::BIGINT                  AS stopover_count
  FROM raw_trips r
  LEFT JOIN file_date_order o
    ON o.system_id = r.system_id AND o.source_file = r.source_file
)
SELECT * EXCLUDE (rid)
FROM typed
WHERE departure_ts IS NOT NULL
  AND (departure_station_key IS NOT NULL OR departure_station_name IS NOT NULL)
  -- Vancouver is deduplicated; the other two pass through with the measured
  -- residual recorded above and reported in docs/data-quality-report.md.
  AND (system_id <> 'van-mobi' OR rid IN (SELECT keep_rid FROM dedupe_keep));

-- Station snapshots: Montreal's annual files. Collapsed to one row per station
-- at conform, where a station's positions over the years become one position.
CREATE OR REPLACE TABLE clean_stations AS
SELECT DISTINCT
  system_id,
  source_period,
  nullif(trim(station_key), '')   AS station_key,
  nullif(trim(station_name), '')  AS station_name,
  try_cast(lat AS DOUBLE)         AS lat,
  try_cast(lon AS DOUBLE)         AS lon
FROM raw_stations
WHERE nullif(trim(station_key), '') IS NOT NULL
   OR nullif(trim(station_name), '') IS NOT NULL;
