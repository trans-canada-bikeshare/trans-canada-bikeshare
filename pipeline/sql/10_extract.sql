-- Stage 10: land every source file as VARCHAR with headers unified by the
-- per-system era maps. Nothing is typed, cleaned or judged here — the only job
-- is to get the bytes in without losing or guessing anything.
--
-- Columns are the UNION across all three systems. A system that does not
-- publish a field leaves it NULL, and that absence is meaningful: it is what
-- spec 009's metric registry reads to decide what may be compared.

-- IF NOT EXISTS, not OR REPLACE: extract runs per system, and `--system tor`
-- must not wipe the Montreal rows loaded an hour earlier. The runner deletes
-- only the systems it is about to reload.
CREATE TABLE IF NOT EXISTS raw_trips (
  system_id              VARCHAR NOT NULL,
  source_period          VARCHAR NOT NULL,
  source_file            VARCHAR NOT NULL,

  trip_id                VARCHAR,
  departure_raw          VARCHAR,   -- text timestamp, five formats in Vancouver alone
  return_raw             VARCHAR,
  departure_ms           VARCHAR,   -- epoch milliseconds, BIXI 2022+
  return_ms              VARCHAR,

  departure_station_key  VARCHAR,   -- integer code / pk; absent for name-only eras
  return_station_key     VARCHAR,
  departure_station_name VARCHAR,
  return_station_name    VARCHAR,
  departure_lat          VARCHAR,   -- inline coordinates, BIXI 2022+ only
  departure_lon          VARCHAR,
  return_lat             VARCHAR,
  return_lon             VARCHAR,
  departure_borough      VARCHAR,
  return_borough         VARCHAR,

  duration_s             VARCHAR,
  distance_m             VARCHAR,   -- Vancouver only
  membership_raw         VARCHAR,
  bike_id                VARCHAR,
  bike_model             VARCHAR,   -- Toronto 2025+ only; the e-bike signal
  electric_bike          VARCHAR,   -- Vancouver only; the e-bike signal
  departure_temp         VARCHAR,   -- Vancouver only
  return_temp            VARCHAR,
  stopover_s             VARCHAR,   -- Vancouver only
  stopover_count         VARCHAR
);

-- Annual station snapshots. Montreal ships these inside its pre-2022 archives,
-- which is how historical Montreal coordinates exist at all — GBFS only knows
-- about stations that are live today.
CREATE TABLE IF NOT EXISTS raw_stations (
  system_id     VARCHAR NOT NULL,
  source_period VARCHAR NOT NULL,
  source_file   VARCHAR NOT NULL,
  station_key   VARCHAR,
  station_name  VARCHAR,
  lat           VARCHAR,
  lon           VARCHAR
);

CREATE TABLE IF NOT EXISTS etl_metrics (
  stage  VARCHAR NOT NULL,
  metric VARCHAR NOT NULL,
  value  BIGINT  NOT NULL
);
