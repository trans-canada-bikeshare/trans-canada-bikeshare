"""The generated data dictionary, and the gate that keeps it honest.

`docs/data-dictionary.md` is generated from the fifteen schema contracts and
from `pipeline/completeness.py`. The value of a generated document is entirely
in the gate: an ungated one drifts from its sources on the first schema change
and then describes an artifact that no longer exists, with the authority of a
file in `docs/`.

So these tests do what spec 028 did for the quality report and 009b did for the
metric gate — they watch the check FAIL first. Every drift case here plants a
real change (a new field, a renamed field, a changed constraint, a changed
completeness reason) and asserts the committed document stops matching.
"""

from __future__ import annotations

import copy
import json
import shutil

import pytest

import artifact_schemas
import completeness
import generate_data_dictionary as gen


def test_committed_dictionary_matches_its_sources():
    """The gate itself: no diff between the committed file and a fresh render."""
    diff = gen.check(gen.OUT)
    assert diff == [], (
        "docs/data-dictionary.md is stale. Regenerate it with "
        "`python pipeline/generate_data_dictionary.py`:\n"
        + "\n".join(diff[:40])
    )


def test_every_artifact_has_a_section_and_a_completeness_rule():
    text = gen.OUT.read_text(encoding="utf-8")
    names = artifact_schemas.declared()
    assert len(names) == len(completeness.POLICIES)
    for name in names:
        assert f"### {name}\n" in text, f"{name} has no section"
        assert f"src/data/generated/{name}.json" in text
        rule = completeness.POLICIES[name]["rule"]
        assert f"**`{rule}`**" in text, f"{name} does not state its month rule"


def test_the_dictionary_carries_no_timestamp():
    """Deliberate: the diff in `make check-dictionary` is total.

    `check_report.py` has to exclude a generated-at line, which is one line of
    that document nothing checks. Nothing here is generated from a clock, so
    nothing here needs excluding.
    """
    text = gen.OUT.read_text(encoding="utf-8")
    assert "Generated 20" not in text
    assert gen.render() == gen.render()


def test_licence_is_pointed_at_not_restated():
    """DATA-LICENSES.md is the authority; a copy of it here could drift."""
    text = gen.OUT.read_text(encoding="utf-8")
    assert "DATA-LICENSES.md" in text
    for obligation in ("Contains information from Mobi",
                       "based on Environment and Climate Change Canada data",
                       "Open Government Licence"):
        assert obligation not in text, (
            f"the dictionary restates a licence obligation ({obligation!r}). "
            "Point at DATA-LICENSES.md instead — a restated obligation is one "
            "that can drift from the instrument it came from."
        )


# ---------------------------------------------------------------------------
# The planted drifts
# ---------------------------------------------------------------------------


@pytest.fixture()
def schema_dir(tmp_path, monkeypatch):
    """A writable copy of the schemas the generator will read instead."""
    target = tmp_path / "schemas"
    shutil.copytree(artifact_schemas.SCHEMA_DIR, target)
    monkeypatch.setattr(artifact_schemas, "SCHEMA_DIR", target)
    return target


def _edit(schema_dir, name, mutate):
    path = schema_dir / f"{name}.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    mutate(schema)
    path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


def test_a_new_field_fails_the_gate(schema_dir):
    def mutate(schema):
        schema["properties"]["new_field_nobody_documented"] = {"type": "string"}
    _edit(schema_dir, "meta", mutate)
    diff = gen.check(gen.OUT)
    assert diff, "a field added to a schema did not fail the dictionary gate"
    assert any("new_field_nobody_documented" in line for line in diff)


def test_a_renamed_field_fails_the_gate(schema_dir):
    def mutate(schema):
        schema["properties"]["windows_note"] = schema["properties"].pop("window_note")
        schema["required"] = ["windows_note" if r == "window_note" else r
                              for r in schema["required"]]
    _edit(schema_dir, "meta", mutate)
    assert gen.check(gen.OUT), "a renamed field did not fail the dictionary gate"


def test_a_loosened_constraint_fails_the_gate(schema_dir):
    """The case a shape-only dictionary would miss: same fields, weaker contract."""
    def mutate(schema):
        schema["properties"]["systems"]["items"]["properties"]["trips"].pop("minimum")
    _edit(schema_dir, "meta", mutate)
    diff = gen.check(gen.OUT)
    assert diff, "a dropped `minimum` did not fail the dictionary gate"
    assert any("systems[].trips" in line for line in diff)


def test_a_changed_completeness_reason_fails_the_gate(monkeypatch):
    """The other source. A policy edited without regenerating is a drift too."""
    policies = copy.deepcopy(completeness.POLICIES)
    policies["trips_monthly"]["reason"] = "because it seemed right at the time"
    monkeypatch.setattr(completeness, "POLICIES", policies)
    assert gen.check(gen.OUT), \
        "a changed completeness reason did not fail the dictionary gate"


def test_an_artifact_without_a_policy_refuses_to_generate(schema_dir):
    """A schema with no completeness policy is a refusal, not a blank cell."""
    shutil.copy(schema_dir / "meta.schema.json",
                schema_dir / "undeclared.schema.json")
    with pytest.raises(gen.DictionaryInvariant) as exc:
        gen.render()
    assert "undeclared" in str(exc.value)
