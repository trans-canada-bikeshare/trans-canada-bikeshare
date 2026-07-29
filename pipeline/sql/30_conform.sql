-- Stage 30: give every trip a stable station identity, a canonical month, and
-- quality flags. Nothing is deleted here — suspect rows are marked and counted.
--
-- The hard problem is station identity, and it is hard in a different way for
-- each system:
--
--   Vancouver  the station NAME carries its id as a prefix: "0069 7th &
--              Granville". Split it.
--   Montreal   three key spaces across four eras. 2014-2020 codes (6xxx) join
--              to GBFS short_name; 2021 keys (small ints) join to GBFS
--              station_id; 2022+ has no key at all, only a name.
--   Toronto    ids from 2018 on, but 2016 and half of 2017 ship names only.
--
-- So the conformed key is: the published id where one exists, and a normalised
-- name otherwise. Which of the two was used is recorded per row, because a
-- name-matched station is a weaker claim than an id-matched one and the
-- quality report must be able to say how much of the archive rests on it.

CREATE OR REPLACE MACRO norm_name(s) AS
  nullif(trim(regexp_replace(lower(cast(s AS VARCHAR)), '\s+', ' ', 'g')), '');

-- Vancouver's "0069 7th & Granville" -> ('0069', '7th & Granville')
CREATE OR REPLACE MACRO van_id(s) AS
  regexp_extract(cast(s AS VARCHAR), '^\s*(\d{3,4})\s', 1);
CREATE OR REPLACE MACRO van_label(s) AS
  nullif(trim(regexp_replace(cast(s AS VARCHAR), '^\s*\d{3,4}\s+', '')), '');

-- A VIEW, not a table. Materialising it would mean a third full copy of 135M
-- rows for no gain: fact_trips is the only thing downstream queries, and it
-- reads through this in one pass.
CREATE OR REPLACE VIEW conformed_trips AS
WITH resolved AS (
  SELECT
    c.*,
    -- Departure identity
    CASE
      WHEN system_id = 'van-mobi' AND nullif(van_id(departure_station_name), '') IS NOT NULL
        THEN 'van-mobi:' || van_id(departure_station_name)
      WHEN departure_station_key IS NOT NULL
        THEN system_id || ':' || departure_station_key
      WHEN departure_station_name IS NOT NULL
        THEN system_id || ':name:' || norm_name(departure_station_name)
    END AS departure_station_id,
    CASE
      WHEN system_id = 'van-mobi' AND nullif(van_id(return_station_name), '') IS NOT NULL
        THEN 'van-mobi:' || van_id(return_station_name)
      WHEN return_station_key IS NOT NULL
        THEN system_id || ':' || return_station_key
      WHEN return_station_name IS NOT NULL
        THEN system_id || ':name:' || norm_name(return_station_name)
    END AS return_station_id,
    CASE
      WHEN system_id = 'van-mobi' AND nullif(van_id(departure_station_name), '') IS NOT NULL THEN 'id'
      WHEN departure_station_key IS NOT NULL THEN 'id'
      ELSE 'name'
    END AS departure_station_match,
    -- Human label, with Vancouver's numeric prefix stripped
    CASE WHEN system_id = 'van-mobi'
         THEN coalesce(van_label(departure_station_name), departure_station_name)
         ELSE departure_station_name END AS departure_label,
    CASE WHEN system_id = 'van-mobi'
         THEN coalesce(van_label(return_station_name), return_station_name)
         ELSE return_station_name END AS return_label
  FROM clean_trips c
),
derived AS (
  SELECT
    *,
    -- The published period label is NOT the content month anywhere: Vancouver's
    -- 2025-01 file holds February rows, and BIXI's annual files are unsorted
    -- and spill across the year boundary. Always derive from the timestamp.
    date_trunc('month', departure_ts)::DATE          AS trip_month,
    year(departure_ts)                               AS trip_year,
    departure_ts::DATE                               AS date_key,
    CASE WHEN return_ts IS NOT NULL
         THEN date_diff('second', departure_ts, return_ts) END AS derived_duration_s,
    -- e-bike, from whichever signal the system publishes. Montreal has none in
    -- any era, and NULL here means "not published", never "not electric".
    CASE
      WHEN system_id = 'van-mobi' AND electric_bike IS NOT NULL
        THEN lower(electric_bike) IN ('true', '1', 'yes')
      WHEN system_id = 'tor-bikeshare' AND bike_model IS NOT NULL
        THEN upper(bike_model) LIKE 'EFIT%'
    END                                              AS is_ebike
  FROM resolved
)
SELECT
  *,
  -- Duration published by the source where available, derived otherwise.
  coalesce(duration_s, derived_duration_s)           AS duration_final_s,
  list_filter([
    CASE WHEN return_ts IS NULL                            THEN 'unterminated' END,
    CASE WHEN return_ts IS NOT NULL AND return_ts < departure_ts
                                                           THEN 'negative_duration' END,
    CASE WHEN coalesce(duration_s, derived_duration_s) = 0  THEN 'zero_duration' END,
    CASE WHEN coalesce(duration_s, derived_duration_s) > 86400 THEN 'over_24h' END,
    CASE WHEN departure_station_id IS NOT NULL
              AND departure_station_id = return_station_id
              AND coalesce(duration_s, derived_duration_s) < 120
                                                           THEN 'same_station_under_2min' END,
    CASE WHEN return_station_id IS NULL AND return_ts IS NOT NULL
                                                           THEN 'no_return_station' END,
    CASE WHEN departure_station_match = 'name'             THEN 'station_matched_by_name' END,
    -- Nothing in this archive predates 2009 or postdates today by much. A row
    -- outside that window survived parsing but cannot be trusted; flag it
    -- rather than quietly averaging it into a monthly total.
    CASE WHEN year(departure_ts) < 2009
           OR departure_ts > current_date + INTERVAL 2 DAY
                                                           THEN 'implausible_date' END
  ], x -> x IS NOT NULL)                             AS quality_flags
FROM derived;

-- One row per station per system, positions preferred from the most recent
-- annual snapshot that has them.
CREATE OR REPLACE TABLE conformed_stations AS
SELECT
  system_id,
  system_id || ':' || station_key      AS station_id,
  arg_max(station_name, source_period) AS station_name,
  arg_max(lat, source_period)          AS lat,
  arg_max(lon, source_period)          AS lon,
  min(source_period)                   AS first_seen_period,
  max(source_period)                   AS last_seen_period
FROM clean_stations
WHERE station_key IS NOT NULL AND lat IS NOT NULL AND lon IS NOT NULL
GROUP BY system_id, station_key;
