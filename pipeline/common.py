"""Shared helpers for the Trans-Canada Bikeshare pipeline.

Scaffold (spec 002): paths, the system registry, checksums, and format
detection. The downloader, ETL, and publish stages arrive in specs 003 onward.

Spec 029 adds the runtime configuration every stage reads: the Python version
this pipeline is pinned to, and the environment overrides that let the whole
pipeline be pointed at a different data tree without editing a line. See
`docs/runbook.md`, "Configuration".
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

USER_AGENT = "trans-canada-bikeshare-pipeline (+https://github.com/adnanreza)"

# The one place the Python version is stated. `pipeline/requirements.lock`
# carries CPython 3.11 (`cp311`) wheel hashes and nothing else, so 3.12 has
# nothing to install — but a machine with the packages already present would
# otherwise run happily on an interpreter this project has never tested, and
# find out at the first behavioural difference rather than at startup.
PYTHON_REQUIRES = (3, 11)


class WrongPython(Exception):
    """The interpreter is not the version the lock file pins."""


def require_python(version: tuple[int, int] | None = None) -> None:
    """Abort on an interpreter the lock file does not cover.

    Called at import, because every pipeline entry point imports this module
    and the failure has to arrive before any work does. Loud, named, and with
    the fix in the message — the same shape as every other refusal here.
    """
    found = version or sys.version_info[:2]
    if tuple(found) != PYTHON_REQUIRES:
        want = ".".join(str(n) for n in PYTHON_REQUIRES)
        have = ".".join(str(n) for n in found)
        raise WrongPython(
            f"this pipeline is pinned to Python {want}; running on {have}. "
            f"pipeline/requirements.lock contains cp{PYTHON_REQUIRES[0]}"
            f"{PYTHON_REQUIRES[1]} wheel hashes only, so the environment this "
            "is running in was not built from it. Create the venv with "
            f"python{want} and install from the lock."
        )


require_python()


def env_path(name: str, default: Path) -> Path:
    """An overridable path. Empty or unset means the default.

    Paths are resolved so a relative override ('--data-root ./fixtures') means
    the same thing to every stage regardless of where it was launched from.
    """
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser().resolve() if raw else default


MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    # The Mobi system-data page misspells November 2021's label. Accommodate
    # the exact observed typo rather than fuzzy-matching month names — a fuzzy
    # matcher would also silently swallow a genuinely new label.
    "novemeber": 11,
}

DRIVE_FILE_RE = re.compile(
    r"https://(?:drive|docs)\.google\.com/(?:file/d|spreadsheets/d)/([\w-]+)"
)

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent

# Where the data lives. Every one of these is overridable, because a fixture
# run has to be able to point the WHOLE pipeline — etl, publish, the quality
# report and every gate — at a different tree in one move. `BIKESHARE_DATA_ROOT`
# moves the three that must move together; the individual variables exist for
# the cases where they must not.
#
# The archive, the warehouse and the manifests are one unit: a manifest pins
# the bytes in the archive, and the warehouse records which pinned bytes it was
# built from. Point two of them at a fixture tree and the third at the real one
# and every checksum comparison is meaningless. So DATA_ROOT moves all three,
# to `<root>/data-raw`, `<root>/data-warehouse` and `<root>/manifests`.
_DATA_ROOT_SET = bool(os.environ.get("BIKESHARE_DATA_ROOT", "").strip())
DATA_ROOT = env_path("BIKESHARE_DATA_ROOT", REPO_ROOT)
DATA_RAW = env_path("BIKESHARE_DATA_RAW", DATA_ROOT / "data-raw")
DATA_WAREHOUSE = env_path("BIKESHARE_DATA_WAREHOUSE", DATA_ROOT / "data-warehouse")
# Manifests default to their in-repo home, which is NOT under DATA_ROOT — they
# are committed and versioned. Once DATA_ROOT moves, they move with it, because
# a fixture archive pinned by the real manifests would fail every checksum.
MANIFEST_DIR = env_path(
    "BIKESHARE_MANIFEST_DIR",
    DATA_ROOT / "manifests" if _DATA_ROOT_SET else PIPELINE_DIR / "manifests",
)

# NOT overridable, deliberately. The era maps, the membership groups, the
# metric registry and the date-order exceptions are CODE: they encode decisions
# about what the published bytes mean, they are reviewed as code, and every one
# of them is the thing a gate checks against. A run that could swap them out
# could also make any archive parse "correctly", which is the one substitution
# this project must not permit — a fixture run proves the mappings work, it
# does not get its own.
MAPPINGS_DIR = PIPELINE_DIR / "mappings"

# The site's data directory. Separate from DATA_ROOT because publishing to a
# scratch directory while reading the real warehouse is a legitimate thing to
# want (`publish.py --out`), and the freshness gate is what stops it shipping.
GENERATED_DIR = env_path("BIKESHARE_GENERATED_DIR", REPO_ROOT / "src" / "data" / "generated")

# DuckDB runtime limits. The defaults are what specs 005-008 measured on a
# 16 GB machine against 135.6M rows; a smaller machine or a CI runner needs
# smaller, and neither should have to edit etl.py to say so.
DUCKDB_MEMORY_LIMIT = os.environ.get("BIKESHARE_DUCKDB_MEMORY_LIMIT", "").strip() or "10GB"
DUCKDB_THREADS = int(os.environ.get("BIKESHARE_DUCKDB_THREADS", "").strip() or "8")

# Where DuckDB keeps its extension binaries. Unset means DuckDB's own default
# (~/.duckdb). A CI job that caches this directory installs the excel extension
# once instead of on every run — see etl.load_extensions for why one extension
# needs a network install at all and the other does not.
DUCKDB_EXTENSION_DIR = os.environ.get("BIKESHARE_DUCKDB_EXTENSION_DIR", "").strip()

# Set to "0" to forbid the network install of a missing DuckDB extension, so a
# run that claims to be offline fails instead of quietly reaching out.
DUCKDB_ALLOW_EXTENSION_INSTALL = (
    os.environ.get("BIKESHARE_ALLOW_EXTENSION_INSTALL", "").strip() != "0"
)

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


def parse_mobi_period_label(label: str) -> str | None:
    """Map a link label on the Mobi system-data page to a period key.

    "May 2026" -> "2026-05"; "ALL of 2017" -> "2017"; anything else -> None,
    which the caller must treat as an unrecognized label to report, not skip.
    """
    text = re.sub(r"\s+", " ", label).strip().lower()
    if re.fullmatch(r"all of 2017", text):
        return "2017"
    match = re.fullmatch(r"([a-z]+) (\d{4})", text)
    if match and match.group(1) in MONTH_NAMES:
        return f"{match.group(2)}-{MONTH_NAMES[match.group(1)]:02d}"
    return None


def drive_download_url(file_id: str) -> str:
    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"


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
        "data_terms": (
            "All data-source terms are collected in DATA-LICENSES.md at the "
            "repository root; the obligations in this manifest's licence "
            "entries are recorded there, and neither file supersedes the "
            "other."
        ),
        "licence": None,
        "sources": {},
        "reference": {},
    }


def local_path(system_id: str, period: str, content_format: str | None) -> Path:
    """Where a downloaded source file lives. Extension follows detected content,
    never the URL — see detect_format."""
    ext = extension_for(content_format) if content_format else ""
    return DATA_RAW / system_id / f"{period}{ext}"


def reference_path(system_id: str, name: str) -> Path:
    """Where a pinned reference file lives.

    Extension follows the name: GBFS feeds are JSON, ECCC climate years are
    CSV. Anything else defaults to JSON, which is what every reference entry
    was before spec 013 added weather.
    """
    ext = ".csv" if name.startswith("weather_") else ".json"
    return DATA_RAW / system_id / "reference" / f"{name}{ext}"


def save_manifest(system_id: str, manifest: dict) -> None:
    manifest["sources"] = dict(sorted(manifest.get("sources", {}).items()))
    path = manifest_path(system_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic: this is rewritten after every downloaded file during a multi-GB
    # run, so an in-place write is a standing invitation to truncate the
    # manifest — losing every pin from the run and breaking load_manifest for
    # every later command.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)
