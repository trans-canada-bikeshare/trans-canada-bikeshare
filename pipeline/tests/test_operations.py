"""The invariants behind spec 024's operational signals.

`src/operations.test.ts` checks the artifact the site serves. These check the
computation that produced it, against the warehouse, and each one plants the
mistake it guards: a query written the plausible way, run beside the correct
one, so the difference is a number rather than an argument.

Three of them are about a chain of one bike's trips, and all three have the
same shape — the chain is only correct if it is cut in the right places.
"""

import json

import pytest

duckdb = pytest.importorskip("duckdb")

import common  # noqa: E402

TRUSTED = "NOT list_contains(quality_flags, 'implausible_date')"

LINKED = f"""
  {TRUSTED}
  AND departure_station_id IS NOT NULL
  AND return_station_id IS NOT NULL
  AND return_ts IS NOT NULL
"""


@pytest.fixture(scope="module")
def con():
    db = common.DATA_WAREHOUSE / "bikeshare.duckdb"
    if not db.exists():
        pytest.skip(f"warehouse not built at {db}")
    # Capped deliberately. This module runs window functions over tens of
    # millions of rows; left to itself DuckDB takes every core on the machine
    # for the length of the suite.
    c = duckdb.connect(str(db), read_only=True, config={"threads": "3"})
    yield c
    c.close()


@pytest.fixture(scope="module")
def registry():
    return json.loads((common.MAPPINGS_DIR / "metric_support.json").read_text("utf-8"))


# --- the registry split -----------------------------------------------------


def test_registry_splits_the_two_signals(registry):
    """One key could only ever be as narrow as its narrowest signal.

    `operational_signals` marked Montreal unsupported wholesale because dwell
    needs a bike id. That excluded the flagship system — 88M of 135.6M trips —
    from signals its trip data supports perfectly well.
    """
    metrics = registry["metrics"]
    assert "operational_signals" not in metrics
    assert {"rebalancing_pressure", "bike_dwell"} <= set(metrics)

    pressure = metrics["rebalancing_pressure"]
    assert pressure["comparable"] is True
    assert all(v.get("supported") for v in pressure["systems"].values())
    assert set(pressure["systems"]) == set(common.SYSTEMS)
    # The bound is the metric's most misreadable property, so it is a field of
    # the registry rather than a sentence somebody remembered to write.
    assert "lower bound" in pressure["caveat"].lower()

    dwell = metrics["bike_dwell"]
    assert dwell["comparable"] is False
    assert dwell["systems"]["mtl-bixi"]["supported"] is False
    assert dwell["systems"]["mtl-bixi"]["reason"]
    for system_id in ("van-mobi", "tor-bikeshare"):
        assert dwell["systems"][system_id]["supported"] is True
        # Both carry era limits, and a limit nobody states is a limit nobody
        # applies.
        assert dwell["systems"][system_id]["note"]


# --- net flow by hour -------------------------------------------------------


def test_hourly_net_cancels_to_zero_per_system(con):
    """A trip is one departure and one return, so a system's day nets zero.

    It stops being true the moment an unlinked trip is admitted: the departure
    is counted and the return it never had is not.
    """
    rows = con.execute(f"""
      WITH linked AS (SELECT system_id, departure_ts, return_ts
                      FROM fact_trips WHERE {LINKED}),
      ev AS (SELECT system_id, hour(departure_ts) h, -1 v FROM linked
             UNION ALL SELECT system_id, hour(return_ts) h, 1 v FROM linked)
      SELECT system_id, sum(v), count(DISTINCT h) FROM ev GROUP BY 1 ORDER BY 1
    """).fetchall()
    assert rows
    for system_id, net, hours in rows:
        assert net == 0, f"{system_id} nets {net:,} over its day rather than 0"
        assert hours == 24, f"{system_id} has {hours} hours, not 24"


def test_unlinked_trips_would_break_the_hourly_identity(con):
    """The regression, planted: count every departure and only the returns that
    resolve, and each system's day nets minus its unreturned trips."""
    rows = con.execute(f"""
      WITH ev AS (
        SELECT system_id, -1 v FROM fact_trips
        WHERE {TRUSTED} AND departure_station_id IS NOT NULL
        UNION ALL
        SELECT system_id, 1 v FROM fact_trips
        WHERE {TRUSTED} AND return_station_id IS NOT NULL AND return_ts IS NOT NULL
      )
      SELECT system_id, sum(v) FROM ev GROUP BY 1 ORDER BY 1
    """).fetchall()
    assert any(net != 0 for _, net in rows), (
        "the buggy computation nets zero too, so this test proves nothing"
    )


