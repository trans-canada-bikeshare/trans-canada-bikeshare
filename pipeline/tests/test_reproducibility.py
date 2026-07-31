"""The reproducibility guards of spec 029, each shown by a planted violation.

In the 009b style: every guard here is demonstrated by making it fail. A gate
that has only ever been observed passing has not been observed at all — this
project shipped a `make check-metrics` that printed "stub" and exited 0 for a
month, under a registry that claimed it was enforced.

Five guards, one per section below:

  transactions   an extract that aborts leaves the previous rows in place
  pins           a manifest entry without a checksum stops the run
  caches         a repaired copy is never served for different source bytes
  date order     an order the values cannot prove must be declared, or abort
  reconciliation the audit is still true of the archive the manifests pin

Fixtures are built in tmp_path, following `test_etl_audit.py`: nothing here
needs a committed data file, and a planted violation that lives in the
repository is one somebody eventually "fixes".
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import duckdb
import pytest

import check_reconciliation
import common
import etl

# Real headers from the real era maps. A fixture with invented column names
# would exercise the plumbing and prove nothing about the mapping it runs
# through, and `plan()` would reject it for the wrong reason.
VAN_HEADER = "Departure,Return,Departure station,Return station,Duration (sec.)"
VAN_ROW = "2024-06-01 08:00,2024-06-01 08:20,0001 Foo,0002 Bar,1200"
TOR_HEADER = "Trip Id,Start Time,End Time,Start Station Id,End Station Id,User Type"
TOR_ROW = "1,2024-06-01 08:00,2024-06-01 08:20,7000,7001,Annual Member"


def write_archive(root: Path, manifests: Path, files: dict[str, list[str]]) -> None:
    """`files` maps 'system_id/period' to the CSV lines to write."""
    for key, lines in files.items():
        system_id, period = key.split("/")
        (root / system_id).mkdir(parents=True, exist_ok=True)
        path = root / system_id / f"{period}.csv"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    by_system: dict[str, dict] = {}
    for key in files:
        system_id, period = key.split("/")
        path = root / system_id / f"{period}.csv"
        by_system.setdefault(system_id, {})[period] = {
            "url": f"https://example.invalid/{system_id}/{period}.csv",
            "sha256": common.sha256_file(path),
            "bytes": path.stat().st_size,
            "content_format": "csv",
        }
    manifests.mkdir(parents=True, exist_ok=True)
    for system_id, sources in by_system.items():
        (manifests / f"{system_id}.json").write_text(
            json.dumps({"system_id": system_id, "sources": sources}, indent=2),
            encoding="utf-8")


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A stand-in data tree: two systems, one pinned month each."""
    root, manifests = tmp_path / "data-raw", tmp_path / "manifests"
    write_archive(root, manifests, {
        "van-mobi/2024-06": [VAN_HEADER, VAN_ROW, VAN_ROW],
        "tor-bikeshare/2024-06": [TOR_HEADER, TOR_ROW],
    })
    monkeypatch.setattr(common, "DATA_RAW", root)
    monkeypatch.setattr(common, "MANIFEST_DIR", manifests)
    return root, manifests


@pytest.fixture
def con(tmp_path):
    c = duckdb.connect(str(tmp_path / "w.duckdb"))
    yield c
    c.close()


def repin(manifests: Path, root: Path, system_id: str, period: str) -> None:
    """Re-pin a manifest entry to whatever the file on disk now contains."""
    path = manifests / f"{system_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = root / system_id / f"{period}.csv"
    payload["sources"][period]["sha256"] = common.sha256_file(source)
    payload["sources"][period]["bytes"] = source.stat().st_size
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def counts(con) -> dict[str, int]:
    return dict(con.execute(
        "SELECT system_id, count(*) FROM raw_trips GROUP BY 1").fetchall())


# --------------------------------------------------------------------------
# Transactional extraction
# --------------------------------------------------------------------------

def test_a_clean_extract_lands_both_systems(con, tree):
    etl.run_extract(con, ["tor-bikeshare", "van-mobi"], None)
    assert counts(con) == {"tor-bikeshare": 1, "van-mobi": 2}


