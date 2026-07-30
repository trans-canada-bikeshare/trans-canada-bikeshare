-- Stage 35: reconcile Montreal's three station key spaces into one identity.
--
-- BIXI has published station identity three incompatible ways:
--   2014-2020  four-digit codes        (6209)
--   2021       small-int emplacement_pk (10, 188) — a DIFFERENT key space
--   2022+      the station NAME only, with inline coordinates
--
-- Counted naively that is ~3,490 "stations" for a network of roughly 1,200,
-- and no station has a history that crosses an era boundary. The GBFS feed is
-- what makes this recoverable: it carries `short_name` (the old code) and
-- `station_id` (the pk) on the same row, so the two key spaces can be joined
-- through it, and it carries the name and coordinates to reach era D.
--
-- Three matchers, strongest first. Anything unmatched keeps its era-local
-- identity and is COUNTED as unmatched — a station silently dropped would be
-- exactly the failure this project promises not to have.

CREATE OR REPLACE MACRO bridge_name(s) AS
  regexp_replace(
    regexp_replace(lower(trim(cast(s AS VARCHAR))), '\s*\([^)]*\)', '', 'g'),
    '\s*([/-])\s*', '\1', 'g');

CREATE OR REPLACE MACRO hav_m(a1, o1, a2, o2) AS
  2 * 6371000 * asin(sqrt(
    pow(sin(radians(a2 - a1) / 2), 2)
    + cos(radians(a1)) * cos(radians(a2)) * pow(sin(radians(o2 - o1) / 2), 2)));

