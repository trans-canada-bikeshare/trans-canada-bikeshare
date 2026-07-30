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
-- ONE station resolution, materialised, used by both the dimension and the
-- fact. It was previously inlined in dim_station only, so `fact_trips` carried
-- the Montreal bridge but NOT the name bridge below it. The two tables
-- therefore disagreed for Toronto and Vancouver: 781 Toronto keys covering
-- 2,249,950 events and 266 Vancouver keys covering 529,839 existed in
-- `fact_trips` with no row in `dim_station` at all.
--
-- "Union Station" is the clean example — dim_station held one row of 543,172
-- events while fact_trips held `tor-bikeshare:7033` (487,467) and
-- `tor-bikeshare:name:union station` (55,705) as separate stations.
--
-- Spec 022 then computed flows from the fact and divided by lifetime events
-- from the dim: a partial numerator over a merged denominator. It inflated
-- Vancouver's distinct pair count by 44%, Toronto's by 5% and Montreal's not
-- at all — which is precisely the "different amount each" failure the comment
-- above warns is the worst kind for a side-by-side comparison.
CREATE OR REPLACE TABLE station_identity AS
WITH usage AS (
  SELECT system_id, departure_station_id AS station_id, departure_label AS label,
         departure_ts AS ts
  FROM conformed_trips WHERE departure_station_id IS NOT NULL
  UNION ALL
  SELECT system_id, return_station_id, return_label, return_ts
  FROM conformed_trips WHERE return_station_id IS NOT NULL
),
-- Step 1: Montreal's era-local ids collapse to one canonical identity where
-- the bridge resolves them; everything else keeps the id it had.
step1 AS (
  SELECT u.system_id,
         u.station_id                           AS source_id,
         coalesce(b.canonical_id, u.station_id) AS mid,
         u.label, u.ts
  FROM usage u
  LEFT JOIN mtl_station_bridge b ON b.era_id = u.station_id
),
mid_agg AS (
  SELECT system_id, mid,
         arg_max(label, ts) AS station_name,
         count(*)           AS lifetime_events
  FROM step1 GROUP BY 1, 2
),
-- Step 2: a station reached by NAME is the same station reached by its
-- published id. Built only from stations that HAVE a published id.
name_bridge AS (
  SELECT system_id, lower(trim(station_name)) AS key,
         arg_max(mid, lifetime_events)        AS canonical
  FROM mid_agg
  WHERE mid NOT LIKE '%:name:%' AND station_name IS NOT NULL
  GROUP BY 1, 2
),
resolved_mid AS (
  SELECT m.system_id, m.mid,
         coalesce(nb.canonical, m.mid) AS canonical_id
  FROM mid_agg m
  LEFT JOIN name_bridge nb
    ON nb.system_id = m.system_id
   AND m.mid LIKE '%:name:%'
   AND nb.key = lower(trim(m.station_name))
)
SELECT DISTINCT s.system_id, s.source_id, r.canonical_id
FROM step1 s
JOIN resolved_mid r ON r.system_id = s.system_id AND r.mid = s.mid;

CREATE OR REPLACE TABLE dim_station AS
WITH usage AS (
  SELECT system_id, departure_station_id AS station_id, departure_label AS label,
         departure_ts AS ts
  FROM conformed_trips WHERE departure_station_id IS NOT NULL
  UNION ALL
  SELECT system_id, return_station_id, return_label, return_ts
  FROM conformed_trips WHERE return_station_id IS NOT NULL
),
resolved AS (
  SELECT
    u.system_id,
    si.canonical_id                 AS station_id,
    arg_max(u.label, u.ts)          AS station_name,
    min(u.ts)                       AS first_ts,
    max(u.ts)                       AS last_ts,
    count(*)                        AS lifetime_events
  FROM usage u
  JOIN station_identity si
    ON si.system_id = u.system_id AND si.source_id = u.station_id
  GROUP BY 1, 2
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
  c.system_id,
  c.date_key,
  c.departure_ts,
  c.return_ts,
  c.trip_month,
  c.trip_year,
  -- Canonical station identity, from the SAME table dim_station uses, so the
  -- fact and the dimension agree by construction rather than by comment.
  --
  -- This previously applied only the Montreal bridge, so the claim above was
  -- false for Toronto and Vancouver: a station reached by name stayed separate
  -- here while dim_station merged it. Spec 022 divided one by the other and
  -- inflated Vancouver's distinct pair count by 44%.
  coalesce(sd.canonical_id, c.departure_station_id) AS departure_station_id,
  coalesce(sr.canonical_id, c.return_station_id)    AS return_station_id,
  c.departure_label,
  c.return_label,
  c.departure_borough,
  c.return_borough,
  c.membership_raw,
  c.bike_id,
  c.is_ebike,
  c.duration_final_s        AS duration_s,
  c.distance_m,
  c.departure_temp_c,
  c.return_temp_c,
  c.stopover_s,
  c.stopover_count,
  c.quality_flags,
  len(c.quality_flags) > 0  AS has_quality_issue,
  c.source_period,
  source_file
FROM conformed_trips c
LEFT JOIN station_identity sd
  ON sd.system_id = c.system_id AND sd.source_id = c.departure_station_id
LEFT JOIN station_identity sr
  ON sr.system_id = c.system_id AND sr.source_id = c.return_station_id;