def test_a_failure_in_the_second_system_leaves_the_first_reloaded_and_the_second_intact(
        con, tree):
    """The planted violation: an unmapped header, mid-run.

    Before this, extraction DELETEd every requested system up front and loaded
    them one at a time, so this exact failure emptied van-mobi and left no
    record that it had ever held anything. The warehouse ended in a state no
    successful run could produce, which is the worst kind: every later stage
    reads it happily and reports a smaller archive as fact.
    """
    root, manifests = tree
    etl.run_extract(con, ["tor-bikeshare", "van-mobi"], None)
    before = counts(con)

    poisoned = root / "van-mobi" / "2024-06.csv"
    poisoned.write_text(f"{VAN_HEADER},Surprise\n{VAN_ROW},x\n", encoding="utf-8")
    repin(manifests, root, "van-mobi", "2024-06")

    with pytest.raises(etl.UnknownColumns, match="Surprise"):
        etl.run_extract(con, ["tor-bikeshare", "van-mobi"], None)

    after = counts(con)
    assert after["van-mobi"] == before["van-mobi"] == 2, (
        "van-mobi's previous rows must survive an abort while loading it"
    )
    assert after["tor-bikeshare"] == 1
    # And its audit must survive with them: an audit that outlives the rows it
    # describes is a reconciliation that passes over nothing.
    assert con.execute("SELECT count(*) FROM raw_file_audit "
                       "WHERE system_id = 'van-mobi'").fetchone()[0] == 1


def test_a_failure_in_the_first_system_changes_nothing_at_all(con, tree):
    root, manifests = tree
    etl.run_extract(con, ["van-mobi", "tor-bikeshare"], None)
    before = counts(con)
    (root / "van-mobi" / "2024-06.csv").write_text(
        f"{VAN_HEADER},Surprise\n{VAN_ROW},x\n", encoding="utf-8")
    repin(manifests, root, "van-mobi", "2024-06")
    with pytest.raises(etl.UnknownColumns):
        etl.run_extract(con, ["van-mobi", "tor-bikeshare"], None)
    assert counts(con) == before


def test_the_warehouse_is_queryable_after_an_aborted_extract(con, tree):
    """Not merely correct — usable. A rolled-back transaction that left the
    connection wedged would fail the same acceptance criterion."""
    root, manifests = tree
    etl.run_extract(con, ["van-mobi"], None)
    (root / "van-mobi" / "2024-06.csv").write_text(
        f"{VAN_HEADER},Surprise\n{VAN_ROW},x\n", encoding="utf-8")
    repin(manifests, root, "van-mobi", "2024-06")
    with pytest.raises(etl.UnknownColumns):
        etl.run_extract(con, ["van-mobi"], None)
    assert con.execute("SELECT count(*) FROM raw_trips").fetchone()[0] == 2
    con.execute("SELECT 1")


# --------------------------------------------------------------------------
# Strict manifests
# --------------------------------------------------------------------------

def test_a_manifest_entry_without_a_checksum_aborts(con, tree):
    """The planted violation: a pinless entry, which used to be skipped."""
    _, manifests = tree
    path = manifests / "van-mobi.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["sources"]["2024-06"].pop("sha256")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(etl.UnpinnedSource, match="no sha256"):
        etl.run_extract(con, ["van-mobi"], None)
    assert con.execute("SELECT count(*) FROM raw_trips").fetchone()[0] == 0


def test_an_unpinned_entry_names_the_download_that_fixes_it(tree):
    with pytest.raises(etl.UnpinnedSource) as exc:
        etl.require_sha("van-mobi", "2024-06", {"url": "x"})
    assert "download.py --system van-mobi --period 2024-06" in str(exc.value)


def test_the_deliberate_exclusion_still_works(con, tree, monkeypatch):
    """EXCLUDED is checked before the pin, so a period this pipeline never
    reads does not need a checksum to justify not reading it."""
    _, manifests = tree
    path = manifests / "tor-bikeshare.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["sources"]["2024-06"].pop("sha256")
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setitem(etl.EXCLUDED, ("tor-bikeshare", "2024-06"), "test exclusion")
    etl.run_extract(con, ["tor-bikeshare"], None)
    assert con.execute("SELECT count(*) FROM raw_trips").fetchone()[0] == 0


# --------------------------------------------------------------------------
# Checksum-keyed caches
# --------------------------------------------------------------------------

