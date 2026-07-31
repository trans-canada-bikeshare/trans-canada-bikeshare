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

-- Station key normalisation lives HERE, one stage earlier than the identity it
-- feeds, because the drop rule below has to ask the same question stage 30
-- will: "does this row have a station at all?"
--
-- It did not, and five 2016 Toronto rows proved it. Their departure station
-- name is the literal four-character string 'NULL' with no key beside it. The
-- old predicate tested `nullif(trim(name), '')`, which 'NULL' passes, so the
-- rows were KEPT — and stage 30 then nulled the token and produced no station
-- identity for them. Kept rows with no departure station violate the rule this
-- file states in its own header, and they were invisible to the funnel because
-- nothing counted them under any reason.
--
-- Toronto's return-side ids also arrive float-formatted in some eras: '8160.0'
-- beside '8160' for the same dock. Left alone they become two stations, which
-- inflated the site's active-station count by roughly 2.3x. Only the exact
-- 'NULL' token is nulled — scoped to the observed defect, nothing
-- pattern-matched.
CREATE OR REPLACE MACRO norm_key(s) AS
  CASE WHEN upper(trim(cast(s AS VARCHAR))) = 'NULL' THEN NULL
       ELSE nullif(regexp_replace(trim(cast(s AS VARCHAR)), '\.0+$', ''), '') END;

CREATE OR REPLACE MACRO norm_name(s) AS
  nullif(nullif(trim(regexp_replace(lower(cast(s AS VARCHAR)), '\s+', ' ', 'g')), 'null'),
         '');

-- Two-digit years. Mobi's 2019-04 file ships '4/20/19' and the whole of
-- Toronto's 2017 Q4 uses M/D/YY. strptime's %Y cheerfully matches '19' and
-- yields the year 19, so 421,805 rows landed in the first century — an entire
-- quarter of Toronto among them. Rather than fight the format list, correct
-- after the fact: nothing in this archive is genuinely from year 19.
CREATE OR REPLACE MACRO fix_short_year(ts) AS
  CASE WHEN ts IS NOT NULL AND year(ts) < 100
       THEN ts + INTERVAL 2000 YEAR ELSE ts END;

-- Context-aware: Excel serial, then the file's proven date order, then the
-- general list. `ord` is file_date_order.resolved_order — the order the values
-- PROVED, or, where they could not, the one declared in
-- pipeline/mappings/date_order.json. The derived value stays in `date_order`
-- beside it, so what the data said and what a person decided never collapse
-- into one column that cannot tell them apart. Nothing is defaulted: a file
-- with neither aborts the stage (etl.AmbiguousDateOrder).
CREATE OR REPLACE MACRO parse_ts_ord(s, ord) AS fix_short_year(coalesce(
  excel_ts(s),
  CASE WHEN ord = 'day' THEN parse_day_first(s) END,
  parse_month_first(s)
));

-- Kept for ad-hoc queries and the accounting in etl.py, where per-file order is
-- not to hand. Do not use it inside clean_trips.
CREATE OR REPLACE MACRO parse_ts(s) AS fix_short_year(coalesce(excel_ts(s), parse_month_first(s)));

-- Deduplication, scoped by measurement rather than applied blindly.
--
-- Measured rates over the full archive (pipeline/census + a hash count, ~10s):
--   van-mobi       2.78%   (documented cross-file spillover)
--   mtl-bixi       0.030%
--   tor-bikeshare  0.020%
--
-- Only Vancouver's rate changes a published figure — leaving it would overstate
-- Vancouver's ridership by nearly 3%. So Vancouver is deduplicated exactly, and
-- the other two carry a measured, stated residual reported in the quality
-- report.
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
--
-- MATERIALISED, not inlined as a CTE, so the row accounting can COUNT the rows
-- this step removes against the very same keep set the table was built from.
-- While it was a CTE the funnel had no way to count them, and the duplicate
-- figure was landed-minus-kept-minus-everything-else — an identity that closes
-- the funnel by construction and could not have detected a double-counted
-- reason.
CREATE OR REPLACE TABLE van_dedupe_keep AS
  SELECT min(rowid) AS keep_rid
  FROM raw_trips
  WHERE system_id = 'van-mobi'
  GROUP BY
    departure_raw, departure_ms, return_raw, return_ms,
    departure_station_key, return_station_key,
    departure_station_name, return_station_name,
    bike_id, duration_s;

CREATE OR REPLACE TABLE clean_trips AS
WITH
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
    coalesce(parse_ts_ord(r.departure_raw, o.resolved_order),
             to_local(r.system_id, r.departure_ms))               AS departure_ts,
    coalesce(parse_ts_ord(r.return_raw, o.resolved_order),
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
  -- The SAME question stage 30 asks. Testing the trimmed raw values here let
  -- the literal token 'NULL' through as if it were a station name.
  AND (norm_key(departure_station_key) IS NOT NULL
       OR norm_name(departure_station_name) IS NOT NULL)
  -- Vancouver is deduplicated; the other two pass through with the measured
  -- residual recorded above and reported in docs/data-quality-report.md.
  AND (system_id <> 'van-mobi' OR rid IN (SELECT keep_rid FROM van_dedupe_keep));

-- Toronto's 2016.xlsx Q4 worksheet has a mixed-type date column that TORONTO'S
-- OWN Excel corrupted before publishing. The sheet was built from D/M/Y text;
-- Excel silently coerced every value whose day was <= 12 into an M/D/Y
-- datetime — day and month transposed — and left the rest (days 13-31) as
-- strings. The strings prove the true order, and the typed cells' day field
-- carries only {10, 11, 12}: the true MONTHS of Q4.
--
-- Uncorrected, 80,109 of the sheet's 217,569 trips landed on months January
-- through September, fabricating six months of 2016 ridership that never
-- happened (each existing only on days 9-12 — one more day than the
-- incomplete-month gate excludes) and stripping October, November and
-- December of their first twelve days.
--
-- The repair is a pure swap, and it is exactly scoped: within this one sheet,
-- serial-typed rows decode to day <= 12 and string rows parse to day >= 13,
-- so the predicate cannot touch a string row. Verified against the workbook
-- with openpyxl before writing this. The rest of the archive was swept for
-- the same signature (serial rows whose decoded days never exceed 12) and no
-- other file has it — Vancouver's xlsx serials all span full months.
--
-- This runs BEFORE 25_localise, so the UTC shift applies to corrected dates.
UPDATE clean_trips
SET departure_ts = make_timestamp(year(departure_ts), day(departure_ts),
                                  month(departure_ts), 0, 0, 0)
                   + (departure_ts - date_trunc('day', departure_ts))
WHERE source_file LIKE '%2016.xlsx#tor_trips_2016_Q4'
  AND day(departure_ts) <= 12;

UPDATE clean_trips
SET return_ts = make_timestamp(year(return_ts), day(return_ts),
                               month(return_ts), 0, 0, 0)
                + (return_ts - date_trunc('day', return_ts))
WHERE source_file LIKE '%2016.xlsx#tor_trips_2016_Q4'
  AND return_ts IS NOT NULL AND day(return_ts) <= 12;

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
