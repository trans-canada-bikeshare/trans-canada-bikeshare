"""Refresh each system's manifest from its own source of truth.

Discovery is cheap — it reads a page or an API and records where every file
lives. It never downloads a payload; that is download.py, and the archive is
several GB.

New periods are added. A changed URL for a period already in the manifest is
REPORTED, not applied, unless --accept-changes is passed. Toronto re-published
its 2024-2026 archives on the day of the spec-001 audit; a source that
repoints under us is exactly what this refusal exists to surface.

Usage:
  python pipeline/discover.py [--system van-mobi|mtl-bixi|tor-bikeshare]
                              [--accept-changes]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import urlparse

import requests

import common

ANCHOR_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
BIXI_YEAR_RE = re.compile(r"(?:DonneesOuvertes?|Historique-BIXI-)[_-]?(20\d\d)", re.I)
TORONTO_YEAR_RE = re.compile(r"(20\d\d)")

CKAN_PACKAGE = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show"
    "?id=bike-share-toronto-ridership-data"
)


def _clean_label(inner_html: str) -> str:
    label = re.sub(r"<[^>]+>", " ", inner_html)
    return label.replace("&amp;", "&").replace("&nbsp;", " ").strip()


def discover_van_mobi(html: str) -> tuple[dict[str, str], list[str]]:
    """Google Drive / Sheets links labelled by period on the system-data page."""
    found: dict[str, str] = {}
    unrecognized: list[str] = []
    for href, inner in ANCHOR_RE.findall(html):
        id_match = common.DRIVE_FILE_RE.match(href)
        if not id_match:
            continue
        label = _clean_label(inner)
        period = common.parse_mobi_period_label(label)
        url = common.drive_download_url(id_match.group(1))
        if period is None:
            unrecognized.append(f"{label!r} -> {href}")
        elif period in found and found[period] != url:
            unrecognized.append(f"duplicate period {period}: {href}")
        else:
            found[period] = url
    return found, unrecognized


def discover_mtl_bixi(html: str) -> tuple[dict[str, str], list[str]]:
    """Annual ZIP links on the BIXI open-data page.

    The year lives in the FILENAME, not the path — the URL path carries the
    WordPress upload date, so /uploads/2026/02/...2025...zip is the 2025 file.
    """
    found: dict[str, str] = {}
    unrecognized: list[str] = []
    for href, _inner in ANCHOR_RE.findall(html):
        if not href.lower().endswith(".zip"):
            continue
        basename = urlparse(href).path.rsplit("/", 1)[-1]
        match = BIXI_YEAR_RE.search(basename)
        if not match:
            unrecognized.append(f"zip with no recognizable year: {href}")
            continue
        year = match.group(1)
        if year in found and found[year] != href:
            unrecognized.append(f"duplicate year {year}: {href}")
        else:
            found[year] = href
    return found, unrecognized


def discover_tor_bikeshare(package: dict) -> tuple[dict[str, str], list[str]]:
    """Ridership resources from the CKAN package_show payload."""
    found: dict[str, str] = {}
    unrecognized: list[str] = []
    for resource in package.get("result", {}).get("resources", []):
        name = resource.get("name") or ""
        url = resource.get("url") or ""
        if "ridership" not in name.lower():
            continue
        if "readme" in name.lower():
            continue  # documentation, not data; read at spec 005
        years = TORONTO_YEAR_RE.findall(name)
        if not years:
            unrecognized.append(f"ridership resource with no year: {name!r}")
            continue
        # "bikeshare-ridership-2014-2015" covers two years in one workbook;
        # key it by its span so the range stays visible in the manifest.
        period = years[0] if len(years) == 1 else f"{years[0]}-{years[-1]}"
        if period in found and found[period] != url:
            unrecognized.append(f"duplicate period {period}: {url}")
        else:
            found[period] = url
    return found, unrecognized


def merge(
    manifest: dict, discovered: dict[str, str], accept_changes: bool
) -> dict[str, list[str]]:
    """Merge {period: url} into manifest['sources'], preserving pins.

    An existing period whose URL changed keeps its recorded checksum and old
    URL unless accept_changes — the pin is the contract, and silently
    repointing it would make the archive unreproducible.
    """
    report: dict[str, list[str]] = {"new": [], "unchanged": [], "changed": []}
    sources = manifest.setdefault("sources", {})
    for period, url in discovered.items():
        entry = sources.get(period)
        if entry is None:
            sources[period] = {
                "url": url,
                "sha256": None,
                "bytes": None,
                "content_format": None,
                "downloaded_at": None,
            }
            report["new"].append(period)
        elif entry.get("url") == url:
            report["unchanged"].append(period)
        else:
            report["changed"].append(f"{period}: {entry.get('url')} -> {url}")
            if accept_changes:
                entry["url"] = url
                # A new URL invalidates the pin; force a re-download.
                entry["sha256"] = None
                entry["bytes"] = None
                entry["content_format"] = None
                entry["downloaded_at"] = None
    return report


# Licence blocks record what spec 001 observed. Montreal's null is a finding,
# not a gap: the source page states no licence, terms, or attribution at all.
LICENCES: dict[str, dict] = {
    "van-mobi": {
        "name": "Mobi Data License Agreement",
        "url": "https://www.mobibikes.ca/en/system-data",
        "checked": "2026-07-28",
        "attribution": "Contains information from Mobi by Rogers.",
        "note": "Non-commercial analysis use. Carried from the sister project; "
        "re-confirm against the live page before any commercial use.",
    },
    "mtl-bixi": {
        "name": None,
        "url": "https://bixi.com/en/open-data/",
        "checked": "2026-07-28",
        "attribution": None,
        "note": "NO licence, terms, or attribution text is stated on the source "
        "page (observed, spec 001). A third party republishes the 2014-2021 "
        "files under CC BY-SA 4.0, but that is that author's choice and is not "
        "evidence of BIXI's terms. Resolve before shipping any "
        "Montreal-derived artifact.",
    },
    "tor-bikeshare": {
        "name": "Open Government Licence – Toronto",
        "url": "https://open.toronto.ca/open-data-licence/",
        "checked": "2026-07-28",
        "attribution": "Contains information licensed under the Open Government "
        "Licence – Toronto.",
        "note": "Portal-wide default; the CKAN record's own licence field is "
        "null. Permits commercial use.",
    },
}


def fetch(system_id: str) -> tuple[dict[str, str], list[str]]:
    headers = {"User-Agent": common.USER_AGENT}
    if system_id == "tor-bikeshare":
        response = requests.get(CKAN_PACKAGE, timeout=60, headers=headers)
        response.raise_for_status()
        return discover_tor_bikeshare(response.json())
    page = common.SYSTEMS[system_id]["source_page"]
    response = requests.get(page, timeout=60, headers=headers)
    response.raise_for_status()
    if system_id == "van-mobi":
        return discover_van_mobi(response.text)
    return discover_mtl_bixi(response.text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", choices=sorted(common.SYSTEMS), action="append")
    parser.add_argument("--accept-changes", action="store_true")
    args = parser.parse_args()

    failures = 0
    for system_id in args.system or sorted(common.SYSTEMS):
        print(f"\n=== {system_id} ({common.SYSTEMS[system_id]['city']})")
        try:
            discovered, unrecognized = fetch(system_id)
        except requests.RequestException as exc:
            print(f"  FAILED to reach source: {exc}", file=sys.stderr)
            failures += 1
            continue

        manifest = common.load_manifest(system_id)
        manifest["licence"] = LICENCES[system_id]
        report = merge(manifest, discovered, args.accept_changes)

        # Reference feeds are discovered from the registry, not scraped.
        reference = manifest.setdefault("reference", {})
        gbfs_url = common.SYSTEMS[system_id]["gbfs_station_information"]
        entry = reference.setdefault(
            "gbfs_station_information",
            {"url": gbfs_url, "sha256": None, "bytes": None, "downloaded_at": None},
        )
        if entry.get("url") != gbfs_url:
            print(f"  GBFS url changed: {entry['url']} -> {gbfs_url}")
            if args.accept_changes:
                entry.update({"url": gbfs_url, "sha256": None, "bytes": None})

        common.save_manifest(system_id, manifest)

        print(f"  discovered {len(discovered)} periods")
        print(f"  new {len(report['new'])} · unchanged {len(report['unchanged'])}")
        for line in report["changed"]:
            action = "updated" if args.accept_changes else "NOT applied (--accept-changes)"
            print(f"  changed url, {action}: {line}")
        for line in unrecognized:
            print(f"  unrecognized: {line}")
        if not discovered:
            print("  ERROR: no periods found; the page layout may have changed",
                  file=sys.stderr)
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