DIRTY_A = b"name\n25 York St \x96 Union\n"        # cp1252 en-dash
DIRTY_B = b"name\nKing\x92s College Cr.\n"        # cp1252 curly apostrophe


def test_the_repair_cache_is_not_served_for_different_content(tmp_path):
    """The planted violation: same filename, different bytes, same cache slot.

    A source re-published under the same name and accepted with
    `--accept-changes` would have been read back as last month's repaired copy,
    with every downstream count describing a file that no longer exists.
    """
    path = tmp_path / "2023-06.csv"
    path.write_bytes(DIRTY_A)
    first, repaired_a = etl.ensure_utf8(path, "a" * 64)
    assert repaired_a == 1 and "York" in first.read_text(encoding="utf-8")

    path.write_bytes(DIRTY_B)
    second, repaired_b = etl.ensure_utf8(path, "b" * 64)
    assert second == first, "same slot on disk — that is what makes this a trap"
    text = second.read_text(encoding="utf-8")
    assert "College" in text and "York" not in text, (
        "the cache served bytes from a source that is no longer there"
    )
    assert repaired_b == 1


def test_the_repair_cache_is_reused_for_identical_content(tmp_path):
    """The other half. A key that never hits is not a cache, it is a rebuild,
    and the archive is 20 GB."""
    path = tmp_path / "2023-06.csv"
    path.write_bytes(DIRTY_A)
    dest, _ = etl.ensure_utf8(path, "a" * 64)
    dest.write_text("SENTINEL\n", encoding="utf-8")   # would be overwritten
    again, repaired = etl.ensure_utf8(path, "a" * 64)
    assert again == dest and repaired == 1
    assert again.read_text(encoding="utf-8") == "SENTINEL\n"


def test_a_marker_with_no_checksum_is_not_a_cache_hit(tmp_path):
    """Migration: markers written before the key existed say nothing about
    which bytes produced them, so they are rebuilt rather than trusted."""
    path = tmp_path / "2023-06.csv"
    path.write_bytes(DIRTY_A)
    dest, _ = etl.ensure_utf8(path, "a" * 64)
    marker = dest.with_suffix(dest.suffix + ".lines")
    marker.write_text("1")                            # the old one-line format
    dest.write_text("SENTINEL\n", encoding="utf-8")
    again, repaired = etl.ensure_utf8(path, "a" * 64)
    assert again.read_text(encoding="utf-8") != "SENTINEL\n"
    assert repaired == 1
    assert etl.read_marker(marker) == (1, "a" * 64)


def test_the_backfill_still_reads_a_legacy_marker(tmp_path):
    """A marker without a checksum is still a truthful record of how many
    lines the copy beside it repaired, which is all the backfill asks."""
    marker = tmp_path / "x.csv.lines"
    marker.write_text("17")
    assert etl.read_marker(marker) == (17, None)
    etl.write_marker(marker, 17, "c" * 64)
    assert etl.read_marker(marker) == (17, "c" * 64)


def test_the_unpacked_archive_cache_is_keyed_by_checksum(tmp_path, monkeypatch):
    """The other cache, verified rather than assumed: a re-pinned zip at the
    same period must not serve the previous unpack."""
    import zipfile

    monkeypatch.setattr(common, "DATA_RAW", tmp_path)
    (tmp_path / "van-mobi").mkdir()
    archive = tmp_path / "van-mobi" / "2024-06.zip"

    def build(payload: str) -> dict:
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("inner.csv", payload)
        return {"sha256": common.sha256_file(archive), "content_format": "zip"}

    first = etl.tabular_files("van-mobi", "2024-06", build("a\n1\n"))
    assert first[0].read_text(encoding="utf-8") == "a\n1\n"
    second = etl.tabular_files("van-mobi", "2024-06", build("a\n2\n"))
    assert second[0].read_text(encoding="utf-8") == "a\n2\n"


# --------------------------------------------------------------------------
# Explicit date-order exceptions
# --------------------------------------------------------------------------

def date_order_map(tmp_path, monkeypatch, exceptions: dict) -> Path:
    monkeypatch.setattr(common, "MAPPINGS_DIR", tmp_path)
    (tmp_path / etl.DATE_ORDER_MAP).write_text(
        json.dumps({"exceptions": exceptions}), encoding="utf-8")
    return tmp_path