# --- implied minimum daily rebalancing --------------------------------------


def test_archive_edge_invents_days_with_returns_and_no_departures(con):
    """Montreal's archive ends 2026-06-30, and trips that departed on the last
    days return after it. Dating each event by its own day is right, but a day
    with returns and no departures is not a day the system operated: 2026-07-01
    carries 617 Montreal returns against a ~3,000-move norm, and 21 more days
    behind it carry a handful each.

    Left in, they drag Montreal's mean down by several percent for a reason
    that is the end of the archive rather than anything about the network.
    """
    rows = con.execute(f"""
      WITH linked AS (
        SELECT system_id, departure_ts, return_ts FROM fact_trips WHERE {LINKED}
      ), deps AS (SELECT DISTINCT system_id, departure_ts::DATE d FROM linked),
         rets AS (SELECT system_id, return_ts::DATE d, count(*) n
                  FROM linked GROUP BY 1, 2)
      SELECT r.system_id, count(*) AS phantom_days, sum(r.n) AS events
      FROM rets r LEFT JOIN deps p
        ON p.system_id = r.system_id AND p.d = r.d
      WHERE p.d IS NULL
      GROUP BY 1 ORDER BY 1
    """).fetchall()
    assert rows, (
        "no return lands on a day without a departure, so the operating-day "
        "condition in publish.py is guarding nothing and should be revisited"
    )
    for system_id, days, events in rows:
        assert days > 0 and events > 0, system_id


def test_published_rebalancing_matches_a_recomputation(con):
    """The artifact, re-derived from scratch for the headline year.

    Deliberately not a call into publish.py: a test that reruns the code under
    test agrees with it by construction.
    """
    art = json.loads((common.GENERATED_DIR / "rebalancing.json").read_text("utf-8"))
    year = art["headline_year"]
    if year is None:
        pytest.skip("no year the archive covers end to end for every system")

    # Two years either side, not the target year alone. A trip departing on
    # 31 December returns on 1 January, and its two legs belong to two
    # different years' days — the longest linked trip in the archive runs 424
    # days, so the window has to be wider than the year it is checking.
    rows = {
        r[0]: (r[1], r[2]) for r in con.execute(f"""
          WITH linked AS (
            SELECT system_id, departure_ts, departure_station_id,
                   return_ts, return_station_id
            FROM fact_trips WHERE {LINKED} AND trip_year BETWEEN ? - 2 AND ? + 1
          ), opday AS (
            SELECT DISTINCT system_id, departure_ts::DATE d FROM linked
            WHERE year(departure_ts) = ?
          ), ev AS (
            SELECT system_id, departure_ts::DATE d, departure_station_id sid, -1 v
            FROM linked
            UNION ALL
            SELECT system_id, return_ts::DATE d, return_station_id sid, 1 v
            FROM linked
          ), st AS (
            SELECT e.system_id, e.d, e.sid, sum(e.v) net
            FROM ev e JOIN opday o ON o.system_id = e.system_id AND o.d = e.d
            GROUP BY 1, 2, 3
          ), dayagg AS (
            SELECT system_id, d, sum(abs(net)) abs_net FROM st GROUP BY 1, 2
          )
          SELECT system_id, count(*), sum(abs_net)::BIGINT
          FROM dayagg GROUP BY 1 ORDER BY 1
        """, [year, year, year]).fetchall()
    }
    published = {r["system_id"]: r for r in art["yearly"] if r["year"] == year}
    assert set(published) == set(rows)
    for system_id, row in published.items():
        days, abs_net = rows[system_id]
        assert (row["days"], row["abs_net"]) == (days, abs_net), system_id


# --- per-bike dwell ---------------------------------------------------------


def test_bike_id_namespaces_overlap_between_systems(con):
    """Why the chain partitions by system as well as by bike.

    The ids are each operator's own; nothing makes them globally unique, and in
    fact thousands collide. A chain keyed on bike_id alone would interleave two
    cities' bikes and read the gap between them as dwell.
    """
    shared = con.execute("""
      WITH ids AS (SELECT DISTINCT system_id, bike_id FROM fact_trips
                   WHERE bike_id IS NOT NULL)
      SELECT count(*) FROM ids a JOIN ids b
        ON a.bike_id = b.bike_id AND a.system_id < b.system_id
    """).fetchone()[0]
    assert shared > 0, (
        "no bike id is shared between systems today, but nothing in the "
        "sources guarantees that, so the partition stays"
    )


