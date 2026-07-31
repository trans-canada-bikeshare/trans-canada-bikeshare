"""The synthetic fixture archive has to keep its own contract.

`make check-fixture` runs the pipeline over `pipeline/tests/fixtures/archive`
and would fail on any of the defects below — but it would fail late, with a
checksum error or an unmapped-header abort forty seconds into a CI job, and it
needs the whole toolchain to say so. These are the same claims asked directly of
the committed bytes, in milliseconds, with no warehouse.

Three of them exist because the fixture is a claim about provenance as much as
about parsing: a manifest with a real-looking licence over invented data would
be exactly the "stated and wrong" failure `docs/decisions.md` records for ECCC.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

import common

FIXTURES = common.PIPELINE_DIR / "tests" / "fixtures"
ARCHIVE = FIXTURES / "archive"
MANIFESTS = FIXTURES / "manifests"

SYSTEMS = sorted(common.SYSTEMS)

# The marker every fixture manifest carries, from generate_fixtures.SYNTHETIC.
SYNTHETIC = "SYNTHETIC FIXTURE DATA"


def manifest(system_id: str) -> dict:
    return json.loads((MANIFESTS / f"{system_id}.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("system_id", SYSTEMS)
def test_every_fixture_manifest_entry_matches_the_bytes_beside_it(system_id):
    """A drifted fixture is a gate that fails for the wrong reason.

    Editing a fixture CSV without re-running `generate_fixtures.py` leaves the
    manifest pinning bytes that are gone, and `make check-fixture` then reports
    a corrupt archive — true, but about the fixture rather than about the
    pipeline, which is the least useful kind of red.
    """
    m = manifest(system_id)
    assert m["sources"], f"{system_id}: no fixture sources pinned"
    for period, entry in sorted(m["sources"].items()):
        path = ARCHIVE / system_id / f"{period}{common.extension_for(entry['content_format'])}"
        assert path.exists(), f"{system_id} {period}: pinned but absent at {path}"
        assert entry["bytes"] == path.stat().st_size, f"{system_id} {period}: size"
        assert entry["sha256"] == sha256(path), (
            f"{system_id} {period}: checksum drifted — re-run "
            "pipeline/tests/fixtures/generate_fixtures.py"
        )
    for name, entry in sorted(m["reference"].items()):
        suffix = ".csv" if name.startswith("weather_") else ".json"
        path = ARCHIVE / system_id / "reference" / f"{name}{suffix}"
        assert path.exists(), f"{system_id} {name}: pinned but absent at {path}"
        assert entry["sha256"] == sha256(path), f"{system_id} {name}: checksum drifted"


@pytest.mark.parametrize("system_id", SYSTEMS)
def test_every_fixture_header_exists_in_the_real_era_map(system_id):
    """The fixtures test the shipped maps, or they test nothing.

    `pipeline/mappings/` has no environment override, deliberately — a run that
    could substitute the era maps could make any archive parse "correctly". So
    a fixture header the real map does not carry would abort extraction, and
    catching that here says which header rather than which stage.
    """
    era_map = json.loads(
        (common.MAPPINGS_DIR / f"{system_id}.json").read_text(encoding="utf-8"))
    trips = {k for k in era_map["trips"] if not k.startswith("_")}
    files = sorted((ARCHIVE / system_id).glob("*.csv"))
    assert files, f"{system_id}: no fixture trip files"
    for path in files:
        with path.open(encoding="utf-8", newline="") as fh:
            header = next(csv.reader(fh))
        unknown = [h for h in header if h.strip() not in trips]
        assert not unknown, f"{path.name}: header(s) the era map omits: {unknown}"


@pytest.mark.parametrize("system_id", SYSTEMS)
def test_every_fixture_membership_label_is_one_the_mapping_carries(system_id):
    """An unmapped label stops publish.py; here it names the label."""
    mapped = set()
    with (common.MAPPINGS_DIR / "membership_groups.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            mapped.add((row["system_id"], row["membership_raw"]))

    era_map = json.loads(
        (common.MAPPINGS_DIR / f"{system_id}.json").read_text(encoding="utf-8"))
    used = set()
    for path in sorted((ARCHIVE / system_id).glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            columns = [c for c in (reader.fieldnames or [])
                       if era_map["trips"].get(c.strip()) == "membership_raw"]
            if not columns:
                continue
            for row in reader:
                for c in columns:
                    if (row[c] or "").strip():
                        used.add(row[c].strip())
    unmapped = sorted(v for v in used if (system_id, v) not in mapped)
    assert not unmapped, (
        f"{system_id}: fixture uses membership label(s) "
        f"{unmapped} that pipeline/mappings/membership_groups.csv does not map"
    )


@pytest.mark.parametrize("system_id", SYSTEMS)
def test_fixture_manifests_say_they_are_synthetic(system_id):
    """A manifest is a provenance claim, and this one has to make the right one.

    `docs/decisions.md` records what a confidently wrong licence costs: the ECCC
    entry named a real instrument, gave a URL and stamped a checked-on date, and
    the combination is what stops anyone looking again. A fixture manifest that
    inherited a plausible licence block would be the same error with none of the
    excuse.
    """
    m = manifest(system_id)
    assert SYNTHETIC in m["data_terms"]
    assert SYNTHETIC in m["licence"]["note"]
    assert m["licence"]["url"] is None
    assert m["source_page"].startswith("synthetic://")
    assert SYNTHETIC in m["weather_station"]["licence"]["note"]
    for entry in m["sources"].values():
        assert entry["url"].startswith("synthetic://"), (
            "a fixture entry pointing at a real URL would let `download.py` "
            "overwrite the fixture with acquired data"
        )


def test_fixture_station_identifiers_cannot_collide_with_real_ones():
    """Every fixture station is named FIXTURE and sits outside the real ranges.

    The names are what make a leak visible: if `FIXTURE Union Fixture Station`
    ever appears in `src/data/generated/stations.json`, a fixture run wrote to
    the real generated directory and the configuration is not what the runbook
    says it is.
    """
    for system_id in SYSTEMS:
        feed = json.loads(
            (ARCHIVE / system_id / "reference" / "gbfs_station_information.json")
            .read_text(encoding="utf-8"))
        stations = feed["data"]["stations"]
        assert len(stations) == 6, f"{system_id}: expected 6 fixture docks"
        for st in stations:
            assert st["name"].startswith("FIXTURE "), st["name"]
            assert int(st["station_id"]) >= 901, (
                f"{system_id} {st['station_id']}: fixture ids must sit clear of "
                "the ranges the real systems publish"
            )
            # The review that forced this clause: fixture Montreal era-A codes
            # 6501-6506 were REAL BIXI docks (Parc Jean-Drapeau among them),
            # while this test looked only at GBFS station_id. Every identifier
            # a fixture publishes — station_id, short_name, and the trip-file
            # keys below — must sit at 9900+ where no system has ever issued.
            short = st.get("short_name")
            if short is not None and str(short).isdigit():
                assert int(short) >= 9900, (
                    f"{system_id} short_name {short}: collides with the range "
                    "real systems issue (BIXI's four-digit codes reach the "
                    "6000s-7000s)"
                )


def test_fixture_trip_file_station_keys_cannot_collide_with_real_ones():
    """The trip files' own station keys, not only the GBFS feed's."""
    import csv as csv_mod
    for path in sorted((ARCHIVE / "mtl-bixi").glob("*.csv")):
        with path.open(encoding="utf-8") as fh:
            rows = list(csv_mod.DictReader(fh))
        for row in rows:
            for col in ("start_station_code", "end_station_code",
                        "emplacement_pk_start", "emplacement_pk_end"):
                v = row.get(col)
                if v is not None and v.isdigit() and len(v) >= 4:
                    assert int(v) >= 9900, (
                        f"{path.name} {col}={v}: a real BIXI code range"
                    )


def test_no_fixture_value_reaches_the_committed_artifacts():
    """The leak signature the fixture README names, asserted rather than
    described: no committed artifact may contain the FIXTURE marker."""
    generated = Path(__file__).resolve().parents[2] / "src" / "data" / "generated"
    for artifact in sorted(generated.glob("*.json")):
        text = artifact.read_text(encoding="utf-8")
        assert "FIXTURE" not in text, (
            f"{artifact.name} contains fixture data — a fixture run wrote to "
            "the real generated directory"
        )