def plant_dates(con, values: list[str], system_id="van-mobi", source_file="x.csv"):
    """Land raw rows and derive the order the way the clean stage does."""
    etl.run_sql(con, "10_extract.sql")
    for v in values:
        con.execute("INSERT INTO raw_trips (system_id, source_period, source_file, "
                    "departure_raw) VALUES (?, '2024-06', ?, ?)",
                    [system_id, source_file, v])
    etl.run_sql(con, "15_dates.sql")


def derived(con) -> str:
    return con.execute("SELECT date_order FROM file_date_order").fetchone()[0]


def test_an_ambiguous_file_with_no_declaration_aborts(con, tmp_path, monkeypatch):
    """The planted fixture: every field 12 or under, so nothing proves itself.

    This used to print a line and parse month-first. Day-first and month-first
    agree on every date before the 13th, so the wrong choice is invisible in
    about 40% of the rows and moves the rest into another month entirely.
    """
    date_order_map(tmp_path, monkeypatch, {})
    plant_dates(con, ["05/06/2024 10:00", "07/08/2024 11:00"])
    assert derived(con) == "ambiguous"
    with pytest.raises(etl.AmbiguousDateOrder, match="cannot prove"):
        etl.resolve_date_orders(con)


def test_a_declared_order_resolves_an_ambiguous_file(con, tmp_path, monkeypatch):
    date_order_map(tmp_path, monkeypatch, {
        "van-mobi": {"x.csv": {"date_order": "day", "reason": "test",
                               "evidence": "test", "recorded": "2026-07-31"}}})
    plant_dates(con, ["05/06/2024 10:00"])
    etl.resolve_date_orders(con)
    row = con.execute("SELECT date_order, resolved_order FROM file_date_order").fetchone()
    assert row == ("ambiguous", "day"), "the evidence and the decision stay distinct"


def test_a_declaration_the_data_no_longer_needs_aborts(con, tmp_path, monkeypatch):
    """A stale exception is a claim nobody re-examined. If the file now proves
    its own order, the declaration would override evidence."""
    date_order_map(tmp_path, monkeypatch, {
        "van-mobi": {"x.csv": {"date_order": "day"}}})
    plant_dates(con, ["05/13/2024 10:00"])          # second field > 12: month-first
    assert derived(con) == "month"
    with pytest.raises(etl.StaleDateOrderException, match="no longer needed"):
        etl.resolve_date_orders(con)


def test_a_declaration_for_a_missing_file_aborts(con, tmp_path, monkeypatch):
    date_order_map(tmp_path, monkeypatch, {
        "van-mobi": {"gone.csv": {"date_order": "day"}}})
    plant_dates(con, ["05/06/2024 10:00"])
    with pytest.raises(etl.StaleDateOrderException, match="no file by that name"):
        etl.resolve_date_orders(con)


def test_a_declaration_for_an_unextracted_system_is_not_stale(con, tmp_path, monkeypatch):
    """A `--system` run or a fixture tree holds one system. Its absence says
    nothing about the others' declarations."""
    date_order_map(tmp_path, monkeypatch, {
        "mtl-bixi": {"x.csv": {"date_order": "day"}}})
    plant_dates(con, ["05/13/2024 10:00"])
    etl.resolve_date_orders(con)


def test_an_unusable_declared_order_aborts(con, tmp_path, monkeypatch):
    date_order_map(tmp_path, monkeypatch, {
        "van-mobi": {"x.csv": {"date_order": "month-first-probably"}}})
    plant_dates(con, ["05/06/2024 10:00"])
    with pytest.raises(etl.StaleDateOrderException, match="allowed"):
        etl.resolve_date_orders(con)


def test_a_four_digit_leading_field_is_a_year_not_an_ambiguity(con, tmp_path, monkeypatch):
    """Mobi's 2025-05 is 'YYYY/MM/DD' and was labelled ambiguous for two specs.

    Both evidence regexes capture one-or-two digits before a slash, so a
    four-digit year matched neither and both counts came out zero. The file
    parsed correctly by the month-first fallback, and the runbook, the clean
    log and the warehouse all reported an ambiguity it does not have.
    """
    date_order_map(tmp_path, monkeypatch, {})
    plant_dates(con, ["2025/05/02 01:21:44", "2025/05/31 22:00:00"])
    assert derived(con) == "year"
    etl.resolve_date_orders(con)        # no declaration needed, and none stale


