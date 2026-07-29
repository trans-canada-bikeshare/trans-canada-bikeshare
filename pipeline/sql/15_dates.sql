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
-- that shows neither is ambiguous and is reported rather than guessed at.

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
    count(*) AS slashed_rows
  FROM raw_trips
  WHERE departure_raw LIKE '%/%'
  GROUP BY 1, 2
)
SELECT
  *,
  CASE
    WHEN day_evidence > 0 AND month_evidence = 0 THEN 'day'
    WHEN month_evidence > 0 AND day_evidence = 0 THEN 'month'
    WHEN day_evidence > 0 AND month_evidence > 0 THEN 'conflict'
    ELSE 'ambiguous'
  END AS date_order
FROM evidence;
