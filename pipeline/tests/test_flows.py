"""The net-flow invariant, checked where every station is in scope.

`src/flows.test.ts` can only see stations shipped to the site — those with
coordinates and at least 100 lifetime events. The identity that actually
constrains net flow needs all of them, so it lives here.

Spec 022's first implementation counted every trip's departure but only the
returns it could resolve, leaving a phantom -1 at the origin of each unreturned
trip. In Montreal that was 272,088 trips, enough to bias the whole map amber
for a reason that was a gap in the data rather than any movement of bikes.
"""

import pytest

duckdb = pytest.importorskip("duckdb")

import common  # noqa: E402

TRUSTED = "NOT list_contains(quality_flags, 'implausible_date')"

NET_FLOW = f"""
  WITH linked AS (
    SELECT system_id, departure_station_id AS a, return_station_id AS b
    FROM fact_trips
    WHERE {TRUSTED}
      AND departure_station_id IS NOT NULL
      AND return_station_id IS NOT NULL
  ), ev AS (
    SELECT system_id, a AS sid, -1 AS d FROM linked
    UNION ALL
    SELECT system_id, b AS sid, 1 AS d FROM linked
  )
  SELECT system_id, sum(d) AS net FROM ev GROUP BY 1 ORDER BY 1
"""


@pytest.fixture(scope="module")
def con():
    db = common.DATA_WAREHOUSE / "bikeshare.duckdb"
    if not db.exists():
        pytest.skip(f"warehouse not built at {db}")
    c = duckdb.connect(str(db), read_only=True)
    yield c
    c.close()


def test_net_flow_cancels_to_zero_per_system(con):
    """Every trip is one departure and one return, so a system must net zero."""
    rows = con.execute(NET_FLOW).fetchall()
    assert rows, "no systems in fact_trips"
    for system_id, net in rows:
        assert net == 0, (
            f"{system_id} nets {net:,} rather than 0 — net flow is counting "
            "departures it cannot pair with a return"
        )


def test_unreturned_trips_do_not_reach_net_flow(con):
    """The specific regression: unreturned trips must not skew any origin.

    Recomputed the buggy way, the sum equals minus the unreturned count. That
    it differs from the correct computation is what this pins.
    """
    buggy = f"""
      WITH ev AS (
        SELECT system_id, departure_station_id AS sid, -1 AS d
        FROM fact_trips WHERE {TRUSTED}
        UNION ALL
        SELECT system_id, return_station_id AS sid, 1 AS d
        FROM fact_trips WHERE {TRUSTED} AND return_station_id IS NOT NULL
      )
      SELECT system_id, sum(d) FROM ev WHERE sid IS NOT NULL GROUP BY 1 ORDER BY 1
    """
    ends = {
        r[0]: (r[1], r[2]) for r in con.execute(f"""
          SELECT system_id,
                 count(*) FILTER (departure_station_id IS NULL) AS no_dep,
                 count(*) FILTER (return_station_id IS NULL)    AS no_ret
          FROM fact_trips WHERE {TRUSTED} GROUP BY 1
        """).fetchall()
    }

    for system_id, net in con.execute(buggy).fetchall():
        no_dep, no_ret = ends[system_id]
        # The old computation counts known departures as -1 and known returns
        # as +1, so it nets exactly (missing departures - missing returns).
        # Originally no trip lacked a departure station and this reduced to
        # -no_returns; the literal-'NULL' station-key fix (2026-07-30) made a
        # handful of departures honestly unknown, so the general identity is
        # the one to pin. If this ever nets 0 with both counts 0, the guard
        # has nothing to guard.
        assert net == no_dep - no_ret, (
            f"{system_id}: buggy recomputation should net "
            f"{no_dep:,} - {no_ret:,} = {no_dep - no_ret:,}, got {net:,}"
        )
        assert no_ret > 0, f"{system_id}: no unreturned trips at all?"
