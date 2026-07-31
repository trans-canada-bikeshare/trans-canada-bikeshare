"""Render `docs/data-dictionary.md` from the artifact contracts themselves.

The repository is public and the fifteen files in `src/data/generated/` are the
only thing a reader can actually use: the site renders them, the schemas
constrain them, and nothing until now described them in one place in prose. The
obvious way to fix that is to write the document. The obvious way is wrong —
a hand-written dictionary is a copy of the schemas that starts drifting from
them the first time a field is added, and a stale dictionary is worse than none
because it reads as a description of the current data.

So the dictionary is GENERATED, from three sources and no fourth:

  * `pipeline/schemas/*.schema.json` — the fields, their types and every
    constraint on them, which is where the site's expectations and the
    publisher's output are already written down together (spec 030);
  * `pipeline/completeness.py` — which rule governs what reaches each artifact,
    the reason it is that rule, and the numeric admission thresholds it applies
    (spec 030);
  * `DATA-LICENSES.md` — pointed at, never paraphrased. Restating a licence
    obligation in a generated file is how a wrong one gets published with an
    air of authority, which this project has already done once (2026-07-30).

**No timestamp.** `check_report.py` has to exclude one line from its diff
because the quality report is stamped with its generation time; this document
is derived from files in git and from nothing else, so two runs over the same
tree produce identical bytes and the diff can be total. Every line is checked.

Usage:

    python pipeline/generate_data_dictionary.py            # write the document
    python pipeline/generate_data_dictionary.py --check    # fail if it drifted

`make check-dictionary` runs the second form, and
`pipeline/tests/test_data_dictionary.py` runs it again with a planted schema
change to watch it fail. Standard library only — this must run anywhere the
repository is checked out, including with no warehouse and no archive.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

import artifact_schemas
import common
import completeness

OUT = common.REPO_ROOT / "docs" / "data-dictionary.md"

MAX_DIFF_LINES = 40

# Where the artifacts live, relative to the repository root, and where the
# schemas live. Written once here so the document cannot name a path that moved.
GENERATED_REL = "src/data/generated"
SCHEMA_REL = "pipeline/schemas"


class DictionaryInvariant(Exception):
    """The dictionary cannot be generated from an inconsistent declaration."""


# ---------------------------------------------------------------------------
# Schema -> field rows
# ---------------------------------------------------------------------------
#
# One row per leaf and per container, in document order, with a dotted path.
# `[]` marks an array element and `<pattern>` a key constrained by a pattern
# rather than named — dynamic keys are real here (a system id, a `level_YYYY-MM`
# coefficient) and a dictionary that silently omitted them would describe a
# smaller artifact than the one that ships.


def _type_of(node: dict) -> str:
    if "type" not in node:
        return "any"
    kind = node["type"]
    if isinstance(kind, list):
        return " | ".join(str(k) for k in kind)
    return str(kind)


def _constraints(node: dict, required: bool) -> str:
    """Every constraint the schema states, in a fixed order."""
    parts: list[str] = ["required" if required else "optional"]
    if "enum" in node:
        parts.append("one of " + ", ".join(f"`{v}`" for v in node["enum"]))
    if "const" in node:
        parts.append(f"const `{node['const']}`")
    for key, label in (
        ("minimum", ">="),
        ("exclusiveMinimum", ">"),
        ("maximum", "<="),
        ("exclusiveMaximum", "<"),
    ):
        if key in node:
            parts.append(f"{label} {node[key]}")
    if "minLength" in node:
        parts.append(f"min length {node['minLength']}")
    if "maxLength" in node:
        parts.append(f"max length {node['maxLength']}")
    if "pattern" in node:
        parts.append(f"matches `{node['pattern']}`")
    if "minItems" in node:
        parts.append(f"min items {node['minItems']}")
    if "minProperties" in node:
        parts.append(f"min properties {node['minProperties']}")
    names = node.get("propertyNames")
    if isinstance(names, dict):
        if "enum" in names:
            parts.append("keys: " + ", ".join(f"`{v}`" for v in names["enum"]))
        elif "pattern" in names:
            parts.append(f"keys match `{names['pattern']}`")
    if node.get("additionalProperties") is False and "properties" in node:
        parts.append("no other keys")
    return "; ".join(parts)


def _cell(text: str) -> str:
    """A markdown table cell: single line, pipes escaped."""
    return " ".join(str(text).split()).replace("|", "\\|")


def fields(node: dict, path: str = "", required: bool = True) -> list[tuple[str, str, str, str]]:
    """`(path, type, constraints, description)` for `node` and everything under it.

    The root row is emitted only for a container that has a shape worth stating
    (an array of objects, an object with properties), because "the file is an
    object" is not a field.
    """
    rows: list[tuple[str, str, str, str]] = []
    if path:
        rows.append((path, _type_of(node), _constraints(node, required),
                     node.get("description", "")))

    if "properties" in node:
        req = set(node.get("required", []))
        for name, child in node["properties"].items():
            child_path = f"{path}.{name}" if path else name
            rows.extend(fields(child, child_path, name in req))

    patterned = node.get("patternProperties") or {}
    for pattern, child in patterned.items():
        # One pattern is the case in every schema here, and `<key>` reads
        # better than the regex; the parent row's constraints already say which
        # keys are allowed. More than one and the pattern goes in the path,
        # because two `<key>` branches would be indistinguishable.
        label = "<key>" if len(patterned) == 1 else f"<{pattern}>"
        child_path = f"{path}.{label}" if path else label
        rows.extend(fields(child, child_path, True))

    items = node.get("items")
    if isinstance(items, dict):
        rows.extend(fields(items, f"{path}[]" if path else "[]", True))

    return rows


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------


def _policy(name: str) -> dict:
    try:
        return completeness.POLICIES[name]
    except KeyError as exc:  # pragma: no cover - guarded by validate() below
        raise DictionaryInvariant(
            f"artifact {name!r} has a schema and no completeness policy"
        ) from exc


def _rule_lines(name: str) -> list[str]:
    policy = _policy(name)
    rules = (policy["rule"], *policy.get("extra_rules", ()))
    out: list[str] = []
    for rule in rules:
        out.append(f"- **`{rule}`** — {completeness.RULES[rule]['statement']}")
    for key in policy.get("also", ()):
        entry = completeness.ADMISSION[key]
        out.append(f"- **`{key}` = `{entry['value']}`** — {entry['reason']}")
    out.append(f"- Why this artifact: {policy['reason']}")
    return out


def render() -> str:
    """The whole document, deterministically."""
    names = artifact_schemas.declared()
    if not names:
        raise DictionaryInvariant(
            f"no schemas found under {SCHEMA_REL}; nothing to document")

    declared_policies = set(completeness.POLICIES)
    if set(names) != declared_policies:
        missing = sorted(set(names) - declared_policies)
        orphan = sorted(declared_policies - set(names))
        raise DictionaryInvariant(
            "the schemas and the completeness declaration disagree"
            + (f"; no policy for {missing}" if missing else "")
            + (f"; policy with no schema for {orphan}" if orphan else "")
        )

    schemas = {name: artifact_schemas.load(name) for name in names}

    lines: list[str] = []
    w = lines.append

    w("# Data dictionary")
    w("")
    w("Every field of every artifact this project publishes, with the rule that")
    w("decides which rows reach it.")
    w("")
    w("<!-- GENERATED FILE — do not edit by hand. -->")
    w("")
    w("Generated by `pipeline/generate_data_dictionary.py` from")
    w(f"`{SCHEMA_REL}/*.schema.json` and `pipeline/completeness.py`. It carries no")
    w("timestamp, so two runs over the same tree produce identical bytes and")
    w("`make check-dictionary` can diff it in full — a schema that changes without")
    w("a regenerated dictionary fails the gate, and fails")
    w("`pipeline/tests/test_data_dictionary.py` before that.")
    w("")
    w("```bash")
    w("python pipeline/generate_data_dictionary.py       # regenerate")
    w("make check-dictionary                             # fail if it drifted")
    w("```")
    w("")
    w("## What these files are")
    w("")
    w(f"The site reads `{GENERATED_REL}/` and nothing else — no API, no database,")
    w("no build-time query. They are small aggregates computed from each system's")
    w("published open data by `pipeline/publish.py`, validated against their")
    w("schemas before a byte is written, and byte-compared against a fresh")
    w("publish run by `make check-artifacts`. **Raw trip data is never committed**;")
    w("these aggregates are the whole published output.")
    w("")
    w("## Licence")
    w("")
    w("Code is MIT (`LICENSE`). These artifacts are analysis outputs derived from")
    w("each system's published open data and remain governed by the source terms,")
    w("which are recorded in **[`DATA-LICENSES.md`](../DATA-LICENSES.md)** and in")
    w("each `pipeline/manifests/*.json` entry. That file is the authority; this")
    w("one deliberately does not restate an obligation, because a restated")
    w("obligation is one that can drift from the instrument it came from.")
    w("")
    w("## The artifacts")
    w("")
    w("| Artifact | Metric | Completeness rule | Fields |")
    w("| --- | --- | --- | --- |")
    for name in names:
        policy = _policy(name)
        metric = policy["metric"]
        metric_cell = f"`{metric}`" if metric else "—"
        count = len(fields(schemas[name]))
        w(f"| [`{name}.json`](#{name}) | {metric_cell} | "
          f"`{policy['rule']}` | {count} |")
    w("")
    w("The metric column names the key in `pipeline/mappings/metric_support.json`")
    w("that says which systems the artifact may publish a comparable series for;")
    w("`—` means the artifact is accounting or context rather than a metric.")
    w("`make check-metrics` enforces that column.")
    w("")
    w("## Completeness rules")
    w("")
    w("Declared once in `pipeline/completeness.py`, consumed by every artifact")
    w("below. `whole_archive` is an answer, not an absence.")
    w("")
    for rule in sorted(completeness.RULES):
        entry = completeness.RULES[rule]
        w(f"### `{rule}`")
        w("")
        w(entry["statement"])
        w("")
        w(f"*Why:* {entry['reason']}")
        w("")
    w("## Field reference")
    w("")
    w("Paths are dotted. `[]` is an array element; `<...>` is a key constrained by")
    w("a pattern or an enum rather than named. Constraints are the schema's own —")
    w("if it is not listed here, the contract does not require it.")
    w("")
    for name in names:
        schema = schemas[name]
        w(f"### {name}")
        w("")
        w(f"`{GENERATED_REL}/{name}.json` — contract `{SCHEMA_REL}/{name}.schema.json`")
        w("")
        description = schema.get("description", "").strip()
        if description:
            w(description)
            w("")
        w(f"Top level: `{_type_of(schema)}`.")
        w("")
        w("**Completeness**")
        w("")
        for line in _rule_lines(name):
            w(line)
        w("")
        rows = fields(schema)
        if not rows:
            w("No fields: the contract constrains the top-level value only.")
            w("")
            continue
        w("| Field | Type | Constraints | Description |")
        w("| --- | --- | --- | --- |")
        for path, kind, constraint, note in rows:
            # Every cell goes through `_cell`, including the path and the type:
            # a union type renders as `integer | null` and a pattern key can
            # hold a `|`, and an unescaped pipe silently splits a table column.
            w(f"| `{_cell(path)}` | {_cell(kind)} | {_cell(constraint)} "
              f"| {_cell(note)} |")
        w("")

    return "\n".join(lines).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def check(out: Path) -> list[str]:
    """Empty list on a pass; the diff, as lines, on a failure."""
    fresh = render()
    if not out.exists():
        return [f"{out} does not exist — run "
                "`python pipeline/generate_data_dictionary.py`"]
    committed = out.read_text(encoding="utf-8")
    if committed == fresh:
        return []
    return list(difflib.unified_diff(
        committed.splitlines(), fresh.splitlines(),
        fromfile=f"{out} (committed)", tofile="fresh from the schemas",
        lineterm="", n=1,
    ))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true",
                    help="fail if the committed document is not what the "
                         "schemas and the completeness declaration say")
    args = ap.parse_args()

    try:
        if args.check:
            diff = check(args.out)
            if diff:
                for line in diff[:MAX_DIFF_LINES]:
                    print(line, file=sys.stderr)
                if len(diff) > MAX_DIFF_LINES:
                    print(f"... {len(diff) - MAX_DIFF_LINES} more diff line(s)",
                          file=sys.stderr)
                print(f"\n{args.out} is stale. Regenerate it with "
                      "`python pipeline/generate_data_dictionary.py`, read the "
                      "diff, and commit it.", file=sys.stderr)
                return 1
            print(f"{args.out.name} matches the schemas and the completeness "
                  "declaration")
            return 0

        text = render()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out} "
              f"({len(text.splitlines())} lines, "
              f"{len(artifact_schemas.declared())} artifacts)")
        return 0
    except (DictionaryInvariant, artifact_schemas.SchemaViolation) as exc:
        print(f"the data dictionary cannot be generated: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
