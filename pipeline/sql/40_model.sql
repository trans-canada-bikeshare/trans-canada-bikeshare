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
-- A station reached by name and the same station reached by its published id
-- are ONE station. Without this bridge every system's count is inflated —
-- Vancouver's by 104, Toronto's by 375 — and by a different amount each, which
-- is the worst possible failure for a side-by-side comparison.
CREATE OR REPLACE TABLE dim_station AS
WITH usage AS (
  SELECT system_id, departure_station_id AS station_id, departure_label AS label,
         departure_ts AS ts
  FROM conformed_trips WHERE departure_station_id IS NOT NULL
  UNION ALL
  SELECT system_id, return_station_id, return_label, return_ts
  FROM conformed_trips WHERE return_station_id IS NOT NULL
),
raw_agg AS (
  SELECT
    system_id,
    -- Montreal's era-local ids collapse to one canonical identity where the
    -- bridge resolves them; everything else keeps the id it had.
    coalesce(b.canonical_id, u.station_id) AS station_id,
    arg_max(u.label, u.ts)          AS station_name,
    min(u.ts)                       AS first_ts,
    max(u.ts)                       AS last_ts,
    count(*)                        AS lifetime_events
  FROM usage u
  LEFT JOIN mtl_station_bridge b ON b.era_id = u.station_id
  GROUP BY 1, 2
),
-- name -> canonical id, built only from stations that HAVE a published id
bridge AS (
  SELECT system_id, lower(trim(station_name)) AS key, arg_max(station_id, lifetime_events) AS canonical
  FROM raw_agg
  WHERE station_id NOT LIKE '%:name:%' AND station_name IS NOT NULL
  GROUP BY 1, 2
),
resolved AS (
  SELECT
    r.system_id,
    coalesce(b.canonical, r.station_id) AS station_id,
    r.station_name, r.first_ts, r.last_ts, r.lifetime_events
  FROM raw_agg r
  LEFT JOIN bridge b
    ON b.system_id = r.system_id
   AND r.station_id LIKE '%:name:%'
   AND b.key = lower(trim(r.station_name))
),
agg AS (
  SELECT
    system_id, station_id,
    arg_max(station_name, last_ts)  AS station_name,
    min(first_ts)::DATE             AS first_seen,
    max(last_ts)::DATE              AS last_seen,
    sum(lifetime_events)            AS lifetime_events
  FROM resolved
  GROUP BY system_id, station_id
)
SELECT
  a.* EXCLUDE (station_name),
  -- Montreal's id-era trip files carry no station names at all, so a
  -- canonicalised station can reach here nameless. GBFS supplies the label.
  --
  -- The label must come from whatever supplied the POSITION, or a dot is
  -- named one dock and drawn at another. Trip labels are picked by
  -- arg_max(station_name, last_ts) — last writer wins on a noisy field — and
  -- Toronto reuses retired station ids: id 7823 carries "Greenwood Ave /
  -- Sammon Ave" on 4,771 rows and "Bloor St W / Christie St" on 3, and the
  -- three won on a timestamp. That shipped two dots labelled "Bloor St W /
  -- Christie St" 7.2 km apart, and "Hanlan's Point Ferry Dock" drawn at
  -- Centre Island. Where GBFS gives a usable coordinate, GBFS also names it.
  CASE
    WHEN g.lat BETWEEN 41 AND 84 AND g.lon BETWEEN -141 AND -52
      THEN coalesce(g.name, a.station_name, s.station_name)
    ELSE coalesce(a.station_name, s.station_name)
  END                               AS station_name,
  -- Coordinates come from GBFS where the identity resolves to a live station,
  -- and from the annual snapshots otherwise (Montreal's pre-2022 files are the
  -- only source for stations GBFS no longer lists, since the feed is
  -- current-state only).
  -- Coordinates are validated, not merely preferred. BIXI's 2021 snapshot
  -- carries a station at (-1, -1) and the GBFS feed has 7 rows outside any
  -- plausible Canadian extent; placing a dot at the Gulf of Guinea is worse
  -- than showing no dot, and "no position" is already a case the page states.
  CASE WHEN coalesce(g.lat, s.lat) BETWEEN 41 AND 84
        AND coalesce(g.lon, s.lon) BETWEEN -141 AND -52
       THEN coalesce(g.lat, s.lat) END AS lat,
  CASE WHEN coalesce(g.lat, s.lat) BETWEEN 41 AND 84
        AND coalesce(g.lon, s.lon) BETWEEN -141 AND -52
       THEN coalesce(g.lon, s.lon) END AS lon,
  -- "Active" means seen in the last six months OF THAT SYSTEM'S OWN data, not
  -- of the archive as a whole: the three systems have different end dates and
  -- a shared cutoff would silently retire the ones that publish less often.
  a.last_seen >= (
    SELECT max(last_seen) - INTERVAL 6 MONTH
    FROM agg a2 WHERE a2.system_id = a.system_id
  )                                 AS is_active
FROM agg a
LEFT JOIN conformed_stations s USING (system_id, station_id)
LEFT JOIN gbfs_station g
  ON g.system_id = a.system_id
 AND g.station_id = regexp_replace(a.station_id, '^[a-z-]+:s?', '');

CREATE OR REPLACE TABLE fact_trips AS
SELECT
  system_id,
  date_key,
  departure_ts,
  return_ts,
  trip_month,
  trip_year,
  -- Canonical station identity, so the fact and dim_station agree. Without
  -- this the fact still carries Montreal's era-local keys and every
  -- station-level join silently splits one dock into three.
  coalesce(bd.canonical_id, departure_station_id) AS departure_station_id,
  coalesce(br.canonical_id, return_station_id)    AS return_station_id,
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
FROM conformed_trips c
LEFT JOIN mtl_station_bridge bd ON bd.era_id = c.departure_station_id
LEFT JOIN mtl_station_bridge br ON br.era_id = c.return_station_id;
