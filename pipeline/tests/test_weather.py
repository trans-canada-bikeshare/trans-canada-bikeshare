"""Spec 013 — ECCC weather ingest.

The failure mode this guards is silent: 0 °C is a legitimate and common value
in this dataset, so a missing day that became a zero would be
indistinguishable from an observation and would quietly bias any model trained
on it toward cold.
"""

import pytest

import common
import weather

duckdb = pytest.importorskip("duckdb")


def test_years_derive_from_the_trip_window_not_a_literal():
    """A new trip year must pull its weather without anyone editing a list."""
    manifest = {"sources": {"2019-04": {}, "2017": {}, "2021-12": {}}}
    assert weather.trip_years(manifest) == [2017, 2018, 2019, 2020, 2021]


def test_toronto_style_range_key_reads_as_its_first_year():
    """Toronto's earliest period is the range "2014-2015"."""
    assert weather.trip_years({"sources": {"2014-2015": {}, "2016": {}}}) == [2014, 2015, 2016]


def test_no_sources_yields_no_years():
    assert weather.trip_years({"sources": {}}) == []


def test_every_configured_system_is_a_known_system():
    for system_id in weather.STATIONS:
        assert system_id in common.SYSTEMS


def test_every_station_carries_the_identifiers_needed_to_refind_it():
    for system_id, st in weather.STATIONS.items():
        # station_id drives the endpoint and can move; climate_id is ECCC's
        # stable key and is what makes the station recoverable if it does.
        assert isinstance(st["station_id"], int), system_id
        assert str(st["climate_id"]).isdigit(), system_id
        assert st["name"], system_id
        assert 41 <= st["lat"] <= 84, system_id
        assert -141 <= st["lon"] <= -52, system_id


def test_licence_is_stated_with_attribution():
    assert weather.LICENCE["name"]
    assert weather.LICENCE["url"].startswith("https://")
    assert "Environment and Climate Change Canada" in weather.LICENCE["attribution"]


def test_every_manifest_weather_entry_is_pinned():
    """A pinned entry with no checksum would download without verification."""
    for system_id in weather.STATIONS:
        manifest = common.load_manifest(system_id)
        entries = {k: v for k, v in (manifest.get("reference") or {}).items()
                   if k.startswith("weather_")}
        if not entries:
            pytest.skip(f"{system_id}: weather not discovered yet")
        for name, entry in entries.items():
            assert entry.get("url"), f"{system_id} {name}"
            path = common.reference_path(system_id, name)
            if path.exists():
                assert entry.get("sha256"), f"{system_id} {name} downloaded but unpinned"
                assert entry.get("bytes"), f"{system_id} {name}"


@pytest.fixture(scope="module")
def con():
    db = common.DATA_WAREHOUSE / "bikeshare.duckdb"
    if not db.exists():
        pytest.skip(f"warehouse not built at {db}")
    c = duckdb.connect(str(db), read_only=True)
    if not c.execute("SELECT count(*) FROM information_schema.tables "
                     "WHERE table_name = 'weather_daily'").fetchone()[0]:
        pytest.skip("weather_daily not loaded")
    yield c
    c.close()


def test_a_missing_observation_stays_null_and_is_never_zero(con):
    """The silent failure: a gap rendered as 0 °C.

    Real zeros exist and are common, so this cannot be checked by looking for
    zeros. It checks the opposite direction — that NULLs survive the load at
    all. If some fill had been applied there would be none.
    """
    nulls = con.execute(
        "SELECT count(*) FROM weather_daily WHERE temp_mean_c IS NULL"
    ).fetchone()[0]
    assert nulls > 0, (
        "no NULL temperatures anywhere — ECCC's record has gaps, so this "
        "means something filled them"
    )


def test_kept_rows_carry_at_least_one_observation(con):
    """Calendar padding for future dates must not be stored as data."""
    empty = con.execute("""
        SELECT count(*) FROM weather_daily
        WHERE coalesce(temp_mean_c, temp_max_c, temp_min_c,
                       precip_mm, snow_cm, snow_ground_cm) IS NULL
    """).fetchone()[0]
    assert empty == 0


def test_temperatures_are_physically_plausible(con):
    """Catches a units error or a column shifted by a reordered export."""
    bad = con.execute("""
        SELECT count(*) FROM weather_daily
        WHERE temp_mean_c IS NOT NULL AND (temp_mean_c < -50 OR temp_mean_c > 45)
    """).fetchone()[0]
    assert bad == 0


def test_min_never_exceeds_max(con):
    """Two columns swapped would still look plausible one at a time."""
    bad = con.execute("""
        SELECT count(*) FROM weather_daily
        WHERE temp_min_c IS NOT NULL AND temp_max_c IS NOT NULL
          AND temp_min_c > temp_max_c
    """).fetchone()[0]
    assert bad == 0


def test_precipitation_is_never_negative(con):
    bad = con.execute("""
        SELECT count(*) FROM weather_daily
        WHERE (precip_mm IS NOT NULL AND precip_mm < 0)
           OR (snow_cm IS NOT NULL AND snow_cm < 0)
    """).fetchone()[0]
    assert bad == 0


def test_one_row_per_system_per_day(con):
    dupes = con.execute("""
        SELECT count(*) FROM (
          SELECT system_id, date_key FROM weather_daily
          GROUP BY 1, 2 HAVING count(*) > 1)
    """).fetchone()[0]
    assert dupes == 0


def test_each_city_has_a_named_station(con):
    rows = con.execute("SELECT system_id, station_name FROM weather_station").fetchall()
    got = {s for s, _ in rows}
    assert got == set(weather.STATIONS), got
    for _, name in rows:
        assert name


def test_coverage_of_each_trip_window_is_near_complete(con):
    """A station that stopped reporting mid-window would fail here.

    Not a demand for perfection: the record genuinely has gaps, and the point
    of the spec is that they are counted rather than filled. But losing a
    meaningful share of a window would make any weather-conditioned series
    quietly unrepresentative.
    """
    for system_id, window, present in con.execute("""
        WITH win AS (
          SELECT system_id, min(departure_ts)::DATE AS f, max(departure_ts)::DATE AS l
          FROM fact_trips
          WHERE NOT list_contains(quality_flags, 'implausible_date')
          GROUP BY 1),
        cal AS (
          SELECT w.system_id,
                 unnest(generate_series(w.f, w.l, INTERVAL 1 DAY))::DATE AS d
          FROM win w)
        SELECT cal.system_id, count(*), count(wd.temp_mean_c)
        FROM cal LEFT JOIN weather_daily wd
          ON wd.system_id = cal.system_id AND wd.date_key = cal.d
        GROUP BY 1
    """).fetchall():
        assert present / window > 0.97, (
            f"{system_id}: only {present:,} of {window:,} window days have a "
            "mean temperature"
        )
