"""Shared helpers for the Trans-Canada Bikeshare pipeline.

Scaffold (spec 002): paths, the system registry, checksums, and format
detection. The downloader, ETL, and publish stages arrive in specs 003 onward.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent
DATA_RAW = REPO_ROOT / "data-raw"
DATA_WAREHOUSE = REPO_ROOT / "data-warehouse"
MANIFEST_DIR = PIPELINE_DIR / "manifests"
MAPPINGS_DIR = PIPELINE_DIR / "mappings"
GENERATED_DIR = REPO_ROOT / "src" / "data" / "generated"

# Total gzipped budget for everything published to the browser. The Vancouver
# project ships ~80 KB for one city; three cities plus comparison artifacts get
# proportionally more, but not unboundedly more. Enforced from spec 014.
PUBLISH_BUDGET_BYTES = 320 * 1024

# One entry per docked system. `key` is the system_id carried by every fact and
# dimension row — it is what makes a cross-city query either comparable or
# explicitly not. Tier 2 (Calgary, Edmonton dockless) is deliberately absent:
# see docs/decisions.md.
SYSTEMS: dict[str, dict[str, str]] = {
    "van-mobi": {
        "city": "Vancouver",
        "system": "Mobi by Rogers",
        "source_page": "https://www.mobibikes.ca/en/system-data",
        "gbfs_station_information": (
            "https://gbfs.kappa.fifteen.eu/gbfs/2.2/mobi/en/station_information.json"
        ),
        "first_year": "2017",
    },
    "mtl-bixi": {
        "city": "Montreal",
        "system": "BIXI",
        "source_page": "https://bixi.com/en/open-data/",
        "gbfs_station_information": (
            "https://gbfs.velobixi.com/gbfs/2-2/en/station_information.json"
        ),
        "first_year": "2014",
    },
    "tor-bikeshare": {
        "city": "Toronto",
        "system": "Bike Share Toronto",
        "source_page": (
            "https://open.toronto.ca/dataset/bike-share-toronto-ridership-data/"
        ),
        "gbfs_station_information": (
            "https://toronto.publicbikesystem.net/customer/gbfs/v2/en/station_information"
        ),
        "first_year": "2014",
    },
}

# The window in which all three systems publish. Cross-city comparisons default
# to it; per-city views use each system's own full range. See docs/roadmap.md.
COMMON_WINDOW_FIRST_YEAR = "2017"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_format(head: bytes) -> str:
    """Classify downloaded content from its first bytes: zip, xlsx, csv, html.

    Extensions lie — Toronto serves annual archives, BIXI serves a ZIP whose
    member is a 2.8 GB CSV, and Mobi's Drive links have returned XLSX, CSV, and
    Google Sheets exports for the same period across years. Magic bytes do not.
    """
    if head.startswith(b"PK\x03\x04"):
        # Both xlsx and zip are PK archives; the caller disambiguates by
        # inspecting members. Reported as zip here, refined at download time.
        return "zip"
    sample = head[:4096].lstrip()
    lowered = sample[:512].lower()
    if lowered.startswith(b"<!doctype") or lowered.startswith(b"<html") or b"<html" in lowered:
        return "html"
    try:
        text = sample.decode("utf-8")
    except UnicodeDecodeError:
        return "unknown"
    # Some older exports use bare-\r (classic Mac) line endings.
    if "," in text and ("\n" in text or "\r" in text):
        return "csv"
    return "unknown"


def extension_for(fmt: str) -> str:
    return {"xlsx": ".xlsx", "csv": ".csv", "zip": ".zip"}[fmt]


def manifest_path(system_id: str) -> Path:
    if system_id not in SYSTEMS:
        raise KeyError(f"unknown system {system_id!r}; known: {sorted(SYSTEMS)}")
    return MANIFEST_DIR / f"{system_id}.json"


def load_manifest(system_id: str) -> dict:
    path = manifest_path(system_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "system_id": system_id,
        "source_page": SYSTEMS[system_id]["source_page"],
        "sources": {},
        "reference": {},
    }


def save_manifest(system_id: str, manifest: dict) -> None:
    manifest["sources"] = dict(sorted(manifest.get("sources", {}).items()))
    path = manifest_path(system_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
