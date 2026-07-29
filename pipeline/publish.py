"""Publish typed JSON aggregates from the warehouse to src/data/generated/.

No per-trip data ever reaches the browser. Everything here is an aggregate, and
the whole payload is held under a size budget that the build enforces.

Two rules this module exists to keep:

  1. Every series states the window it actually covers. The site's copy is
     derived from these files, so a partially-acquired archive produces honest
     prose automatically rather than a confident lie.
  2. A cross-city series may only contain systems the metric registry marks as
     supported. Publishing one that does not is an error here, not a judgement
     call made later by whoever is reading the chart.

Usage: python pipeline/publish.py [--db PATH] [--out DIR]
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

import common

REGISTRY = common.MAPPINGS_DIR / "metric_support.json"


class UnsupportedSeries(Exception):
    """A cross-city artifact contains a system the registry excludes."""


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def supported_systems(registry: dict, metric: str) -> list[str]:
    entry = registry["metrics"][metric]
    return sorted(k for k, v in entry["systems"].items() if v.get("supported"))


def guard(registry: dict, metric: str, systems: list[str]) -> None:
    allowed = set(supported_systems(registry, metric))
    offenders = sorted(set(systems) - allowed)
    if offenders:
        reasons = "; ".join(
            f"{s}: {registry['metrics'][metric]['systems'][s].get('reason', 'not supported')}"
            for s in offenders
        )
        raise UnsupportedSeries(
            f"metric '{metric}' would publish unsupported system(s) {offenders}. {reasons}"
        )


# Rows flagged implausible_date survived parsing but cannot be trusted. They
# stay in fact_trips and in the quality report — nothing is hidden — but they
# must not reach a published series, where a single stray row would stretch a
# chart axis back to the year 2000.
TRUSTED = "NOT list_contains(quality_flags, 'implausible_date')"


def rows(con, sql: str, params: list | None = None) -> list[dict]:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def build(con, registry: dict) -> dict[str, object]:
    art: dict[str, object] = {}

    # --- window and headline totals, per system -----------------------------
    systems = rows(con, """
      SELECT system_id,
             count(*)                              AS trips,
             -- Window excludes rows flagged implausible_date: a handful of
             -- unparseable stragglers must not define the range the site
             -- claims to cover.
             min(departure_ts) FILTER (
               NOT list_contains(quality_flags, 'implausible_date')
             )::DATE::VARCHAR                      AS first_trip,
             max(departure_ts) FILTER (
               NOT list_contains(quality_flags, 'implausible_date')
             )::DATE::VARCHAR                      AS last_trip,
             -- NOT a station count. Montreal spans three key spaces
             -- (2014-2020 codes, 2021 emplacement_pk, 2022+ names) that are
             -- not yet bridged, so this reads ~3,490 for a ~1,200-station
             -- network. Named for what it is until the GBFS bridge lands.
             count(DISTINCT departure_station_id)  AS station_identities_seen,
             sum(CASE WHEN has_quality_issue THEN 1 ELSE 0 END) AS flagged
      FROM fact_trips GROUP BY 1 ORDER BY 1
    """)
    for s in systems:
        meta = common.SYSTEMS[s["system_id"]]
        s["city"], s["system"] = meta["city"], meta["system"]

    active = {r["system_id"]: r["active_stations"] for r in rows(con, """
      SELECT system_id, count(*) AS active_stations
      FROM dim_station WHERE is_active GROUP BY 1
    """)}
    for s in systems:
        s["active_stations"] = active.get(s["system_id"], 0)

    for s_ in systems:
        s_["stations_note"] = (
            "Distinct station identities, not physical stations. Montreal's "
            "eras use three key spaces that are not yet bridged."
        )

    art["meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "common_window_first_year": registry["_window"]["common_first_year"],
        "systems": systems,
        # Stated, not implied: the site renders this rather than asserting a
        # window of its own.
        "window_note": "Each system covers the range shown. Cross-city "
                       "comparisons are restricted to the common window.",
    }

    # --- month completeness -------------------------------------------------
    # A month observed on 3 days of 31 is not a low month; it is a month we do
    # not have. Publishing it as a data point produced two lies at once: the
    # trailing partial month made Vancouver's "latest" read 26 trips against a
    # 144,105 prior month, and Vancouver's 2022-10 (37 trips, the download that
    # 500s) rendered as a ridership collapse under a lede promising that gaps
    # are drawn as gaps. Incomplete months are now excluded from every series
    # and listed in the artifact so the site can say which and why.
    incomplete = rows(con, f"""
      SELECT system_id, strftime(trip_month, '%Y-%m') AS month,
             count(DISTINCT date_key) AS days_observed,
             day(last_day(trip_month)) AS days_in_month,
             count(*) AS trips
      FROM fact_trips WHERE {TRUSTED}
      GROUP BY 1, 2, trip_month
      -- Two distinct things look alike here and must not be conflated:
      --   a month we do not HAVE          -> exclude
      --   a month the system only OPERATED part of -> keep, it is real
      -- BIXI opens mid-April and closed mid-November for most of its history,
      -- so ~16 observed days in those months is genuine ridership. A blanket
      -- coverage threshold deleted it and punched fake gaps in the chart.
      -- Exclude only a stub of a few days, or a trailing month the source has
      -- not finished publishing.
      HAVING count(DISTINCT date_key) <= 3
          OR (trip_month = (SELECT max(f2.trip_month) FROM fact_trips f2
                            WHERE f2.system_id = fact_trips.system_id)
              AND count(DISTINCT date_key) < day(last_day(trip_month)))
      ORDER BY 1, 2
    """)
    art["incomplete_months"] = incomplete
    skip = {(r["system_id"], r["month"]) for r in incomplete}

    def complete(series: list[dict]) -> list[dict]:
        return [r for r in series if (r["system_id"], r["month"]) not in skip]

    # --- trips per month, all three ----------------------------------------
    monthly = complete(rows(con, f"""
      SELECT system_id, strftime(trip_month, '%Y-%m') AS month, count(*) AS trips
      FROM fact_trips WHERE {TRUSTED} GROUP BY 1, 2 ORDER BY 1, 2
    """))
    guard(registry, "trips", sorted({r["system_id"] for r in monthly}))
    art["trips_monthly"] = monthly

    # --- seasonality: mean trips by month of year, common window ------------
    first = int(registry["_window"]["common_first_year"])
    # Seasonality averages MONTHS, so a one-day stub dragged Montreal's July
    # mean down 10% and handed the "peak riding month" title to August. Only
    # complete months count, and only whole ones inside the common window.
    seasonal = rows(con, f"""
      WITH months AS (
        SELECT system_id, trip_month, month(trip_month) AS moy,
               count(*) AS trips, count(DISTINCT date_key) AS days
        FROM fact_trips WHERE trip_year >= ? AND {TRUSTED}
        GROUP BY 1, 2, 3
        HAVING count(DISTINCT date_key) > 3
      )
      SELECT system_id, moy AS month_of_year,
             CAST(round(avg(trips)) AS BIGINT) AS mean_trips,
             count(*) AS months_averaged
      FROM months GROUP BY 1, 2 ORDER BY 1, 2
    """, [first])
    guard(registry, "seasonality", sorted({r["system_id"] for r in seasonal}))
    art["seasonality"] = {"first_year": first, "series": seasonal}

    # --- active stations over time -----------------------------------------
    stations = rows(con, f"""
      SELECT system_id, trip_year AS year,
             count(DISTINCT departure_station_id) AS stations
      FROM fact_trips WHERE {TRUSTED} GROUP BY 1, 2 ORDER BY 1, 2
    """)
    guard(registry, "active_stations", sorted({r["system_id"] for r in stations}))
    art["stations_yearly"] = stations

    # --- e-bike share: only where a signal is published ---------------------
    ebike_systems = supported_systems(registry, "ebike_share")
    ebike = rows(con, f"""
      SELECT system_id, strftime(trip_month, '%Y-%m') AS month,
             count(*) FILTER (is_ebike) AS ebike_trips,
             count(*) FILTER (is_ebike IS NOT NULL) AS classified_trips,
             count(*) AS month_trips
      FROM fact_trips
      WHERE system_id IN ({','.join('?' * len(ebike_systems))})
        AND {TRUSTED}
      GROUP BY 1, 2
      -- A month where 15 of 39,000 trips carry a bike-type field cannot state
      -- an e-bike share. Require the classified rows to be most of the month.
      HAVING count(*) FILTER (is_ebike IS NOT NULL) >= 0.5 * count(*)
      ORDER BY 1, 2
    """, ebike_systems)
    ebike = complete(ebike)
    guard(registry, "ebike_share", sorted({r["system_id"] for r in ebike}))
    art["ebike_share"] = {
        "series": ebike,
        # The gap is part of the artifact, so the chart can render it as a
        # labelled absence instead of a missing line nobody explains.
        "unsupported": {
            k: v for k, v in registry["metrics"]["ebike_share"]["systems"].items()
            if not v.get("supported")
        },
    }

    # --- duration distribution, terminated trips only -----------------------
    duration = rows(con, f"""
      SELECT system_id,
             CAST(median(duration_s) AS INTEGER)                      AS median_s,
             CAST(quantile_cont(duration_s, 0.25) AS INTEGER)         AS p25_s,
             CAST(quantile_cont(duration_s, 0.75) AS INTEGER)         AS p75_s,
             count(*)                                                 AS basis_trips
      FROM fact_trips
      WHERE return_ts IS NOT NULL AND duration_s BETWEEN 1 AND 86400
        AND {TRUSTED}
      GROUP BY 1 ORDER BY 1
    """)
    guard(registry, "duration", sorted({r["system_id"] for r in duration}))
    art["duration"] = duration

    # --- what was excluded, so the site can say so --------------------------
    art["exclusions"] = rows(con, """
      SELECT system_id,
             count(*) FILTER (list_contains(quality_flags, 'unterminated'))
                                                        AS unterminated,
             count(*) FILTER (list_contains(quality_flags, 'station_matched_by_name'))
                                                        AS station_matched_by_name,
             count(*)                                   AS total
      FROM fact_trips GROUP BY 1 ORDER BY 1
    """)
    return art


def write(art: dict[str, object], out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, payload in art.items():
        path = out / f"{name}.json"
        text = json.dumps(payload, separators=(",", ":"), default=str) + "\n"
        path.write_text(text, encoding="utf-8")
        gz = len(gzip.compress(text.encode()))
        total += gz
        print(f"  {name}.json  {len(text):>9,}B  ({gz:,}B gzip)")
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path,
                        default=common.DATA_WAREHOUSE / "bikeshare.duckdb")
    parser.add_argument("--out", type=Path, default=common.GENERATED_DIR)
    args = parser.parse_args()

    registry = load_registry()
    con = duckdb.connect(str(args.db), read_only=True)
    try:
        art = build(con, registry)
    except UnsupportedSeries as exc:
        print(f"ABORT: {exc}", file=sys.stderr)
        return 1
    finally:
        con.close()

    total = write(art, args.out)
    budget = common.PUBLISH_BUDGET_BYTES
    print(f"\ntotal {total:,}B gzip of {budget:,}B budget "
          f"({100 * total / budget:.1f}%)")
    if total > budget:
        print("ABORT: over the publish size budget", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
