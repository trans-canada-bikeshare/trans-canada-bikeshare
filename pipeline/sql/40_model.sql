-- Stage 40: Kimball-style star schema.
--
--   fact_trips       one row per trip, degenerate quality flags
--   dim_system       the three docked systems (loaded by the runner from
--                    common.SYSTEMS so there is one source of truth)
--   dim_station      every station ever seen, with coordinates where any
--                    source supplies them
--   dim_date         calendar spanning the trip history
--   dim_membership   raw label -> reporting group, explicitly mapped
--
-- system_id is on the fact and on every dimension. It is what makes a
-- cross-city query either comparable or explicitly not.

CREATE OR REPLACE TABLE dim_date AS
SELECT
  d::DATE                                  AS date_key,
  CAST(year(d) AS INTEGER)                 AS year,
  CAST(month(d) AS INTEGER)                AS month,
  strftime(d, '%Y-%m')                     AS year_month,
  CAST(isodow(d) AS INTEGER)               AS iso_weekday,
  isodow(d) >= 6                           AS is_weekend,
  CASE
    WHEN month(d) IN (12, 1, 2) THEN 'winter'
    WHEN month(d) IN (3, 4, 5)  THEN 'spring'
    WHEN month(d) IN (6, 7, 8)  THEN 'summer'
    ELSE 'fall'
  END                                      AS season
FROM unnest(generate_series(
  (SELECT min(departure_ts)::DATE FROM conformed_trips),
  (SELECT max(departure_ts)::DATE FROM conformed_trips),
  INTERVAL 1 DAY)) AS t(d);

-- Raw membership labels, with a reporting group where the mapping file covers
-- them. An unmapped label yields NULL and is surfaced in the quality report
-- rather than being quietly bucketed as "casual".
CREATE OR REPLACE TABLE dim_membership AS
WITH labels AS (
  SELECT DISTINCT system_id, membership_raw
  FROM conformed_trips
  WHERE membership_raw IS NOT NULL
),
mapped AS (
  SELECT * FROM read_csv(
    getvariable('mappings_dir') || '/membership_groups.csv',
    header = true, all_varchar = true)
)
SELECT
  l.system_id,
  l.membership_raw,
  m.membership_group,
  count(*) OVER (PARTITION BY l.system_id) AS labels_in_system
FROM labels l
LEFT JOIN mapped m
  ON m.system_id = l.system_id AND m.membership_raw = l.membership_raw;

-- Every station the trips reference, plus anything the annual snapshots know.
-- Coordinates come from the snapshots (Montreal) or GBFS (loaded at spec 012);
-- a station with none is still a real station and still counted.
CREATE OR REPLACE TABLE dim_station AS
WITH usage AS (
  SELECT system_id, departure_station_id AS station_id, departure_label AS label,
         departure_ts AS ts
  FROM conformed_trips WHERE departure_station_id IS NOT NULL
  UNION ALL
  SELECT system_id, return_station_id, return_label, return_ts
  FROM conformed_trips WHERE return_station_id IS NOT NULL
),
agg AS (
  SELECT
    system_id,
    station_id,
    arg_max(label, ts)              AS station_name,
    min(ts)::DATE                   AS first_seen,
    max(ts)::DATE                   AS last_seen,
    count(*)                        AS lifetime_events
  FROM usage
  GROUP BY system_id, station_id
)
SELECT
  a.*,
  s.lat,
  s.lon,
  -- "Active" means seen in the last six months OF THAT SYSTEM'S OWN data, not
  -- of the archive as a whole: the three systems have different end dates and
  -- a shared cutoff would silently retire the ones that publish less often.
  a.last_seen >= (
    SELECT max(last_seen) - INTERVAL 6 MONTH
    FROM agg a2 WHERE a2.system_id = a.system_id
  )                                 AS is_active
FROM agg a
LEFT JOIN conformed_stations s USING (system_id, station_id);

CREATE OR REPLACE TABLE fact_trips AS
SELECT
  system_id,
  date_key,
  departure_ts,
  return_ts,
  trip_month,
  trip_year,
  departure_station_id,
  return_station_id,
  departure_label,
  return_label,
  departure_borough,
  return_borough,
  membership_raw,
  bike_id,
  is_ebike,
  duration_final_s        AS duration_s,
  distance_m,
  departure_temp_c,
  return_temp_c,
  stopover_s,
  stopover_count,
  quality_flags,
  len(quality_flags) > 0  AS has_quality_issue,
  source_period,
  source_file
FROM conformed_trips;
