-- Stage 17: work out, per file, whether its text timestamps are local or UTC.
--
-- This exists because publishers switch silently. BIXI's 2022+ epoch
-- milliseconds are UTC (handled directly in 20_clean.sql, since epoch time is
-- unambiguously UTC by definition), but Mobi ALSO published two ordinary text
-- months — 2025-05 and 2025-06 — in UTC while every other month is local.
-- Read naively, Vancouver's June 2025 peak sits at 00:00 instead of 17:00 and
-- 21.6% of its trips land between 2 and 6 a.m.
--
-- The signal is the overnight trough. Every bike share has one, it is deep,
-- and it sits around 04:00 local. A file whose trough sits at 04:00 + the
-- zone's UTC offset is published in UTC. This is derived rather than
-- hardcoded for the same reason the date order is: the next file to switch
-- will not come with a note.
--
-- Files with too few rows to have a reliable trough are left as local and
-- reported, never guessed at.

CREATE OR REPLACE TABLE file_timezone AS
WITH hourly AS (
  SELECT
    r.system_id,
    r.source_file,
    hour(parse_ts_ord(r.departure_raw, o.date_order)) AS h,
    count(*) AS n
  FROM raw_trips r
  LEFT JOIN file_date_order o
    ON o.system_id = r.system_id AND o.source_file = r.source_file
  WHERE r.departure_raw IS NOT NULL
    AND parse_ts_ord(r.departure_raw, o.date_order) IS NOT NULL
  GROUP BY 1, 2, 3
),
totals AS (
  SELECT system_id, source_file, sum(n) AS rows_parsed, arg_min(h, n) AS trough_hour
  FROM hourly GROUP BY 1, 2
),
offsets AS (
  -- Standard-time offsets. Daylight saving moves the trough by an hour, which
  -- the +/-2 tolerance below absorbs.
  SELECT * FROM (VALUES
    ('van-mobi', 8), ('mtl-bixi', 5), ('tor-bikeshare', 5)
  ) AS t(system_id, utc_offset)
)
SELECT
  t.system_id,
  t.source_file,
  t.rows_parsed,
  t.trough_hour,
  o.utc_offset,
  CASE
    WHEN t.rows_parsed < 5000                                   THEN 'unknown'
    WHEN abs(t.trough_hour - 4) <= 2                            THEN 'local'
    WHEN abs(((t.trough_hour - o.utc_offset) % 24 + 24) % 24 - 4) <= 2
                                                                THEN 'utc'
    ELSE 'unknown'
  END AS tz_basis
FROM totals t
JOIN offsets o USING (system_id);