def test_a_file_mixing_year_first_and_day_first_is_a_conflict(con, tmp_path, monkeypatch):
    date_order_map(tmp_path, monkeypatch, {})
    plant_dates(con, ["2025/05/02 01:21:44", "13/05/2025 10:00"])
    assert derived(con) == "conflict"
    with pytest.raises(etl.AmbiguousDateOrder):
        etl.resolve_date_orders(con)


def test_the_shipped_map_declares_nothing_the_data_cannot_prove():
    """The committed mapping is itself checked. Every entry must name a real
    system and a legal order — a typo here would abort a rebuild, not a test."""
    raw = json.loads((common.MAPPINGS_DIR / etl.DATE_ORDER_MAP)
                     .read_text(encoding="utf-8"))
    for system_id, files in raw["exceptions"].items():
        assert system_id in common.SYSTEMS, system_id
        for name, spec in files.items():
            assert spec["date_order"] in etl.DECLARABLE_ORDERS, (name, spec)
            assert spec.get("reason") and spec.get("evidence"), (
                f"{system_id} {name}: a declared date order without the "
                "evidence for it is the default it replaced, spelled longer"
            )


# --------------------------------------------------------------------------
# The standing reconciliation gate
# --------------------------------------------------------------------------

@pytest.fixture
def audited(con, tree):
    etl.run_extract(con, ["tor-bikeshare", "van-mobi"], None)
    return con


def test_a_reconciled_warehouse_passes(audited):
    assert check_reconciliation.check(audited, verbose=False) == []


def test_a_planted_count_mismatch_fails_the_gate(audited):
    """The violation the gate exists for: an audit row claiming the source
    held more records than landed. Extraction aborts on this, so a row
    carrying it means the audit and the archive have come apart."""
    audited.execute("UPDATE raw_file_audit SET source_records = 99 "
                    "WHERE system_id = 'van-mobi'")
    failures = check_reconciliation.check(audited, verbose=False)
    assert any("unaccounted for" in f for f in failures), failures


def test_a_null_column_fails_the_gate(audited):
    audited.execute("UPDATE raw_file_audit SET kind = NULL "
                    "WHERE system_id = 'van-mobi'")
    failures = check_reconciliation.check(audited, verbose=False)
    assert any("kind is NULL" in f for f in failures), failures


def test_an_unstamped_audit_fails_with_the_bootstrap_instruction(audited):
    audited.execute("UPDATE raw_file_audit SET source_sha256 = NULL")
    failures = check_reconciliation.check(audited, verbose=False)
    assert any("--recount" in f for f in failures), failures


def test_a_repinned_source_fails_until_the_warehouse_is_rebuilt(audited, tree):
    """The standing half. `download.py --accept-changes` re-pins a source a
    publisher republished; check-manifest passes, check-artifacts passes, and
    the row accounting now describes bytes that are gone."""
    root, manifests = tree
    (root / "van-mobi" / "2024-06.csv").write_text(
        f"{VAN_HEADER}\n{VAN_ROW}\n{VAN_ROW}\n{VAN_ROW}\n", encoding="utf-8")
    repin(manifests, root, "van-mobi", "2024-06")
    failures = check_reconciliation.check(audited, verbose=False)
    assert any("re-published and re-pinned" in f for f in failures), failures
    # The recount is what makes it actionable: it says what actually moved.
    assert any("2 -> 3" in f for f in failures), failures


def test_a_missing_manifest_period_fails_the_gate(audited, tree):
    _, manifests = tree
    path = manifests / "van-mobi.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["sources"]["2024-07"] = dict(payload["sources"]["2024-06"])
    path.write_text(json.dumps(payload), encoding="utf-8")
    failures = check_reconciliation.check(audited, verbose=False)
    assert any("landed nothing" in f for f in failures), failures


def test_an_empty_audit_is_not_a_pass(con):
    etl.ensure_audit_table(con)
    with pytest.raises(check_reconciliation.ReconciliationGateFailure,
                       match="empty"):
        check_reconciliation.check(con, verbose=False)


def test_a_warehouse_with_no_audit_at_all_is_not_a_pass(con):
    with pytest.raises(check_reconciliation.ReconciliationGateFailure,
                       match="no raw_file_audit"):
        check_reconciliation.check(con, verbose=False)


