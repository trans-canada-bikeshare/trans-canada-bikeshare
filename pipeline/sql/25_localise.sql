-- Stage 25: correct the files that publish text timestamps in UTC.
--
-- Only a handful of files are affected — Mobi's 2025-05 and 2025-06, and
-- Toronto's 2016 sheets and 2017 Q1/Q2 — so this rewrites ~1.3M rows rather
-- than evaluating a timezone conversion across all 135M. Doing it inline in
-- the clean SELECT segfaulted DuckDB; a targeted UPDATE is both safe and fast.
--
-- Which files are UTC is derived in 17_timezones.sql from the overnight
-- trough, never hardcoded.

UPDATE clean_trips AS c
SET departure_ts = timezone(
      CASE c.system_id
        WHEN 'mtl-bixi' THEN 'America/Montreal'
        WHEN 'tor-bikeshare' THEN 'America/Toronto'
        WHEN 'van-mobi' THEN 'America/Vancouver'
      END, c.departure_ts AT TIME ZONE 'UTC'),
    return_ts = CASE WHEN c.return_ts IS NULL THEN NULL ELSE timezone(
      CASE c.system_id
        WHEN 'mtl-bixi' THEN 'America/Montreal'
        WHEN 'tor-bikeshare' THEN 'America/Toronto'
        WHEN 'van-mobi' THEN 'America/Vancouver'
      END, c.return_ts AT TIME ZONE 'UTC') END
FROM file_timezone z
WHERE z.system_id = c.system_id
  AND z.source_file = c.source_file
  AND z.tz_basis = 'utc';
