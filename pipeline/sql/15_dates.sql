-- Stage 15: work out, per file, how its slash-separated dates are ordered.
--
-- This exists because Bike Share Toronto changed date convention MID-YEAR and
-- never said so. Verified from the data:
--
--   2017 Q1, Q2   DAY-first     13/06/2017 is 13 June
--   2017 Q3, Q4   MONTH-first   06/13/2017 is 13 June
--   2018-2023     MONTH-first
--
-- The two are indistinguishable for any day ≤ 12, so roughly 40% of rows parse
-- "successfully" under the wrong convention with the day and month silently
-- transposed. That is a worse failure than a parse error, because nothing
-- surfaces it — a June trip quietly becomes a December one.
--
-- So the order is DERIVED per file rather than assumed or hardcoded: a value
-- whose first field exceeds 12 can only be a day, and one whose second field
-- exceeds 12 can only be a month. A file that shows both is corrupt; a file
-- that shows neither is ambiguous, and etl.resolve_date_orders ABORTS on it
-- unless pipeline/mappings/date_order.json declares the order explicitly.
--
-- `year_evidence` was added by spec 029 and it is a fix, not a feature. Mobi's
-- 2025-05 is 'YYYY/MM/DD HH:MM:SS' — slash-separated ISO, in which the leading
-- field is the YEAR and there is nothing ambiguous about it. Both regexes
-- above capture one-or-two digits before a slash, so a four-digit year matches
-- neither, both counts came out zero, and the file was labelled 'ambiguous'
-- and parsed by the month-first fallback. It parsed correctly — %Y/%m/%d is in
-- that list — but for the wrong reason, and the runbook, the clean-stage log
-- and this table all reported an ambiguity the file does not have. A rule that
-- cannot see a year cannot tell a year from a coin toss.
--   Measured: 2025-05.csv has 133,643 slashed rows, one distinct first field
--   ('2025'), one distinct second field ('05'), and third fields spanning
--   01..31. That is a year, a month, and days.

CREATE OR REPLACE TABLE file_date_order AS
WITH evidence AS (
  SELECT
    system_id,
    source_file,
    count(*) FILTER (
      try_cast(regexp_extract(departure_raw, '^(\d{1,2})/', 1) AS INTEGER) > 12
    ) AS day_evidence,
    count(*) FILTER (
      try_cast(regexp_extract(departure_raw, '^\d{1,2}/(\d{1,2})/', 1) AS INTEGER) > 12
    ) AS month_evidence,
    -- A four-digit leading field is a year. No day and no month reaches 1000.
    count(*) FILTER (regexp_matches(departure_raw, '^\d{4}/')) AS year_evidence,
    count(*) AS slashed_rows
  FROM raw_trips
  WHERE departure_raw LIKE '%/%'
  GROUP BY 1, 2
)
SELECT
  *,
  CASE
    -- Year-first is checked first and on its own: it is the only one of the
    -- three that is proved by the SHAPE of the value rather than by a value
    -- large enough to rule an interpretation out.
    WHEN year_evidence > 0 AND day_evidence = 0 AND month_evidence = 0 THEN 'year'
    -- Two forms inside one file. Toronto changed convention mid-year once
    -- already; a file that changed it mid-file is not something to average.
    WHEN year_evidence > 0 THEN 'conflict'
    WHEN day_evidence > 0 AND month_evidence = 0 THEN 'day'
    WHEN month_evidence > 0 AND day_evidence = 0 THEN 'month'
    WHEN day_evidence > 0 AND month_evidence > 0 THEN 'conflict'
    ELSE 'ambiguous'
  END AS date_order
FROM evidence;
