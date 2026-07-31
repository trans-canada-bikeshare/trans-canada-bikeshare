"""The per-file audit, and the repair count that must never be guessed.

`ensure_utf8` repairs cp1252 lines and writes the count beside the scrubbed
copy. That count is the only record of how much of the archive needed
repairing, and the quality report now derives its encoding paragraph from it
rather than restating a remembered "~31,000". So the backfill that reads those
markers into the warehouse has one hard rule: a file the code says should carry
a marker and does not stops the run. A zero standing in for an unknown count
would be a fabricated data-loss figure, which is the failure mode this project
has already met twice.
"""

from __future__ import annotations

import duckdb
import pytest

import common
import etl


@pytest.fixture
def con(tmp_path):
    c = duckdb.connect(str(tmp_path / "audit.duckdb"))
    yield c
    c.close()


@pytest.fixture
def archive(tmp_path, monkeypatch):
    """A stand-in data-raw, holding one pinned Vancouver CSV."""
    root = tmp_path / "data-raw"
    (root / "van-mobi").mkdir(parents=True)
    (root / "van-mobi" / "2023-06.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    monkeypatch.setattr(common, "DATA_RAW", root)
    return root


def audit_one(con, system="van-mobi", period="2023-06", name="2023-06.csv"):
    etl.ensure_audit_table(con)
    con.execute("INSERT INTO raw_file_audit VALUES (?, ?, ?, 1, 1, 0, 'trips', ?)",
                [system, period, name, "0" * 64])


def test_the_audit_table_gains_its_columns_without_a_reload(con):
    """An existing warehouse must be able to grow the columns, not be rebuilt.

    A 13 GB reload to add one nullable column is a cost nobody pays, which
    means the column never arrives and the report keeps guessing. `kind` came
    this way in spec 028 and `source_sha256` in 029.
    """
    con.execute("""CREATE TABLE raw_file_audit (
        system_id VARCHAR, source_period VARCHAR, source_file VARCHAR,
        source_records BIGINT, rows_landed BIGINT, lines_repaired BIGINT)""")
    con.execute("INSERT INTO raw_file_audit VALUES ('van-mobi', '2023-06', 'x.csv', 1, 1, 0)")
    etl.ensure_audit_table(con)
    cols = [r[0] for r in con.execute("DESCRIBE raw_file_audit").fetchall()]
    assert cols[-2:] == ["kind", "source_sha256"]
    # The extract path inserts positionally; the widened table must accept it.
    con.execute("INSERT INTO raw_file_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ["van-mobi", "2023-07", "y.csv", 2, 2, 9, "trips", "a" * 64])
    assert con.execute("SELECT lines_repaired FROM raw_file_audit "
                       "WHERE source_file = 'y.csv'").fetchone()[0] == 9
    # And the pre-existing row keeps NULL rather than a fabricated checksum:
    # `check_reconciliation --recount` is what resolves it, by reading the file.
    assert con.execute("SELECT source_sha256 FROM raw_file_audit "
                       "WHERE source_file = 'x.csv'").fetchone()[0] is None


def test_a_marker_is_read_into_the_audit(con, archive):
    scrub = archive / "van-mobi" / etl.SCRUB_DIR_NAME
    scrub.mkdir()
    (scrub / "2023-06.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (scrub / "2023-06.csv.lines").write_text("17")
    audit_one(con)
    etl.backfill_encoding_repairs(con)
    assert con.execute("SELECT lines_repaired FROM raw_file_audit").fetchone()[0] == 17
    assert con.execute("SELECT value FROM etl_metrics WHERE metric = 'lines_repaired'"
                       ).fetchone()[0] == 17


def test_a_clean_file_records_zero(con, archive):
    audit_one(con)
    etl.backfill_encoding_repairs(con)
    assert con.execute("SELECT lines_repaired FROM raw_file_audit").fetchone()[0] == 0


def test_a_scrubbed_copy_with_no_marker_stops_the_run(con, archive):
    """The planted violation: the repair happened, the count is gone.

    Anything other than an abort here writes a number nobody measured into a
    document whose whole claim is that it measures things.
    """
    scrub = archive / "van-mobi" / etl.SCRUB_DIR_NAME
    scrub.mkdir()
    (scrub / "2023-06.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    audit_one(con)
    with pytest.raises(etl.MissingRepairMarker, match="repaired copy exists"):
        etl.backfill_encoding_repairs(con)


def test_a_marker_no_audited_file_claims_stops_the_run(con, archive):
    scrub = archive / "van-mobi" / etl.SCRUB_DIR_NAME
    scrub.mkdir()
    (scrub / "2023-09.csv.lines").write_text("4")
    audit_one(con)
    with pytest.raises(etl.MissingRepairMarker, match="belong to no audited file"):
        etl.backfill_encoding_repairs(con)


def test_a_missing_source_file_is_not_assumed_clean(con, archive):
    (archive / "van-mobi" / "2023-06.csv").unlink()
    audit_one(con)
    with pytest.raises(etl.MissingRepairMarker, match="not on disk"):
        etl.backfill_encoding_repairs(con)


def test_an_audited_period_the_manifest_does_not_pin_stops_the_run(con, archive):
    audit_one(con, period="1999-01", name="1999-01.csv")
    with pytest.raises(etl.MissingRepairMarker, match="absent from the manifest"):
        etl.backfill_encoding_repairs(con)


def test_an_empty_audit_is_not_a_pass(con):
    etl.ensure_audit_table(con)
    with pytest.raises(etl.MissingRepairMarker, match="nothing to backfill"):
        etl.backfill_encoding_repairs(con)


def test_workbooks_are_recorded_as_zero_without_looking_for_a_marker(con, archive):
    """A worksheet is read by openpyxl, which decodes XML — never a code page."""
    audit_one(con, period="2019-04", name="2019-04.xlsx#Sheet1")
    etl.backfill_encoding_repairs(con)
    assert con.execute("SELECT lines_repaired FROM raw_file_audit").fetchone()[0] == 0
