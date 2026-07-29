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

CREATE OR REPLACE MACRO parse_ts(s) AS try_strptime(
  s,
  [
    '%Y-%m-%d %H:%M:%S.%f',   -- BIXI 2021, milliseconds
    '%Y-%m-%d %H:%M:%S',      -- BIXI 2019-2020, Toronto 2025+
    '%Y-%m-%d %H:%M',         -- BIXI 2014-2018, Mobi
    '%m/%d/%Y %H:%M:%S',
    '%m/%d/%Y %H:%M',         -- Toronto 2019-2024, MONTH FIRST (verified)
    '%-m/%-d/%Y %-H:%M'       -- Toronto 2017-2018, unpadded
  ]
);

CREATE OR REPLACE TABLE clean_trips AS
WITH typed AS (
  SELECT
    system_id,
    source_period,
    source_file,
    nullif(trim(trip_id), '')                                   AS trip_id,

    -- Text timestamp where one exists, epoch milliseconds otherwise. No system
    -- publishes both, so coalesce is unambiguous.
    coalesce(parse_ts(departure_raw), epoch_ms(try_cast(departure_ms AS BIGINT)))
                                                                AS departure_ts,
    coalesce(parse_ts(return_raw),    epoch_ms(try_cast(return_ms    AS BIGINT)))
                                                                AS return_ts,

    nullif(trim(departure_station_key), '')                     AS departure_station_key,
    nullif(trim(return_station_key), '')                        AS return_station_key,
    nullif(trim(departure_station_name), '')                    AS departure_station_name,
    nullif(trim(return_station_name), '')                       AS return_station_name,
    nullif(trim(departure_borough), '')                         AS departure_borough,
    nullif(trim(return_borough), '')                            AS return_borough,

    try_cast(departure_lat AS DOUBLE)                           AS departure_lat,
    try_cast(departure_lon AS DOUBLE)                           AS departure_lon,
    try_cast(return_lat    AS DOUBLE)                           AS return_lat,
    try_cast(return_lon    AS DOUBLE)                           AS return_lon,

    try_cast(duration_s  AS DOUBLE)::BIGINT                     AS duration_s,
    try_cast(distance_m  AS DOUBLE)::BIGINT                     AS distance_m,
    nullif(trim(membership_raw), '')                            AS membership_raw,
    nullif(trim(bike_id), '')                                   AS bike_id,
    nullif(trim(bike_model), '')                                AS bike_model,
    nullif(trim(electric_bike), '')                             AS electric_bike,
    try_cast(departure_temp AS DOUBLE)                          AS departure_temp_c,
    try_cast(return_temp    AS DOUBLE)                          AS return_temp_c,
    try_cast(stopover_s     AS DOUBLE)::BIGINT                  AS stopover_s,
    try_cast(stopover_count AS DOUBLE)::BIGINT                  AS stopover_count
  FROM raw_trips
)
-- Dedupe on the trip's IDENTITY, not on the whole row.
--
-- `SELECT DISTINCT *` looks like the obvious way to do this and is wrong twice
-- over: source_file is part of the row, so two copies of one trip appearing in
-- two different published files never match and survive both — while the
-- engine pays to hash all 25 columns of 135M rows. The duplicates that exist
-- here are exactly the cross-file kind, so provenance columns must be excluded
-- from the comparison and carried along instead.
SELECT * EXCLUDE (dup_rank)
FROM (
  SELECT
    *,
    row_number() OVER (
      PARTITION BY
        system_id, departure_ts, return_ts,
        departure_station_key, return_station_key,
        departure_station_name, return_station_name,
        bike_id, duration_s
      ORDER BY source_period, source_file
    ) AS dup_rank
  FROM typed
  WHERE departure_ts IS NOT NULL
    AND (departure_station_key IS NOT NULL OR departure_station_name IS NOT NULL)
)
WHERE dup_rank = 1;

-- Station snapshots: Montreal's annual files. Deduped across years at conform,
-- where a station's positions over time become one row.
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
