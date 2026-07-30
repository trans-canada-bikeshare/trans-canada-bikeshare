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
    unreturned = dict(con.execute(f"""
      SELECT system_id, count(*) FROM fact_trips
      WHERE {TRUSTED} AND return_station_id IS NULL GROUP BY 1
    """).fetchall())

    for system_id, net in con.execute(buggy).fetchall():
        # If this ever equals 0, the two computations have converged and this
        # test no longer guards anything — which would mean no unreturned trips.
        assert net == -unreturned[system_id], (
            f"{system_id}: the old computation should equal minus the "
            f"unreturned count ({unreturned[system_id]:,}), got {net:,}"
        )