CREATE OR REPLACE TABLE mtl_station_bridge AS
WITH gbfs AS (
  SELECT station_id, short_name, bridge_name(name) AS nm, name AS label, lat, lon
  FROM gbfs_station WHERE system_id = 'mtl-bixi'
),
-- 1. Key eras join to GBFS directly, which is exact.
code_map AS (
  SELECT 'mtl-bixi:' || short_name AS era_id, station_id, 'code' AS via
  FROM gbfs WHERE short_name IS NOT NULL
),
pk_map AS (
  SELECT 'mtl-bixi:' || station_id AS era_id, station_id, 'pk' AS via FROM gbfs
),
-- 2. Era D: every distinct published name, with its median position.
name_obs AS (
  SELECT
    bridge_name(departure_station_name)              AS nm,
    'mtl-bixi:name:' || nullif(trim(regexp_replace(lower(cast(departure_station_name AS VARCHAR)), '\s+', ' ', 'g')), '') AS era_id,
    median(departure_lat)                            AS la,
    median(departure_lon)                            AS lo
  FROM clean_trips
  WHERE system_id = 'mtl-bixi'
    AND departure_station_key IS NULL
    AND departure_station_name IS NOT NULL
  GROUP BY 1, 2
),
name_exact AS (
  SELECT o.era_id, g.station_id, 'name' AS via
  FROM name_obs o JOIN gbfs g USING (nm)
),
-- 3. Whatever the name misses, position resolves — but only when the nearest
--    dock is unambiguous. Two distinct stations 40 m apart must not merge, so
--    the runner-up has to be at least 100 m away.
ranked AS (
  SELECT
    o.era_id, g.station_id,
    hav_m(o.la, o.lo, g.lat, g.lon) AS dist,
    row_number() OVER (PARTITION BY o.era_id ORDER BY hav_m(o.la, o.lo, g.lat, g.lon)) AS rn,
    lead(hav_m(o.la, o.lo, g.lat, g.lon)) OVER (
      PARTITION BY o.era_id ORDER BY hav_m(o.la, o.lo, g.lat, g.lon)) AS next_dist
  FROM name_obs o
  CROSS JOIN gbfs g
  WHERE o.la IS NOT NULL
    AND o.era_id NOT IN (SELECT era_id FROM name_exact)
),
name_geo AS (
  SELECT era_id, station_id, 'geo' AS via
  FROM ranked
  WHERE rn = 1 AND dist <= 50 AND (next_dist IS NULL OR next_dist > 100)
),
-- 4. pk-era stations the live feed has since dropped.
--
-- `pk_map` above joins to CURRENT GBFS, so a 2021 station BIXI has since
-- removed never bridges and keeps its era-local id — landing on the map as a
-- second dot beside its own bridged twin. 35 docks shipped that way, median
-- separation 9 m and several at exactly 0 m: `de Gaspé / Villeray` was both
-- `mtl-bixi:s357` (213,491 events) and `mtl-bixi:767` (15,611), one dock split
-- across two pins with its traffic and net flow divided between them.
--
-- The 2021 BIXI snapshot in `conformed_stations` still knows their name and
-- position, so they can be reached the same way era D is. Same guard as above:
-- the nearest dock must be within 50 m and the runner-up beyond 100 m, so two
-- genuinely distinct stations cannot merge.
pk_orphan AS (
  SELECT cs.station_id AS era_id,
         bridge_name(cs.station_name) AS nm,
         cs.station_name AS label,
         cs.lat AS la, cs.lon AS lo,
         cs.lat BETWEEN 41 AND 84 AND cs.lon BETWEEN -141 AND -52 AS placed
  FROM conformed_stations cs
  WHERE cs.system_id = 'mtl-bixi'
    AND cs.station_id NOT LIKE '%:name:%'
    AND cs.station_id NOT IN (SELECT era_id FROM code_map)
    AND cs.station_id NOT IN (SELECT era_id FROM pk_map)
),
-- The name key deliberately drops the parenthetical cross-streets, so
-- "Parc MacDonald (Earnscliffe / Dupuis)" and "Parc MacDonald (Clanranald /
-- Isabella)" collapse to the same key while being 321 m apart — two docks at
-- one park, not one dock. A name match therefore has to agree with a position
-- too, the same principle the geo matcher below applies.
--
-- Where the snapshot has no usable position — BIXI's 2021 file carries
-- "Smith / Peel" at (-1, -1) — the full published names must match exactly,
-- parenthetical included, since there is nothing else to check against.
pk_orphan_name AS (
  SELECT o.era_id, g.station_id, 'pk-name' AS via
  FROM pk_orphan o JOIN gbfs g USING (nm)
  WHERE o.nm IS NOT NULL
    AND (
      (o.placed AND hav_m(o.la, o.lo, g.lat, g.lon) <= 100)
      OR (NOT o.placed AND lower(trim(o.label)) = lower(trim(g.label)))
    )
),
pk_ranked AS (
  SELECT
    o.era_id, g.station_id,
    hav_m(o.la, o.lo, g.lat, g.lon) AS dist,
    row_number() OVER (PARTITION BY o.era_id ORDER BY hav_m(o.la, o.lo, g.lat, g.lon)) AS rn,
    lead(hav_m(o.la, o.lo, g.lat, g.lon)) OVER (
      PARTITION BY o.era_id ORDER BY hav_m(o.la, o.lo, g.lat, g.lon)) AS next_dist
  FROM pk_orphan o
  CROSS JOIN gbfs g
  WHERE o.la IS NOT NULL
    AND o.era_id NOT IN (SELECT era_id FROM pk_orphan_name)
),
pk_geo AS (
  SELECT era_id, station_id, 'pk-geo' AS via
  FROM pk_ranked
  WHERE rn = 1 AND dist <= 50 AND (next_dist IS NULL OR next_dist > 100)
)
SELECT DISTINCT ON (era_id)
  era_id,
  'mtl-bixi:s' || station_id AS canonical_id,
  via
FROM (
  SELECT * FROM code_map
  UNION ALL SELECT * FROM pk_map
  UNION ALL SELECT * FROM name_exact
  UNION ALL SELECT * FROM name_geo
  UNION ALL SELECT * FROM pk_orphan_name
  UNION ALL SELECT * FROM pk_geo
)
ORDER BY era_id, CASE via WHEN 'code' THEN 1 WHEN 'pk' THEN 2
                          WHEN 'name' THEN 3 WHEN 'pk-name' THEN 4
                          WHEN 'pk-geo' THEN 5 ELSE 6 END;
