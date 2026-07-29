"""Pins for the two helpers specs 003 onward are built on."""

from __future__ import annotations

import hashlib
import json

import common


def test_sha256_matches_hashlib(tmp_path):
    payload = b"trans-canada-bikeshare\n" * 100_000  # spans the 1 MB read chunk
    path = tmp_path / "sample.bin"
    path.write_bytes(payload)
    assert common.sha256_file(path) == hashlib.sha256(payload).hexdigest()


def test_detect_format_reads_magic_bytes_not_extensions():
    assert common.detect_format(b"PK\x03\x04\x14\x00") == "zip"
    assert common.detect_format(b"trip_id,start_time\n1,2025-01-01\n") == "csv"
    assert common.detect_format(b"<!DOCTYPE html><html><body>nope") == "html"
    assert common.detect_format(b"\xff\xfe\x00\x00garbage") == "unknown"


def test_detect_format_handles_classic_mac_line_endings():
    # Some older exports ship bare-\r rows; they are still CSV.
    assert common.detect_format(b"a,b\r1,2\r") == "csv"


def test_detect_format_ignores_leading_whitespace_before_html():
    assert common.detect_format(b"\n\n  <html><head>") == "html"


def test_systems_registry_covers_the_three_tier_one_cities():
    assert sorted(common.SYSTEMS) == ["mtl-bixi", "tor-bikeshare", "van-mobi"]
    for key, meta in common.SYSTEMS.items():
        assert meta["source_page"].startswith("https://"), key
        assert meta["gbfs_station_information"].startswith("https://"), key


def test_manifest_roundtrip_is_sorted_and_scoped_per_system(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "MANIFEST_DIR", tmp_path)
    manifest = common.load_manifest("mtl-bixi")
    assert manifest["system_id"] == "mtl-bixi"
    assert manifest["sources"] == {}

    manifest["sources"]["2025"] = {"bytes": 1}
    manifest["sources"]["2014"] = {"bytes": 2}
    common.save_manifest("mtl-bixi", manifest)

    written = json.loads((tmp_path / "mtl-bixi.json").read_text(encoding="utf-8"))
    assert list(written["sources"]) == ["2014", "2025"], "sources must be sorted"
    assert not (tmp_path / "van-mobi.json").exists(), "manifests are per system"


def test_manifest_path_rejects_unknown_systems():
    try:
        common.manifest_path("cgy-scooters")
    except KeyError as exc:
        assert "cgy-scooters" in str(exc)
    else:
        raise AssertionError("expected a KeyError for an unregistered system")
