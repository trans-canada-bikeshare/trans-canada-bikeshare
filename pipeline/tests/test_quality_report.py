"""The quality report has to be CHECKED, not merely generated.

Every test here plants a specific violation and asserts the failure names it,
the convention `test_check_metrics.py` set: a gate nobody has watched fail is a
gate nobody knows works. The violations are not hypothetical — each one is a
defect this report actually shipped.

  * the Montreal canonical share published 0.0% because the query joined the
    fact's already-canonical station id against the bridge's pre-bridge key;
  * the funnel's duplicate count was landed-minus-everything-else, so its
    residual was zero by construction and could not detect anything;
  * five Toronto rows were kept with no departure station at all, under a rule
    that says such a row is dropped;
  * the per-system table printed Toronto's first trip as 2000-01-01, from the
    one row flagged `implausible_date`;
  * and the whole document sat outside `make check`, so none of the above cost
    anything.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import duckdb
import pytest

import check_report
import common
import quality_report

WAREHOUSE = common.DATA_WAREHOUSE / "bikeshare.duckdb"
real_warehouse = pytest.mark.skipif(
    not WAREHOUSE.exists(), reason="the real warehouse is not built here"
)


# --- a tiny warehouse whose truth is known by construction -------------------
#
# Small enough to state in one screen, shaped exactly like the real one: three
# systems, a Montreal bridge with era ids that are NOT the ids the fact carries
# (which is the whole reason the broken join returned nothing), one flagged
# implausible date, and one Toronto label that is the literal string 'NULL'.

MTL_TRIPS = [
    # (departure_station_id, label)   3 canonical, 1 era-D name, 1 era-local key
    ("mtl-bixi:s101", "Berri"),
    ("mtl-bixi:s101", "Berri"),
    ("mtl-bixi:s102", "Rachel"),
    ("mtl-bixi:name:somewhere else", "Somewhere Else"),
    ("mtl-bixi:6999", "Retired Dock"),
]


def make_db(tmp_path: Path, name: str = "fixture.duckdb") -> Path:
    path = tmp_path / name
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE etl_metrics (stage VARCHAR, metric VARCHAR, value BIGINT)")
    con.execute("""CREATE TABLE fact_trips (
        system_id VARCHAR, departure_ts TIMESTAMP, trip_month DATE,
        departure_station_id VARCHAR, return_station_id VARCHAR,
        departure_label VARCHAR, return_label VARCHAR, membership_raw VARCHAR,
        quality_flags VARCHAR[], has_quality_issue BOOLEAN)""")
    con.execute("""CREATE TABLE dim_station (
        system_id VARCHAR, station_id VARCHAR, station_name VARCHAR,
        is_active BOOLEAN)""")
    con.execute("""CREATE TABLE dim_membership (
        system_id VARCHAR, membership_raw VARCHAR, membership_group VARCHAR)""")
    con.execute("""CREATE TABLE mtl_station_bridge (
        era_id VARCHAR, canonical_id VARCHAR, via VARCHAR)""")
    con.execute("""CREATE TABLE raw_file_audit (
        system_id VARCHAR, source_period VARCHAR, source_file VARCHAR,
        source_records BIGINT, rows_landed BIGINT, lines_repaired BIGINT,
        kind VARCHAR)""")

    def trip(system, ts, dep, ret, label, ret_label, member, flags):
        con.execute(
            "INSERT INTO fact_trips VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [system, ts, ts[:8] + "01", dep, ret, label, ret_label, member,
             flags, bool(flags)],
        )

    for i, (dep, label) in enumerate(MTL_TRIPS):
        trip("mtl-bixi", f"2024-05-0{i + 1} 08:00:00", dep, "mtl-bixi:s102",
             label, "Rachel", "1", [])
    # Toronto: one ordinary trip, one carrying the literal 'NULL' label over a
    # real id, one whose timestamp parsed but cannot be true.
    trip("tor-bikeshare", "2024-05-02 09:00:00", "tor-bikeshare:7033",
         "tor-bikeshare:7043", "Union Station", "Queens Quay", "Member", [])
    trip("tor-bikeshare", "2024-05-03 09:00:00", "tor-bikeshare:7043",
         "tor-bikeshare:7033", "NULL", "Union Station", "Member", [])
    trip("tor-bikeshare", "2000-01-01 09:40:00", "tor-bikeshare:7033",
         "tor-bikeshare:7043", "Union Station", "Queens Quay", "Member",
         ["implausible_date"])
    for i in range(2):
        trip("van-mobi", f"2024-05-0{i + 1} 07:00:00", "van-mobi:0069",
             "van-mobi:0070", "7th & Granville", "Yukon", "365 Standard", [])

    for sid, station, name in [
        ("mtl-bixi", "mtl-bixi:s101", "Berri"),
        ("mtl-bixi", "mtl-bixi:s102", "Rachel"),
        ("mtl-bixi", "mtl-bixi:name:somewhere else", "Somewhere Else"),
        ("mtl-bixi", "mtl-bixi:6999", "Retired Dock"),
        ("tor-bikeshare", "tor-bikeshare:7033", "Union Station"),
        ("tor-bikeshare", "tor-bikeshare:7043", "Queens Quay"),
        ("van-mobi", "van-mobi:0069", "7th & Granville"),
        ("van-mobi", "van-mobi:0070", "Yukon"),
    ]:
        con.execute("INSERT INTO dim_station VALUES (?, ?, ?, ?)",
                    [sid, station, name, True])
    for sid, raw, group in [("mtl-bixi", "1", "member"),
                            ("tor-bikeshare", "Member", "member"),
                            ("van-mobi", "365 Standard", "member")]:
        con.execute("INSERT INTO dim_membership VALUES (?, ?, ?)", [sid, raw, group])
    # The era ids are the PRE-bridge keys. Nothing in fact_trips equals one,
    # which is precisely why joining on them returned nothing.
    for era, canonical, via in [("mtl-bixi:6062", "mtl-bixi:s101", "code"),
                                ("mtl-bixi:101", "mtl-bixi:s101", "pk"),
                                ("mtl-bixi:6063", "mtl-bixi:s102", "code")]:
        con.execute("INSERT INTO mtl_station_bridge VALUES (?, ?, ?)",
                    [era, canonical, via])

    # 13 landed, 10 kept, 3 dropped across the three named reasons.
    for system, period, fname, records, repaired in [
        ("mtl-bixi", "2024", "2024.csv", 6, 0),
        ("tor-bikeshare", "2024", "2024-05.csv", 4, 7),
        ("van-mobi", "2024-05", "2024-05.csv", 3, 0),
    ]:
        con.execute("INSERT INTO raw_file_audit VALUES (?, ?, ?, ?, ?, ?, 'trips')",
                    [system, period, fname, records, records, repaired])
    con.execute("INSERT INTO raw_file_audit VALUES "
                "('mtl-bixi', '2024', 'stations.csv', 2, 2, 0, 'stations')")
    for stage, metric, value in [
        ("extract", "rows_landed", 13),
        ("extract", "lines_repaired", 7),
        ("extract", "files_encoding_repaired", 1),
        ("clean", "rows_kept", 10),
        ("clean", "rows_dropped_no_departure_time", 1),
        ("clean", "rows_dropped_no_departure_station", 1),
        ("clean", "rows_dropped_duplicates", 1),
    ]:
        con.execute("INSERT INTO etl_metrics VALUES (?, ?, ?)", [stage, metric, value])
    con.close()
    return path


@pytest.fixture
def db(tmp_path):
    return make_db(tmp_path)


def render(path: Path) -> str:
    con = duckdb.connect(str(path), read_only=True)
    try:
        return quality_report.build(con)
    finally:
        con.close()


def edit(path: Path, sql: str, params: list | None = None) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute(sql, params or [])
    finally:
        con.close()


# --- the Montreal canonical share -------------------------------------------

def test_canonical_share_is_the_fixtures_known_truth(db):
    """Three of five Montreal trips depart from a bridged station: 60.0%."""
    con = duckdb.connect(str(db), read_only=True)
    try:
        rows = dict((k, n) for k, n, _ in quality_report.montreal_resolution(con))
    finally:
        con.close()
    assert rows == {"canonical": 3, "era-local name": 1, "era-local key": 1}
    assert "**60.0%**" in render(db)


def test_the_old_join_shape_would_have_answered_zero(db):
    """The exact query that shipped 0.0%, run against a fixture that is 60%.

    This is the test the report needed and did not have. The broken version is
    not obviously wrong on inspection — it joins a station id to a station id —
    so only running it against a known answer separates the two.
    """
    con = duckdb.connect(str(db), read_only=True)
    try:
        broken = con.execute("""
            SELECT round(100.0 * count(b.canonical_id) / count(*), 1)
            FROM fact_trips f
            LEFT JOIN mtl_station_bridge b ON b.era_id = f.departure_station_id
            WHERE f.system_id = 'mtl-bixi'""").fetchone()[0]
    finally:
        con.close()
    assert broken == 0.0, "the fixture must reproduce the published defect"


def test_the_remainder_is_described_by_query_not_by_guess(db):
    text = render(db)
    # Both era-local kinds are named and counted; neither is called "retired".
    assert "era-local name" in text and "era-local key" in text
    assert "retired" not in text.lower().split("## Membership")[0].replace(
        "Retired Dock", "")


# --- the funnel --------------------------------------------------------------

def test_funnel_is_reported_and_closes(db):
    text = render(db)
    assert "| landed | 13 | 100.000% |" in text
    assert "Funnel residual: **0**" in text


def test_nonzero_residual_refuses_to_write_the_report(db):
    """Plant a double-counted reason: the same row under two names."""
    edit(db, "UPDATE etl_metrics SET value = 2 "
             "WHERE metric = 'rows_dropped_duplicates'")
    with pytest.raises(quality_report.ReportInvariant, match="funnel residual"):
        render(db)


def test_a_missing_drop_reason_also_refuses(db):
    """Rows leaving under no reason at all is the other direction of the same
    failure, and the derived count could not see it either."""
    edit(db, "DELETE FROM etl_metrics WHERE metric = 'rows_dropped_no_departure_time'")
    with pytest.raises(quality_report.ReportInvariant, match="funnel residual"):
        render(db)


def test_a_file_that_landed_the_wrong_row_count_refuses(db):
    edit(db, "UPDATE raw_file_audit SET rows_landed = rows_landed - 1 "
             "WHERE source_file = '2024.csv'")
    with pytest.raises(quality_report.ReportInvariant, match="landed a different"):
        render(db)


def test_an_audit_that_disagrees_with_etl_metrics_refuses(db):
    """Both sides count what landed. They are allowed to be wrong; they are not
    allowed to be wrong differently and say nothing."""
    edit(db, "UPDATE raw_file_audit SET source_records = source_records + 5, "
             "rows_landed = rows_landed + 5 WHERE source_file = '2024.csv'")
    with pytest.raises(quality_report.ReportInvariant, match="per-file audit"):
        render(db)


# --- station identity --------------------------------------------------------

def test_a_kept_trip_with_no_departure_station_refuses(db):
    """The live defect: five 2016 Toronto rows kept under a rule that drops
    exactly those rows, invisible to the funnel because nothing counted them."""
    edit(db, "UPDATE fact_trips SET departure_station_id = NULL "
             "WHERE departure_label = 'NULL'")
    with pytest.raises(quality_report.ReportInvariant, match="no departure station"):
        render(db)


def test_a_station_named_NULL_refuses(db):
    edit(db, "UPDATE dim_station SET station_name = 'NULL' "
             "WHERE station_id = 'tor-bikeshare:7043'")
    with pytest.raises(quality_report.ReportInvariant, match="named 'NULL'"):
        render(db)


def test_the_literal_null_label_is_explained_and_counted(db):
    text = render(db)
    assert "### The literal label `NULL`" in text
    assert "| tor-bikeshare | 1 | 0 | 1 | 0 |" in text


# --- dates -------------------------------------------------------------------

def test_first_and_last_dates_skip_implausible_rows(db):
    text = render(db)
    per_system = text.split("## Per system")[1].split("## Quality flags")[0]
    assert "2000-01-01" not in per_system, "an implausible date became a first trip"
    assert "2024-05-02" in per_system
    # The row is still a trip and still shows up as a flag.
    assert "implausible_date" in text.split("## Quality flags")[1]


# --- encoding ----------------------------------------------------------------

def test_the_encoding_paragraph_tracks_the_audit(db):
    assert "| tor-bikeshare | 1 | 1 | 7 |" in render(db)
    edit(db, "UPDATE raw_file_audit SET lines_repaired = 42 "
             "WHERE source_file = '2024-05.csv' AND system_id = 'tor-bikeshare'")
    assert "| tor-bikeshare | 1 | 1 | 42 |" in render(db)


def test_no_row_count_is_written_into_the_generators_prose():
    """The regression that produced "~31,000 rows discarded ... open gap".

    That sentence was true when written and false for two specs afterwards,
    and nothing could have noticed, because a number in a string literal is
    not connected to anything. Comma-grouped digits are how this project
    formats counts, so they have no business in a literal.
    """
    source = Path(quality_report.__file__).read_text(encoding="utf-8")
    grouped = re.compile(r"\d{1,3}(?:,\d{3})+")
    offenders = [
        node.value for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and grouped.search(node.value)
    ]
    assert not offenders, f"hardcoded count(s) in the report's prose: {offenders}"


# --- the gate ----------------------------------------------------------------

def test_a_fresh_report_passes_the_gate(db, tmp_path):
    out = tmp_path / "report.md"
    out.write_text(render(db), encoding="utf-8")
    assert check_report.check(db, out) == []


def test_only_the_timestamp_line_may_differ(db, tmp_path):
    out = tmp_path / "report.md"
    text = render(db)
    out.write_text(
        text.replace("Generated 20", "Generated 19"), encoding="utf-8")
    assert check_report.check(db, out) == []


def test_a_stale_committed_report_fails_the_gate(db, tmp_path):
    """The failure mode the gate exists for: the warehouse moved, the committed
    document did not, and every other gate stayed green."""
    out = tmp_path / "report.md"
    out.write_text(render(db), encoding="utf-8")
    edit(db, "INSERT INTO fact_trips VALUES ('van-mobi', TIMESTAMP '2024-05-09 07:00:00', "
             "DATE '2024-05-01', 'van-mobi:0069', 'van-mobi:0070', '7th & Granville', "
             "'Yukon', '365 Standard', [], false)")
    edit(db, "UPDATE etl_metrics SET value = value + 1 "
             "WHERE metric IN ('rows_landed', 'rows_kept')")
    edit(db, "UPDATE raw_file_audit SET source_records = source_records + 1, "
             "rows_landed = rows_landed + 1 WHERE system_id = 'van-mobi'")
    diff = check_report.check(db, out)
    assert diff, "a warehouse that moved must not match a report that did not"
    assert any("van-mobi" in line or "landed" in line for line in diff)


def test_a_missing_report_fails_the_gate(db, tmp_path):
    diff = check_report.check(db, tmp_path / "absent.md")
    assert diff and "does not exist" in diff[0]


# --- against the warehouse this repository actually ships --------------------

@real_warehouse
def test_no_kept_trip_lacks_a_departure_station():
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        orphans = con.execute(
            "SELECT count(*) FROM fact_trips WHERE departure_station_id IS NULL"
        ).fetchone()[0]
        named_null = con.execute(
            "SELECT count(*) FROM dim_station WHERE upper(trim(station_name)) = 'NULL'"
        ).fetchone()[0]
    finally:
        con.close()
    assert orphans == 0
    assert named_null == 0


@real_warehouse
def test_the_committed_report_matches_the_warehouse():
    """The same check `make check-report` runs. It belongs in the suite too:
    the report was regenerated by hand for two specs and nothing compared it."""
    assert check_report.check(WAREHOUSE, quality_report.OUT) == []
