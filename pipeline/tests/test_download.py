"""Pure-logic pins for the downloader and inventory. No network."""

from __future__ import annotations

import hashlib

import common
import download
import inventory
import pytest


def write(path, payload: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def test_a_matching_file_is_satisfied_so_no_request_is_made(tmp_path):
    payload = b"trip_id,start\n1,2025-01-01\n"
    path = tmp_path / "2025.csv"
    sha = write(path, payload)
    entry = {"sha256": sha, "bytes": len(payload)}
    assert download.entry_is_satisfied(entry, path) is True


def test_unsatisfied_when_unpinned_absent_or_altered(tmp_path):
    payload = b"a,b\n1,2\n"
    path = tmp_path / "2025.csv"
    sha = write(path, payload)

    assert download.entry_is_satisfied({"sha256": None}, path) is False
    assert download.entry_is_satisfied({"sha256": sha}, tmp_path / "nope.csv") is False
    assert download.entry_is_satisfied({"sha256": "0" * 64, "bytes": len(payload)}, path) is False
    # A byte-size mismatch short-circuits before the (expensive) hash.
    assert download.entry_is_satisfied({"sha256": sha, "bytes": 999}, path) is False


def test_first_download_pins_the_entry():
    entry = {"sha256": None, "bytes": None, "content_format": None, "downloaded_at": None}
    status = download.apply_result(entry, "a" * 64, 123, "zip", accept_changes=False)
    assert status == "pinned"
    assert entry["sha256"] == "a" * 64 and entry["bytes"] == 123
    assert entry["content_format"] == "zip"
    assert entry["downloaded_at"] is not None


def test_redownloading_identical_content_verifies_rather_than_repins():
    entry = {"sha256": "a" * 64, "bytes": 123, "content_format": "zip"}
    assert download.apply_result(entry, "a" * 64, 123, "zip", accept_changes=False) == "verified"


def test_drift_refuses_and_leaves_the_pin_untouched():
    entry = {"sha256": "a" * 64, "bytes": 123, "content_format": "zip"}
    with pytest.raises(download.Drift) as exc:
        download.apply_result(entry, "b" * 64, 456, "zip", accept_changes=False)
    assert "--accept-changes" in str(exc.value)
    assert entry["sha256"] == "a" * 64, "a refused download must not move the pin"
    assert entry["bytes"] == 123


def test_drift_repins_only_when_explicitly_accepted():
    entry = {"sha256": "a" * 64, "bytes": 123, "content_format": "zip"}
    assert download.apply_result(entry, "b" * 64, 456, "zip", accept_changes=True) == "repinned"
    assert entry["sha256"] == "b" * 64 and entry["bytes"] == 456


def test_inventory_separates_pending_from_failed(tmp_path):
    payload = b"x,y\n1,2\n"
    good = tmp_path / "good.csv"
    sha = write(good, payload)

    assert inventory.classify({"sha256": None}, good)[0] == inventory.PENDING
    assert inventory.classify({"sha256": sha, "bytes": len(payload)}, good)[0] == inventory.OK
    assert inventory.classify({"sha256": sha}, tmp_path / "gone.csv")[0] == inventory.MISSING
    assert inventory.classify({"sha256": "0" * 64, "bytes": len(payload)}, good)[0] == inventory.CORRUPT
    assert inventory.classify({"sha256": sha, "bytes": 5}, good)[0] == inventory.SIZE
    # Pending must never be counted as a failure — a partial archive is normal.
    assert inventory.PENDING not in inventory.FAILING


def test_monthly_gaps_are_detected_for_vancouver_only():
    periods = ["2017", "2018-01", "2018-02", "2018-05"]
    assert inventory.expected_gaps("van-mobi", periods) == ["2018-03", "2018-04"]
    # Annual publishers: a missing year, not a missing month.
    assert inventory.expected_gaps("tor-bikeshare", ["2014", "2016"]) == ["2015"]
    assert inventory.expected_gaps("mtl-bixi", ["2014", "2015", "2016"]) == []


def test_local_paths_are_scoped_per_system():
    a = common.local_path("van-mobi", "2025-01", "csv")
    b = common.local_path("mtl-bixi", "2025", "zip")
    assert a.parent.name == "van-mobi" and a.name == "2025-01.csv"
    assert b.parent.name == "mtl-bixi" and b.name == "2025.zip"
    assert common.reference_path("tor-bikeshare", "gbfs_station_information").parent.name == "reference"


def test_html_is_never_accepted_as_data():
    # A Drive link that expires starts serving an interstitial page; storing it
    # as a trip file would poison the archive silently.
    assert common.detect_format(b"<!DOCTYPE html><html>Sign in") == "html"