def test_recount_refuses_to_restamp_a_source_that_actually_changed(audited, tree):
    """The recount confirms; it never launders. Overwriting the recorded count
    with a fresh one would erase the only evidence the warehouse is stale."""
    root, manifests = tree
    (root / "van-mobi" / "2024-06.csv").write_text(
        f"{VAN_HEADER}\n{VAN_ROW}\n{VAN_ROW}\n{VAN_ROW}\n", encoding="utf-8")
    repin(manifests, root, "van-mobi", "2024-06")
    failures = check_reconciliation.recount(audited, verbose=False)
    assert any("diverged" in f for f in failures), failures
    stored = audited.execute("SELECT source_records FROM raw_file_audit "
                             "WHERE system_id = 'van-mobi'").fetchone()[0]
    assert stored == 2, "the audit still says what extraction measured"


def test_the_gate_runs_inside_make_check():
    """A gate nothing calls is a file. `make check` is what `/feature review`
    runs, and this is the line that puts the new one in it."""
    makefile = (common.REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    target = next(l for l in makefile.splitlines() if l.startswith("check:"))
    assert "check-reconciliation" in target, target
    assert "check_reconciliation.py" in makefile


# --------------------------------------------------------------------------
# The pinned interpreter and the configuration surface
# --------------------------------------------------------------------------

def test_the_pinned_python_version_is_asserted_not_assumed():
    common.require_python((3, 11))
    with pytest.raises(common.WrongPython, match="pinned to Python 3.11"):
        common.require_python((3, 12))


def test_the_lock_pins_every_installed_package_with_hashes():
    """The lock is only a lock if it covers everything and hashes all of it."""
    text = (common.PIPELINE_DIR / "requirements.lock").read_text(encoding="utf-8")
    pinned = {ln.split("==")[0].lower().replace("_", "-")
              for ln in text.splitlines() if "==" in ln and not ln.startswith("#")}
    required = {ln.split(">=")[0].split("==")[0].strip().lower().replace("_", "-")
                for ln in (common.PIPELINE_DIR / "requirements.txt")
                .read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")}
    assert required <= pinned, f"not locked: {sorted(required - pinned)}"
    assert "duckdb" in pinned
    for line in text.splitlines():
        if "==" in line and not line.startswith("#"):
            assert line.rstrip().endswith("\\"), (
                f"{line}: a pin with no --hash continuation is a version, not a lock"
            )
    assert text.count("--hash=sha256:") >= len(pinned)


def reload_common(monkeypatch, **env):
    for key in ("BIKESHARE_DATA_ROOT", "BIKESHARE_DATA_RAW",
                "BIKESHARE_DATA_WAREHOUSE", "BIKESHARE_MANIFEST_DIR",
                "BIKESHARE_GENERATED_DIR", "BIKESHARE_DUCKDB_MEMORY_LIMIT",
                "BIKESHARE_DUCKDB_THREADS"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(common)


def test_data_root_moves_the_archive_the_warehouse_and_the_manifests_together(
        tmp_path, monkeypatch):
    """They are one unit. A fixture archive read against the real manifests
    fails every checksum; the real archive read against fixture manifests
    passes checks that mean nothing."""
    try:
        mod = reload_common(monkeypatch, BIKESHARE_DATA_ROOT=str(tmp_path))
        assert mod.DATA_RAW == tmp_path / "data-raw"
        assert mod.DATA_WAREHOUSE == tmp_path / "data-warehouse"
        assert mod.MANIFEST_DIR == tmp_path / "manifests"
    finally:
        reload_common(monkeypatch)


def test_the_mappings_are_code_and_have_no_override(tmp_path, monkeypatch):
    """The era maps, the membership groups, the metric registry and the
    date-order exceptions decide what the bytes MEAN. A run that could swap
    them could make any archive parse 'correctly'."""
    try:
        mod = reload_common(monkeypatch, BIKESHARE_DATA_ROOT=str(tmp_path))
        assert mod.MAPPINGS_DIR == mod.PIPELINE_DIR / "mappings"
        monkeypatch.setenv("BIKESHARE_MAPPINGS_DIR", str(tmp_path))
        assert importlib.reload(common).MAPPINGS_DIR == mod.PIPELINE_DIR / "mappings"
    finally:
        monkeypatch.delenv("BIKESHARE_MAPPINGS_DIR", raising=False)
        reload_common(monkeypatch)


def test_each_path_can_be_moved_on_its_own(tmp_path, monkeypatch):
    try:
        mod = reload_common(monkeypatch, BIKESHARE_DATA_RAW=str(tmp_path / "r"),
                            BIKESHARE_GENERATED_DIR=str(tmp_path / "g"))
        assert mod.DATA_RAW == tmp_path / "r"
        assert mod.GENERATED_DIR == tmp_path / "g"
        assert mod.DATA_WAREHOUSE == mod.REPO_ROOT / "data-warehouse"
    finally:
        reload_common(monkeypatch)


def test_the_resource_limits_default_to_the_measured_values(monkeypatch):
    try:
        assert reload_common(monkeypatch).DUCKDB_MEMORY_LIMIT == "10GB"
        assert common.DUCKDB_THREADS == 8
        mod = reload_common(monkeypatch, BIKESHARE_DUCKDB_MEMORY_LIMIT="512MB",
                            BIKESHARE_DUCKDB_THREADS="2")
        assert mod.DUCKDB_MEMORY_LIMIT == "512MB" and mod.DUCKDB_THREADS == 2
    finally:
        reload_common(monkeypatch)


def test_the_connection_honours_the_configured_limits(tmp_path):
    con = etl.connect(tmp_path / "w.duckdb", memory_limit="512MB", threads=2)
    try:
        assert con.execute("SELECT current_setting('threads')").fetchone()[0] == 2
        # DuckDB reports the limit back in binary units ('488.2 MiB'), so the
        # assertion is on the magnitude, not the string that was passed in.
        limit = str(con.execute("SELECT current_setting('memory_limit')").fetchone()[0])
        assert limit.endswith("MiB"), f"{limit} — the default is 9.3 GiB"
    finally:
        con.close()


def test_an_offline_run_refuses_rather_than_reaching_for_an_extension(
        tmp_path, monkeypatch):
    """BIKESHARE_ALLOW_EXTENSION_INSTALL=0 is what makes 'offline' checkable.

    `excel` is not bundled in the DuckDB wheel — `icu` is — so an empty
    extension directory plus a forbidden install must produce a named refusal
    naming the variable, not a silent download.
    """
    monkeypatch.setattr(common, "DUCKDB_EXTENSION_DIR", str(tmp_path / "ext"))
    monkeypatch.setattr(common, "DUCKDB_ALLOW_EXTENSION_INSTALL", False)
    con = duckdb.connect()
    try:
        con.execute(f"SET extension_directory = '{tmp_path / 'ext'}'")
        with pytest.raises(etl.ExtensionUnavailable, match="BIKESHARE_ALLOW"):
            etl.load_extension(con, "excel")
    finally:
        con.close()


def test_a_csv_only_run_never_asks_for_the_excel_extension(con, tree, monkeypatch):
    """The reason `excel` is loaded where it is used. `INSTALL excel` ran on
    every invocation of this script, including stages that read no files at
    all — which put a network call in the middle of a run that has none."""
    monkeypatch.setattr(common, "DUCKDB_ALLOW_EXTENSION_INSTALL", False)
    calls: list[str] = []
    real = etl.load_extension
    monkeypatch.setattr(etl, "load_extension",
                        lambda c, n: (calls.append(n), real(c, n))[1])
    etl.run_extract(con, ["van-mobi"], None)
    assert "excel" not in calls, calls
    assert con.execute("SELECT count(*) FROM raw_trips").fetchone()[0] == 2


def test_icu_is_bundled_and_needs_no_install(tmp_path, monkeypatch):
    """The claim the extension comment rests on, checked rather than recalled.

    `INSTALL icu` ran on every connection this pipeline ever opened, asking a
    repository for something already inside the process.
    """
    monkeypatch.setattr(common, "DUCKDB_EXTENSION_DIR", str(tmp_path / "ext"))
    con = duckdb.connect()
    try:
        con.execute(f"SET extension_directory = '{tmp_path / 'ext'}'")
        con.execute("LOAD icu")
        mode = con.execute("SELECT install_mode FROM duckdb_extensions() "
                           "WHERE extension_name = 'icu'").fetchone()[0]
        assert mode == "STATICALLY_LINKED"
    finally:
        con.close()
