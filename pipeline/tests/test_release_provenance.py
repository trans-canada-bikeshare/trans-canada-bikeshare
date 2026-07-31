"""The release provenance block, and the refusals that keep it honest.

The block is assembled once per release, at the moment of tagging, which is the
worst possible moment to discover that one of its sources moved. So every
source it reads is asserted here instead, on every test run: the artifacts and
the schemas agree, the lock states one Python and the code agrees with it, the
CI workflow states a Node version, and `meta.json` carries a window per system.

Needs no warehouse and no archive — every input is a committed file.
"""

from __future__ import annotations

import json
import re
import shutil

import pytest

import artifact_schemas
import release_provenance as prov

SHA = "0" * 40


def test_check_mode_runs_green():
    """The `--check` claim in the module docstring, exercised."""
    block = prov.render("v1.0.0", SHA)
    assert block.startswith("## Provenance")
    assert SHA in block


def test_every_published_artifact_is_hashed():
    hashes = prov.artifact_hashes()
    assert {name for name, _, _ in hashes} == {
        f"{n}.json" for n in artifact_schemas.declared()}
    for name, digest, size in hashes:
        assert re.fullmatch(r"[0-9a-f]{64}", digest), name
        assert size > 0, name


def test_toolchain_versions_come_from_the_locks():
    assert prov.python_version() == "3.11"
    assert re.fullmatch(r"\d+\.\d+\.\d+", prov.locked_version("duckdb"))
    assert re.fullmatch(r"\d+(\.\d+)*", prov.node_version())


def test_windows_are_read_from_meta_not_written():
    """The figures in a release note are the artifact's own."""
    meta = json.loads((prov.GENERATED / "meta.json").read_text(encoding="utf-8"))
    systems = prov.data_windows()
    assert len(systems) == len(meta["systems"])
    block = prov.render("v1.0.0", SHA)
    for entry in systems:
        assert f"{int(entry['trips']):,}" in block
        assert entry["first_trip"] in block
        assert entry["last_trip"] in block


def test_a_short_or_junk_commit_is_refused():
    with pytest.raises(prov.ProvenanceUnavailable):
        prov.render("v1.0.0", "not-a-sha")


def test_an_artifact_with_no_schema_refuses_the_block(tmp_path, monkeypatch):
    """A block listing fourteen of fifteen files would be worse than none."""
    generated = tmp_path / "generated"
    shutil.copytree(prov.GENERATED, generated)
    (generated / "surprise.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(prov, "GENERATED", generated)
    with pytest.raises(prov.ProvenanceUnavailable) as exc:
        prov.artifact_hashes()
    assert "surprise" in str(exc.value)


def test_a_lock_that_disagrees_with_the_code_refuses(tmp_path, monkeypatch):
    """Two sources for the interpreter; if they diverge, neither is quoted."""
    lock = tmp_path / "requirements.lock"
    text = prov.LOCK.read_text(encoding="utf-8").replace("-cp311-", "-cp312-")
    lock.write_text(text, encoding="utf-8")
    monkeypatch.setattr(prov, "LOCK", lock)
    with pytest.raises(prov.ProvenanceUnavailable) as exc:
        prov.python_version()
    assert "PYTHON_REQUIRES" in str(exc.value)
