"""Pure-logic pins for discovery. No network."""

from __future__ import annotations

import common
import discover


def test_mobi_period_labels_including_the_shipped_typo():
    assert common.parse_mobi_period_label("May 2026") == "2026-05"
    assert common.parse_mobi_period_label("ALL of 2017") == "2017"
    assert common.parse_mobi_period_label("  january   2018 ") == "2018-01"
    # The system-data page really does misspell this one.
    assert common.parse_mobi_period_label("Novemeber 2021") == "2021-11"
    # Anything unrecognized must return None so the caller reports it.
    assert common.parse_mobi_period_label("Q3 2020") is None
    assert common.parse_mobi_period_label("Smarch 2019") is None


def test_mobi_discovery_reports_unrecognized_links_rather_than_skipping():
    html = """
      <a href="https://drive.google.com/file/d/AAA111/view">June 2026</a>
      <a href="https://docs.google.com/spreadsheets/d/BBB222/edit">ALL of 2017</a>
      <a href="https://drive.google.com/file/d/CCC333/view">Mystery Export</a>
      <a href="https://example.com/not-drive.csv">May 2026</a>
    """
    found, unknown = discover.discover_van_mobi(html)
    assert set(found) == {"2026-06", "2017"}
    assert "AAA111" in found["2026-06"]
    assert len(unknown) == 1 and "Mystery Export" in unknown[0]


def test_bixi_year_comes_from_the_filename_not_the_upload_path():
    # The WordPress path carries the upload date: /uploads/2026/02/ holds 2025.
    html = """
      <a href="https://cdn.bixi.com/wp-content/uploads/2026/02/DonneesOuvertes2025_0102.zip">2025</a>
      <a href="https://cdn.bixi.com/wp-content/uploads/2023/06/Historique-BIXI-2014.zip">2014</a>
      <a href="https://cdn.bixi.com/wp-content/uploads/2023/08/DonneesOuverte2022.zip">2022</a>
      <a href="https://cdn.bixi.com/wp-content/uploads/x/readme.pdf">not a zip</a>
    """
    found, unknown = discover.discover_mtl_bixi(html)
    assert set(found) == {"2025", "2014", "2022"}
    assert "2026" not in found, "upload-path year must not win over the filename"
    assert unknown == []


def test_bixi_reports_a_zip_with_no_recognizable_year():
    html = '<a href="https://cdn.bixi.com/wp-content/uploads/2026/02/mystery.zip">?</a>'
    found, unknown = discover.discover_mtl_bixi(html)
    assert found == {}
    assert len(unknown) == 1


def test_toronto_spans_are_keyed_by_their_range():
    package = {"result": {"resources": [
        {"name": "bikeshare-ridership-2017", "url": "https://x/2017.zip"},
        {"name": "bikeshare-ridership-2014-2015", "url": "https://x/1415.xlsx"},
        {"name": "bikeshare-ridership-readme", "url": "https://x/readme.xlsx"},
        {"name": "some-other-dataset", "url": "https://x/other.zip"},
    ]}}
    found, unknown = discover.discover_tor_bikeshare(package)
    assert set(found) == {"2017", "2014-2015"}
    assert unknown == []


def test_merge_adds_new_periods_and_leaves_pins_alone():
    manifest = {"sources": {}}
    report = discover.merge(manifest, {"2024": "https://a/2024.zip"}, accept_changes=False)
    assert report["new"] == ["2024"]
    assert manifest["sources"]["2024"]["sha256"] is None

    manifest["sources"]["2024"].update({"sha256": "abc", "bytes": 10})
    report = discover.merge(manifest, {"2024": "https://a/2024.zip"}, accept_changes=False)
    assert report["unchanged"] == ["2024"]
    assert manifest["sources"]["2024"]["sha256"] == "abc"


def test_a_changed_url_is_reported_but_not_applied():
    manifest = {"sources": {"2024": {"url": "https://old/2024.zip", "sha256": "abc"}}}
    report = discover.merge(manifest, {"2024": "https://new/2024.zip"}, accept_changes=False)
    assert len(report["changed"]) == 1
    assert manifest["sources"]["2024"]["url"] == "https://old/2024.zip"
    assert manifest["sources"]["2024"]["sha256"] == "abc", "pin must survive"


def test_accepting_a_changed_url_invalidates_the_pin():
    manifest = {"sources": {"2024": {"url": "https://old/2024.zip", "sha256": "abc",
                                     "bytes": 1, "content_format": "zip"}}}
    discover.merge(manifest, {"2024": "https://new/2024.zip"}, accept_changes=True)
    entry = manifest["sources"]["2024"]
    assert entry["url"] == "https://new/2024.zip"
    assert entry["sha256"] is None, "a new URL must force a re-download"
    assert entry["bytes"] is None and entry["content_format"] is None


def test_every_system_has_a_licence_block_including_montreals_null():
    assert set(discover.LICENCES) == set(common.SYSTEMS)
    assert discover.LICENCES["mtl-bixi"]["name"] is None
    assert "NO licence" in discover.LICENCES["mtl-bixi"]["note"]
    assert discover.LICENCES["tor-bikeshare"]["attribution"].startswith("Contains information")