def test_chain_must_not_step_across_a_withheld_era(con):
    """Vancouver's 2021-2023 are withheld for missing bike ids. A chain that
    spans the gap pairs a 2020 return with a 2024 departure and calls the
    intervening three years dwell."""
    art = json.loads((common.GENERATED_DIR / "dwell.json").read_text("utf-8"))
    eras = sorted({(r["era_first_year"], r["era_last_year"])
                   for r in art["series"] if r["system_id"] == "van-mobi"})
    assert len(eras) == 2, f"expected two Vancouver eras, got {eras}"
    (_, first_end), (second_start, _) = eras
    assert second_start > first_end + 1

    # Built without the era partition, the boundary produces intervals measured
    # in years. Restricted to the two admitted eras so the comparison isolates
    # the partition and nothing else.
    spanning = con.execute(f"""
      WITH src AS (
        SELECT bike_id, departure_ts, departure_station_id,
               return_ts, return_station_id
        FROM fact_trips
        WHERE {TRUSTED} AND system_id = 'van-mobi' AND bike_id IS NOT NULL
          AND (trip_year BETWEEN ? AND ? OR trip_year BETWEEN ? AND ?)
      ), seq AS (
        SELECT return_ts, return_station_id,
               lead(departure_ts)         OVER w AS next_dep_ts,
               lead(departure_station_id) OVER w AS next_dep_station
        FROM src
        WINDOW w AS (PARTITION BY bike_id
                     ORDER BY departure_ts, return_ts,
                              departure_station_id, return_station_id)
      )
      SELECT count(*) FROM seq
      WHERE return_ts IS NOT NULL AND next_dep_ts IS NOT NULL
        AND next_dep_station = return_station_id
        AND datediff('day', return_ts, next_dep_ts) > 365
    """, [eras[0][0], first_end, second_start, eras[1][1]]).fetchone()[0]
    assert spanning > 0, (
        "the unpartitioned chain produced no year-long interval, so this test "
        "no longer demonstrates the failure the era partition prevents"
    )

    published = max(r["p75_s"] for r in art["series"] if r["system_id"] == "van-mobi")
    assert published < 365 * 86400


def test_a_relocated_bike_is_not_dwell(con):
    """The wrong cut, planted.

    Partitioning by station as well as bike looks natural and is wrong: it
    pairs a bike's return at a dock with its next departure FROM THAT DOCK,
    skipping every trip it took elsewhere in between. The interval it reports
    then covers a relocation and one or more rides, not dwell at the dock.

    Vancouver 2024 alone, to keep the window function cheap.
    """
    correct, wrong = con.execute(f"""
      WITH src AS (
        SELECT bike_id, departure_ts, departure_station_id,
               return_ts, return_station_id
        FROM fact_trips
        WHERE {TRUSTED} AND system_id = 'van-mobi' AND trip_year = 2024
          AND bike_id IS NOT NULL
      ), by_bike AS (
        SELECT return_ts, return_station_id,
               lead(departure_ts)         OVER w AS next_dep_ts,
               lead(departure_station_id) OVER w AS next_dep_station
        FROM src
        WINDOW w AS (PARTITION BY bike_id
                     ORDER BY departure_ts, return_ts,
                              departure_station_id, return_station_id)
      ), by_bike_and_station AS (
        SELECT return_ts, return_station_id,
               lead(departure_ts) OVER w AS next_dep_ts
        FROM src
        WINDOW w AS (PARTITION BY bike_id, return_station_id
                     ORDER BY departure_ts, return_ts,
                              departure_station_id, return_station_id)
      )
      SELECT
        (SELECT CAST(median(datediff('second', return_ts, next_dep_ts)) AS BIGINT)
         FROM by_bike
         WHERE return_ts IS NOT NULL AND next_dep_ts IS NOT NULL
           AND next_dep_station = return_station_id
           AND next_dep_ts >= return_ts),
        (SELECT CAST(median(datediff('second', return_ts, next_dep_ts)) AS BIGINT)
         FROM by_bike_and_station
         WHERE return_ts IS NOT NULL AND next_dep_ts IS NOT NULL
           AND next_dep_ts >= return_ts)
    """).fetchone()
    assert wrong > correct, (
        f"the station-partitioned chain reported {wrong}s against the correct "
        f"{correct}s; if they ever agree, the relocation exclusion is doing "
        "nothing and should be re-derived"
    )

    art = json.loads((common.GENERATED_DIR / "dwell.json").read_text("utf-8"))
    published = next(r for r in art["series"]
                     if r["system_id"] == "van-mobi" and r["year"] == 2024)
    assert published["median_s"] == correct
    assert published["relocated"] > 0
