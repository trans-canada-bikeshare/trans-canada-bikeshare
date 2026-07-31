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
import forecast

REGISTRY = common.MAPPINGS_DIR / "metric_support.json"


class UnsupportedSeries(Exception):
    """A cross-city artifact contains a system the registry excludes."""


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def supported_systems(registry: dict, metric: str) -> list[str]:
    entry = registry["metrics"][metric]
    return sorted(k for k, v in entry["systems"].items() if v.get("supported"))


def partial_systems(registry: dict, metric: str) -> list[str]:
    """Systems that publish this metric for only part of their range.

    A third case the registry has always expressed and nothing enforced.
    Montreal carries `is_member` for 2014-2021 and loses it at the 2022 format
    break, so it is neither supported (a column beside the others would imply a
    comparison that stops five years early) nor unsupported ("not published"
    would be false for 35 million labelled trips).

    A partial system is admitted ONLY into a metric the registry marks not
    comparable. The audit demonstrated that without this condition, adding
    `partial_until` to any system under `trips` would have opened a fully
    comparable cross-city series to a fragment of one — the exact reading the
    registry exists to prevent.
    """
    entry = registry["metrics"][metric]
    if entry.get("comparable"):
        return []
    return sorted(k for k, v in entry["systems"].items()
                  if not v.get("supported") and v.get("partial_until"))


def guard(registry: dict, metric: str, systems: list[str]) -> None:
    allowed = set(supported_systems(registry, metric))
    allowed |= set(partial_systems(registry, metric))
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
             -- (2014-2020 codes, 2021 emplacement_pk, 2022+ names). The GBFS
             -- bridge in 35_bridge.sql now resolves most of them, taking this
             -- from ~3,490 to 1,776, but 613 name-era and 85 pk-era identities
             -- remain unmatched — so it is still identities, not stations.
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
            "three era key spaces are bridged to GBFS where they match; the "
            "identities that do not still count separately."
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

    # The same exclusion, pushed into SQL. Series aggregated by something other
    # than a month cannot filter afterwards: a day inside a three-day stub is
    # still a day, and it lands in a yearly mean as if it were a normal one.
    # Sorted so the parameter list is stable and the artifacts byte-reproduce.
    skip_keys = sorted(f"{s}|{m}" for s, m in skip)

    def complete_months(alias: str = "") -> str:
        """A SQL predicate dropping the months `incomplete_months` lists.

        Takes a table alias because one caller joins fact_trips against another
        relation carrying `system_id`, where an unqualified reference is
        ambiguous rather than merely untidy.
        """
        if not skip_keys:
            return ""
        p = f"{alias}." if alias else ""
        return (
            f" AND ({p}system_id || '|' || strftime({p}trip_month, '%Y-%m')) NOT IN ("
            + ",".join("?" * len(skip_keys)) + ")"
        )

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

    # --- stations with a position ------------------------------------------
    # Keys are terse because this is by far the largest artifact the site
    # ships. A station with no coordinates is NOT placed at a guess — it is
    # left out and counted, and the page states the count.
    # One threshold, referenced everywhere. It was previously typed three
    # times — the filter, the published constant the page renders, and the
    # omission count — so changing one would have left the page stating a
    # number that no longer matched the stations it was describing.
    MIN_EVENTS = 100
    station_rows = rows(con, f"""
      SELECT system_id, station_id, station_name, lat, lon,
             lifetime_events, is_active
      FROM dim_station
      WHERE lat IS NOT NULL AND lifetime_events >= {MIN_EVENTS}
      -- station_id breaks the tie, and it is not decoration. `ORDER BY
      -- system_id, lifetime_events DESC` is not a TOTAL order: 26 of the 2,333
      -- drawn stations sit in 13 groups sharing an event count, and DuckDB
      -- returns tied rows in whatever order the scan produced. Two publish runs
      -- over two builds of the same warehouse emitted the same 2,333 stations
      -- with 4 positions swapped — identical data, different bytes, and
      -- `make check-artifacts` byte-compares. So the freshness gate would have
      -- failed for anyone who rebuilt the warehouse, which is precisely the
      -- person it exists to serve. Found by spec 029 rebuilding clean → model
      -- and re-publishing.
      --   The same class was fixed once already, in quality_report.py's bridge
      -- table, and its comment says why: "a bare ORDER BY 2 DESC let two runs
      -- over one warehouse produce two different documents". Every ordering
      -- that reaches an artifact needs a total order.
      ORDER BY system_id, lifetime_events DESC, station_id
    """)
    # A per-system series across all three cities is exactly what the registry
    # governs, and this artifact skipped it while every other one called guard().
    guard(registry, "active_stations", sorted({r["system_id"] for r in station_rows}))
    # Split deliberately: the counts are needed to render the section's prose,
    # the pin list only once a reader reaches the maps. Keeping them together
    # put 260 KB of station data in the initial bundle for a section most
    # readers never scroll to.
    art["stations_meta"] = {
        "min_lifetime_events": MIN_EVENTS,
        "omitted": rows(con, f"""
          SELECT system_id,
                 count(*) FILTER (lat IS NULL)                      AS no_coordinates,
                 count(*) FILTER (lat IS NOT NULL
                                  AND lifetime_events < {MIN_EVENTS}) AS below_threshold,
                 count(*)                                           AS total
          FROM dim_station GROUP BY 1 ORDER BY 1
        """),
    }
    # Net flow per station: returns minus departures, one integer. The rate a
    # reader cares about is net/events, and `t` is already published — deriving
    # it in the browser avoids rounding the same quantity twice.
    #
    # Basis note. `f` and `t` do NOT count the same events, in two ways:
    #
    #   1. `t` comes from dim_station, built without the TRUSTED filter, while
    #      this query applies it. That is 2 events in 271 million, one Toronto
    #      row, and cannot move a rate at any precision the site shows.
    #   2. `f` counts only trips with BOTH ends recorded; `t` counts every
    #      event, so it includes the departure of each of the 293,688 trips
    #      whose return was never recorded. Worst case for any published
    #      station is 1.44% of its `t` (Oakdale Community Centre, 5 of 348).
    #
    # The second is a consequence of making net flow linked-only, and an
    # earlier version of this comment still claimed the two differed "by the
    # flagged rows only". The page states the same thing in its own words:
    # unreturned trips are out of net flow but their departure is in the dot
    # size. Stated rather than silently reconciled.
    # Both ends must be known. An earlier version counted the departure leg of
    # every trip but the return leg only where a return station was recorded,
    # so each unreturned trip left a phantom -1 at its origin: 272,088 of them
    # in Montreal, which biased that whole map amber for a reason that is a
    # gap in the data rather than a movement of bikes. A trip whose return was
    # never recorded is missing information, not a bike removed from the city.
    #
    # Restricting to linked trips makes the system-wide sum exactly zero, which
    # is the invariant net flow should satisfy — every trip is one departure and
    # one return — and src/flows.test.ts now asserts it.
    net = {
        (r["system_id"], r["station_id"]): r["net"]
        for r in rows(con, f"""
          WITH linked AS (
            SELECT system_id, departure_station_id, return_station_id
            FROM fact_trips
            WHERE {TRUSTED}
              AND departure_station_id IS NOT NULL
              AND return_station_id IS NOT NULL
          ), ev AS (
            SELECT system_id, departure_station_id AS sid, -1 AS d FROM linked
            UNION ALL
            SELECT system_id, return_station_id AS sid, 1 AS d FROM linked
          )
          SELECT system_id, sid AS station_id, sum(d)::BIGINT AS net
          FROM ev GROUP BY 1, 2
        """)
    }
    art["stations"] = {
        "stations": [
            {
                "s": r["system_id"],
                "i": r["station_id"].split(":")[-1],
                "n": r["station_name"],
                "y": round(r["lat"], 5),
                "x": round(r["lon"], 5),
                "t": r["lifetime_events"],
                "a": bool(r["is_active"]),
                # A station with events but no LINKED trip has no net flow and
                # is absent here. One such station exists (Montreal, 1 event);
                # it never reaches this lookup only because of the 100-event
                # threshold. Fail loudly rather than defaulting to zero, which
                # would render as "perfectly balanced".
                "f": net[(r["system_id"], r["station_id"])],
            }
            for r in station_rows
        ],
    }

    # --- membership mix ------------------------------------------------------
    # Two systems publish this for their whole range; Montreal publishes it for
    # 2014-2021 and loses it at the 2022 format break. Its series ships under a
    # separate key so it is never read as a third comparable column, and never
    # hidden either — "not published" would be false for 35 million labelled
    # trips.
    MEMBERSHIP = f"""
      SELECT f.system_id AS system_id,
             strftime(f.trip_month, '%Y-%m') AS month,
             count(*) FILTER (m.membership_group = 'member')     AS member,
             count(*) FILTER (m.membership_group = 'casual')     AS casual,
             count(*) FILTER (m.membership_group NOT IN ('member','casual')) AS other,
             count(*) FILTER (f.membership_raw IS NULL)          AS unlabelled,
             count(*)                                            AS trips
      FROM fact_trips f
      LEFT JOIN dim_membership m
        ON m.system_id = f.system_id AND m.membership_raw = f.membership_raw
      WHERE {TRUSTED} AND f.system_id = ?
      GROUP BY 1, 2, f.trip_month ORDER BY 1, 2
    """
    # An unmapped label must stop the run rather than land in a bucket by
    # resemblance. dim_membership maps 93 labels and "Maintenance" deliberately
    # maps to `operational`, which is neither member nor casual.
    unmapped = rows(con, f"""
      SELECT f.system_id, f.membership_raw, count(*) AS n
      FROM fact_trips f
      LEFT JOIN dim_membership m
        ON m.system_id = f.system_id AND m.membership_raw = f.membership_raw
      WHERE {TRUSTED} AND f.membership_raw IS NOT NULL
        AND m.membership_group IS NULL
      GROUP BY 1, 2 ORDER BY 3 DESC
    """)
    if unmapped:
        raise SystemExit(
            "publish: unmapped membership label(s), which would silently "
            f"vanish from every share: {[(r['system_id'], r['membership_raw']) for r in unmapped[:5]]}"
        )

    # Bike Share Toronto's member label is corrupted in its published files —
    # but the corruption is FILE-SCOPED, and it begins at 2021-10, not at the
    # 2018 vocabulary change this code first assumed. Daily member share steps
    # at file boundaries and nowhere else:
    #
    #   2021-09-30  68.2%  ->  2021-10-01  37.8%     hard step down
    #   2021-11-30  35.4%  ->  2021-12-01  78.9%     hard recovery
    #   2022-06-30  19.2%  ->  2022-07-01  35.5%     hard step
    #   ... decaying file by file until the label is absent entirely from
    #   2023-09, while ridership is at its yearly peak.
    #
    # 2018-2019 are indistinguishable from the clean eras by two independent
    # tests: monthly share tracks 2017 within a couple of points across the
    # whole seasonal cycle, and the behavioural discriminant (member minus
    # casual commute-hour rate) runs 12-20pp in 2016-2019 exactly as it does
    # before and after, collapsing only from 2022. An earlier version of this
    # exclusion used the vocabulary change at 2018-01 as its boundary and
    # withheld 45 extra months — 10,092,788 trips showing no sign of the
    # defect. The vocabulary was a tidy boundary, not the true one; the file
    # steps are the true one. Recorded in docs/decisions.md.
    #
    # From 2021-10 the era is a patchwork (2021-12 alone looks clean inside
    # it), so the withheld window is the contiguous span from the first
    # corrupted file to the last: 2021-10..2023-12.
    #
    # LIFT THIS if Toronto ever republishes those months with labels intact.
    UNRELIABLE_LABEL_ERAS = {
        "tor-bikeshare": [("2021-10", "2023-12")],
    }

    def usable(row: dict) -> bool:
        for lo, hi in UNRELIABLE_LABEL_ERAS.get(row["system_id"], []):
            if lo <= row["month"] <= hi:
                return False
        # Structural, any system: a month publishing only one group has
        # stopped publishing the distinction at all.
        if not (row["member"] > 0 and row["casual"] > 0):
            return False
        # Also structural: a month where MOST trips carry no label is not the
        # same measurement as its neighbours. Vancouver 2025-05 is unlabelled
        # for its first twenty days and labelled for its last eleven; the
        # published share would be computed on a third of the month and
        # nothing on the chart would say so.
        if row["unlabelled"] > row["member"] + row["casual"]:
            return False
        return True

    supported = supported_systems(registry, "membership_mix")
    partial = partial_systems(registry, "membership_mix")
    all_supported = [r for s in supported for r in complete(rows(con, MEMBERSHIP, [s]))]
    all_partial = [r for s in partial for r in complete(rows(con, MEMBERSHIP, [s]))
                   if r["member"] + r["casual"] > 0]
    member_series = [r for r in all_supported if usable(r)]
    partial_series = [r for r in all_partial if usable(r)]
    # Not dropped silently. The page states these and the quality report
    # carries them, because a month the source stopped labelling is a fact
    # about the source, not an absence.
    unlabelled_months = [
        {**{k: r[k] for k in ("system_id", "month", "member", "casual", "trips")},
         # Which rule removed it, so the page can distinguish "the source
         # published no distinction" from "we judged the label unreliable".
         "basis": ("labelling era unreliable"
                   if any(lo <= r["month"] <= hi
                          for lo, hi in UNRELIABLE_LABEL_ERAS.get(r["system_id"], []))
                   else "mostly unlabelled"
                   if r["unlabelled"] > r["member"] + r["casual"]
                   else "no distinction published")}
        for r in all_supported + all_partial if not usable(r)
    ]
    guard(registry, "membership_mix",
          sorted({r["system_id"] for r in member_series + partial_series}))
    art["membership"] = {
        "series": member_series,
        # Kept apart deliberately. The site renders it as its own panel with
        # the end of its coverage stated, not as a line beside the other two.
        "partial": partial_series,
        "partial_note": {
            s: registry["metrics"]["membership_mix"]["systems"][s]
            for s in partial
        },
        "unsupported": {
            s: v for s, v in registry["metrics"]["membership_mix"]["systems"].items()
            if not v.get("supported") and not v.get("partial_until")
        },
        # Months the source published trips for but stopped labelling.
        "label_lost": unlabelled_months,
        # How many distinct pass labels each system publishes. The page says
        # so, and an earlier version said "ninety" for Vancouver when it is 87
        # — a number typed by hand in a paragraph where everything else was
        # derived.
        "label_counts": {
            r["system_id"]: r["labels"] for r in rows(con, """
              SELECT system_id, count(*) AS labels
              FROM dim_membership GROUP BY 1 ORDER BY 1
            """)
        },
    }

    # --- station flows ------------------------------------------------------
    # The OD matrix is not shippable: 1,189,574 distinct pairs for Montreal
    # alone. Every pair list here is a truncation, so the truncation ships as a
    # number — total pairs, and the share the shown ones carry.
    #
    # It is also not comparable. The 300 busiest pairs carry 19.08% of
    # Vancouver's linked trips and 3.35% of Montreal's, so three top-N lists
    # side by side would imply a like-for-like reading that does not hold. The
    # CONCENTRATION is the comparable metric — same definition, same window,
    # every system — and the pair lists are per-city detail, labelled as such.
    # Eight, and with names denormalised. The pair keys alone are useless to
    # the page: resolving them needs stations.json, which is lazily loaded for
    # the maps and may never arrive. An earlier version shipped 250 bare-key
    # pairs — 38 KB no surface could render — and then 20 while rendering 5,
    # so "ship what is drawn" was still not true. Eight ship and eight render.
    TOP_PAIRS = 8
    pair_stats = rows(con, f"""
      WITH p AS (
        SELECT system_id, departure_station_id AS a, return_station_id AS b,
               count(*) AS n
        FROM fact_trips
        WHERE {TRUSTED} AND departure_station_id IS NOT NULL
          AND return_station_id IS NOT NULL
        GROUP BY 1, 2, 3
      ), ranked AS (
        SELECT *, row_number() OVER (PARTITION BY system_id ORDER BY n DESC, a, b) AS rk
        FROM p
      )
      SELECT system_id,
             count(*)                                   AS pairs_total,
             sum(n)                                     AS linked_trips,
             sum(n) FILTER (rk <= 10)                   AS top_10,
             sum(n) FILTER (rk <= 100)                  AS top_100,
             sum(n) FILTER (rk <= 1000)                 AS top_1000,
             sum(n) FILTER (rk <= {TOP_PAIRS})          AS top_shown
      FROM ranked GROUP BY 1 ORDER BY 1
    """)
    guard(registry, "station_flows", sorted({r["system_id"] for r in pair_stats}))

    top_pairs = rows(con, f"""
      WITH p AS (
        SELECT system_id, departure_station_id AS a, return_station_id AS b,
               count(*) AS n
        FROM fact_trips
        WHERE {TRUSTED} AND departure_station_id IS NOT NULL
          AND return_station_id IS NOT NULL
        GROUP BY 1, 2, 3
      ), ranked AS (
        -- Deterministic tie-break, so the artifact byte-reproduces.
        SELECT *, row_number() OVER (PARTITION BY system_id ORDER BY n DESC, a, b) AS rk
        FROM p
      )
      SELECT r.system_id, r.a, r.b, r.n,
             da.station_name AS a_name, db.station_name AS b_name
      FROM ranked r
      LEFT JOIN dim_station da
        ON da.system_id = r.system_id AND da.station_id = r.a
      LEFT JOIN dim_station db
        ON db.system_id = r.system_id AND db.station_id = r.b
      WHERE r.rk <= {TOP_PAIRS}
      ORDER BY r.system_id, r.n DESC, r.a, r.b
    """)
    # A named pair whose name is missing would render as an empty row. There is
    # no honest fallback for "which dock is this", so stop instead.
    nameless = [r for r in top_pairs if not r["a_name"] or not r["b_name"]]
    if nameless:
        raise SystemExit(
            f"publish: {len(nameless)} top pair(s) have an unnamed endpoint, "
            f"first {nameless[0]['a']} -> {nameless[0]['b']}"
        )

    # Round trips are a departure and a return at the same station, so they
    # cancel in net flow and contribute nothing to imbalance. They are still
    # trips, and Vancouver's share is three times the other two, which is a
    # real difference in how the network is used rather than a quirk.
    round_trips = {
        r["system_id"]: r for r in rows(con, f"""
          SELECT system_id,
                 count(*) FILTER (departure_station_id = return_station_id) AS round_trips,
                 count(*) FILTER (return_station_id IS NULL)                AS no_return_station,
                 count(*)                                                   AS trips
          FROM fact_trips WHERE {TRUSTED} GROUP BY 1 ORDER BY 1
        """)
    }
    art["flows"] = {
        "top_pairs_shown": TOP_PAIRS,
        "systems": [
            {
                "system_id": s["system_id"],
                "pairs_total": s["pairs_total"],
                "linked_trips": s["linked_trips"],
                "shown_trips": s["top_shown"],
                "top_10": s["top_10"],
                "top_100": s["top_100"],
                "top_1000": s["top_1000"],
                "round_trips": round_trips[s["system_id"]]["round_trips"],
                "no_return_station": round_trips[s["system_id"]]["no_return_station"],
                "trips": round_trips[s["system_id"]]["trips"],
            }
            for s in pair_stats
        ],
        "pairs": [
            {
                "s": r["system_id"],
                "a": r["a_name"],
                "b": r["b_name"],
                "n": r["n"],
                # A pair whose two ends are the same dock is a round trip, and
                # reads very differently from a commute. Flagged rather than
                # filtered, because for Vancouver they are the top pairs.
                "r": r["a"] == r["b"],
            }
            for r in top_pairs
        ],
    }

    # --- weather-driven ridership model, one per system ---------------------
    # Coefficients and fit statistics, never predictions: the browser computes
    # the number so a reader can move the inputs, and every prediction the site
    # draws is reproducible from figures visible in the artifact. The training
    # decisions live in pipeline/forecast.py, next to the code that makes them.
    forecast_art = forecast.build(con, first_year=first, trusted=TRUSTED)
    guard(registry, "forecast",
          sorted({m["system_id"] for m in forecast_art["models"]}))
    art["forecast"] = forecast_art
    # --- rebalancing pressure ------------------------------------------------
    # Two views of one quantity, both from trip records alone, and both DERIVED
    # LOWER BOUNDS rather than observations. Nothing in any of these archives
    # records a bike being moved by a van; what is recorded is where bikes
    # started and finished, and the imbalance that leaves behind.
    #
    # Window. The hour-of-day profile uses the registry's common window (2017
    # onward), because this metric is marked comparable and the registry says a
    # comparable series defaults to the window all three publish. The choice was
    # measured rather than assumed: against a 2025-onward window, no hour of any
    # system's profile moves by more than 0.11 percentage points of its linked
    # trips, and the profiles correlate at r >= 0.992. The common window buys
    # 124 million linked trips for a shape that barely differs, and it is the
    # same window for all three, which is what like-for-like means here.
    HOURLY_FIRST_YEAR = first
    hourly = rows(con, f"""
      WITH linked AS (
        SELECT system_id, departure_ts, return_ts
        FROM fact_trips
        WHERE {TRUSTED}
          AND departure_station_id IS NOT NULL
          AND return_station_id IS NOT NULL
          AND return_ts IS NOT NULL
          AND trip_year >= ?
          {complete_months()}
      ), ev AS (
        SELECT system_id, hour(departure_ts) AS h, 1 AS dep, 0 AS ret FROM linked
        UNION ALL
        SELECT system_id, hour(return_ts)    AS h, 0 AS dep, 1 AS ret FROM linked
      )
      SELECT system_id, h AS hour,
             sum(dep)::BIGINT AS departures,
             sum(ret)::BIGINT AS returns
      FROM ev GROUP BY 1, 2 ORDER BY 1, 2
    """, [HOURLY_FIRST_YEAR, *skip_keys])
    guard(registry, "rebalancing_pressure", sorted({r["system_id"] for r in hourly}))

    # Denominators for the chart, and the measured timestamp grid. Mobi
    # publishes departure and return times ON THE HOUR and nothing finer, so
    # Vancouver's hour buckets are the source's own labels rather than a bucket
    # this pipeline computed. That is a real qualification on an hour-of-day
    # comparison and the page states it — derived from `on_hour_grid`, not
    # asserted in prose.
    hourly_basis = rows(con, f"""
      SELECT system_id,
             count(*)::BIGINT                            AS linked_trips,
             count(DISTINCT date_key)::BIGINT            AS days,
             -- epoch_ms, not epoch: BIXI's 2022+ era publishes milliseconds,
             -- and casting a float second count to BIGINT would round a
             -- 3600.4-second offset onto the hour it is not on.
             count(*) FILTER (
               epoch_ms(departure_ts) % 3600000 = 0
               AND epoch_ms(return_ts) % 3600000 = 0
             )::BIGINT                                   AS on_hour_grid
      FROM fact_trips
      WHERE {TRUSTED}
        AND departure_station_id IS NOT NULL
        AND return_station_id IS NOT NULL
        AND return_ts IS NOT NULL
        AND trip_year >= ?
        {complete_months()}
      GROUP BY 1 ORDER BY 1
    """, [HOURLY_FIRST_YEAR, *skip_keys])

    # Implied minimum daily rebalancing, per year.
    #
    # Each event is dated by its OWN timestamp — a departure by the day it left,
    # a return by the day it arrived — because that is what a dock actually
    # sees. A day counts only if the system had at least one linked DEPARTURE on
    # it. Without that condition the archive's trailing edge invents days: 21
    # dates in July 2026 carry Montreal returns from June departures and no
    # departures at all, and one of them (2026-07-01, 617 returns against a
    # 3,000-a-day norm) diluted Montreal's mean by 3.8%. The same edge exists
    # for Toronto at 2026-04-01. A day the system did not operate is not a day.
    rebalancing = rows(con, f"""
      WITH linked AS (
        SELECT system_id, trip_year, trip_month,
               departure_ts, departure_station_id, return_ts, return_station_id
        FROM fact_trips
        WHERE {TRUSTED}
          AND departure_station_id IS NOT NULL
          AND return_station_id IS NOT NULL
          AND return_ts IS NOT NULL
          {complete_months()}
      ), opday AS (
        SELECT DISTINCT system_id, trip_year, departure_ts::DATE AS d FROM linked
      ), ev AS (
        SELECT system_id, departure_ts::DATE AS d, departure_station_id AS sid,
               -1 AS v FROM linked
        UNION ALL
        SELECT system_id, return_ts::DATE AS d, return_station_id AS sid,
               1 AS v FROM linked
      ), st AS (
        SELECT o.system_id, o.trip_year, e.d, e.sid, sum(e.v) AS net
        FROM ev e JOIN opday o ON o.system_id = e.system_id AND o.d = e.d
        GROUP BY 1, 2, 3, 4
      ), dayagg AS (
        SELECT system_id, trip_year, d, sum(abs(net)) AS abs_net
        FROM st GROUP BY 1, 2, 3
      ), yr AS (
        SELECT system_id, trip_year,
               count(*)::BIGINT       AS n_days,
               sum(abs_net)::BIGINT   AS abs_net
        FROM dayagg GROUP BY 1, 2
      ), tr AS (
        SELECT system_id, trip_year,
               count(*)::BIGINT                     AS linked_trips,
               count(DISTINCT trip_month)::BIGINT   AS n_months
        FROM linked GROUP BY 1, 2
      )
      SELECT y.system_id, y.trip_year AS year, y.n_days AS days,
             t.n_months AS months, y.abs_net, t.linked_trips
      FROM yr y JOIN tr t
        ON t.system_id = y.system_id AND t.trip_year = y.trip_year
      ORDER BY 1, 2
    """, [*skip_keys])
    guard(registry, "rebalancing_pressure",
          sorted({r["system_id"] for r in rebalancing}))

    # Which years the archive covers end to end. A year clipped by the edge of
    # the archive cannot be told apart from a year the system only operated part
    # of — Montreal's 2014 opens in April because BIXI opens in April, and its
    # 2026 stops in June because the archive does. Both look identical from
    # inside the data, so the chart draws only years the archive fully covers
    # and the page says how many it dropped.
    span = {s["system_id"]: (s["first_trip"], s["last_trip"]) for s in systems}
    for r in rebalancing:
        first_trip, last_trip = span[r["system_id"]]
        r["full_year"] = (first_trip <= f"{r['year']}-01-01"
                          and last_trip >= f"{r['year']}-12-31")

    # The latest calendar year every system covers end to end. The headline
    # comparison uses it so all three are read over the same 365 days rather
    # than over whatever each one's archive happens to end on.
    full_years = {
        s: {r["year"] for r in rebalancing
            if r["system_id"] == s and r["full_year"]}
        for s in {r["system_id"] for r in rebalancing}
    }
    shared_full = set.intersection(*full_years.values()) if full_years else set()
    art["rebalancing"] = {
        "hourly_first_year": HOURLY_FIRST_YEAR,
        "hourly": hourly,
        "hourly_basis": hourly_basis,
        "yearly": rebalancing,
        "headline_year": max(shared_full) if shared_full else None,
        # Carried from the registry so the caveat cannot drift away from the
        # number it qualifies: the page renders this string, it does not
        # paraphrase it.
        "caveat": registry["metrics"]["rebalancing_pressure"]["caveat"],
        "qualified": {
            s: v for s, v in
            registry["metrics"]["rebalancing_pressure"]["systems"].items()
            if v.get("qualified")
        },
    }

    # --- dwell at a dock -----------------------------------------------------
    # Which years can carry it at all, measured rather than listed. A year is
    # admitted only if nearly every trip in it names a bike: a chain built from
    # a partly-identified year silently skips the trips it cannot see, so a
    # bike's "next departure" is whichever later trip happens to carry an id,
    # and the interval between them is not dwell.
    BIKE_ID_MIN_COVERAGE = 0.99
    coverage = rows(con, f"""
      SELECT system_id, trip_year AS year,
             count(*)::BIGINT           AS trips,
             count(bike_id)::BIGINT     AS with_bike_id
      FROM fact_trips
      WHERE {TRUSTED} {complete_months()}
      GROUP BY 1, 2 ORDER BY 1, 2
    """, [*skip_keys])
    for c in coverage:
        c["coverage"] = c["with_bike_id"] / c["trips"] if c["trips"] else 0.0

    # Contiguous runs of admitted years. The blocks matter, not just the years:
    # a chain must never step across a withheld era, or Vancouver's last 2020
    # return pairs with its first 2024 departure and reports a three-year dwell.
    eras: list[tuple[str, int, int]] = []
    for c in coverage:
        if c["coverage"] < BIKE_ID_MIN_COVERAGE:
            continue
        if eras and eras[-1][0] == c["system_id"] and eras[-1][2] == c["year"] - 1:
            eras[-1] = (eras[-1][0], eras[-1][1], c["year"])
        else:
            eras.append((c["system_id"], c["year"], c["year"]))

    dwell: list[dict] = []
    if eras:
        values = ",".join("(?,?,?)" for _ in eras)
        params: list[object] = []
        for system_id, lo, hi in eras:
            params += [system_id, lo, hi]
        dwell = rows(con, f"""
          WITH eras(system_id, lo, hi) AS (VALUES {values}),
          src AS (
            SELECT f.system_id, f.bike_id, e.lo, e.hi,
                   f.departure_ts, f.departure_station_id,
                   f.return_ts, f.return_station_id
            FROM fact_trips f
            JOIN eras e ON e.system_id = f.system_id
                       AND f.trip_year BETWEEN e.lo AND e.hi
            WHERE {TRUSTED} AND f.bike_id IS NOT NULL {complete_months("f")}
          ), seq AS (
            SELECT system_id, lo, hi, return_ts, return_station_id,
                   lead(departure_ts)         OVER w AS next_dep_ts,
                   lead(departure_station_id) OVER w AS next_dep_station
            FROM src
            -- Partitioned by system as well as bike: 2,038 bike ids are shared
            -- between the Toronto and Vancouver namespaces, and joining across
            -- them would splice two cities' bikes into one chain.
            WINDOW w AS (
              PARTITION BY system_id, bike_id, lo
              ORDER BY departure_ts, return_ts,
                       departure_station_id, return_station_id
            )
          ), paired AS (
            SELECT system_id, lo, hi,
                   year(return_ts)                         AS yr,
                   month(return_ts)                        AS mo,
                   next_dep_station = return_station_id    AS same_dock,
                   -- datediff, not epoch(): an exact integer second count
                   -- rather than a float that a cast would round.
                   datediff('second', return_ts, next_dep_ts) AS dwell_s
            FROM seq
            WHERE return_ts IS NOT NULL AND return_station_id IS NOT NULL
              AND next_dep_ts IS NOT NULL AND next_dep_station IS NOT NULL
              -- An interval is reported in the year the bike ARRIVED, and only
              -- inside the era that produced it. Without this a Vancouver
              -- return on 2020-12-31 would publish a 2021 row, in a year the
              -- coverage test just withheld.
              AND year(return_ts) BETWEEN lo AND hi
          )
          SELECT system_id, lo AS era_first_year, hi AS era_last_year, yr AS year,
                 count(DISTINCT mo)::BIGINT                          AS months,
                 count(*) FILTER (same_dock AND dwell_s >= 0)::BIGINT AS intervals,
                 -- Not dwell: the bike's next departure is from another dock,
                 -- so something moved it. Counted rather than folded in.
                 count(*) FILTER (NOT same_dock)::BIGINT              AS relocated,
                 count(*) FILTER (same_dock AND dwell_s < 0)::BIGINT  AS out_of_order,
                 count(*) FILTER (
                   same_dock AND dwell_s >= 0 AND dwell_s % 3600 = 0
                 )::BIGINT                                            AS on_hour_grid,
                 CAST(quantile_cont(dwell_s, 0.25)
                      FILTER (same_dock AND dwell_s >= 0) AS BIGINT)  AS p25_s,
                 CAST(quantile_cont(dwell_s, 0.50)
                      FILTER (same_dock AND dwell_s >= 0) AS BIGINT)  AS median_s,
                 CAST(quantile_cont(dwell_s, 0.75)
                      FILTER (same_dock AND dwell_s >= 0) AS BIGINT)  AS p75_s
          -- All four group keys, in order. Three of them left the fourth free
          -- to come back either way if a system ever had two eras sharing a
          -- first year — the same untotal-ordering that made stations.json
          -- unreproducible above. It costs nothing to close.
          FROM paired GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4
        """, [*params, *skip_keys])
    guard(registry, "bike_dwell", sorted({r["system_id"] for r in dwell}))

    art["dwell"] = {
        "min_bike_id_coverage": BIKE_ID_MIN_COVERAGE,
        "series": dwell,
        # Years a supported system publishes trips for but cannot carry dwell.
        # Stated, never quietly absent — the membership section's discipline.
        "withheld": [
            {
                "system_id": c["system_id"],
                "year": c["year"],
                "trips": c["trips"],
                "with_bike_id": c["with_bike_id"],
                "basis": ("no bike identifier published" if c["with_bike_id"] == 0
                          else "bike identifier incomplete"),
            }
            for c in coverage
            if c["coverage"] < BIKE_ID_MIN_COVERAGE
            and any(e[0] == c["system_id"] for e in eras)
        ],
        # Systems with no bike identifier anywhere. Rendered as a labelled gap,
        # exactly like e-bike share for Montreal.
        "unsupported": {
            s: v for s, v in registry["metrics"]["bike_dwell"]["systems"].items()
            if not v.get("supported")
        },
        "notes": {
            s: v["note"] for s, v in
            registry["metrics"]["bike_dwell"]["systems"].items()
            if v.get("supported") and v.get("note")
        },
    }

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
