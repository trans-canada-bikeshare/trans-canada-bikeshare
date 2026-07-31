"""JSON Schema contracts for everything the publisher writes.

Until spec 030 the site trusted the shape of `src/data/generated/*.json`
implicitly: fifteen files, hand-typed TypeScript interfaces over them in
`src/lib/data.ts`, and nothing anywhere connecting the two. A publisher change
that renamed a key, dropped one, or turned an integer into a string would pass
every Python test (they assert values, not shapes), pass typecheck (the
interfaces are declarations, not checks against the file), and reach a browser.

Each artifact now has a schema in `pipeline/schemas/<name>.schema.json`, draft
2020-12, and it is enforced from both ends:

  * here, at publish time, before a single byte is written — so a drift is a
    refusal on the machine that produced it, not a silent republish;
  * in `src/schemas.test.ts`, over the COMMITTED files with ajv — so a drift
    that reaches git fails CI on a runner with no warehouse at all.

The schemas are strict on purpose: `additionalProperties: false` everywhere and
every key required unless the publisher genuinely omits it. A loose schema that
accepts anything is a contract nobody can rely on, and the drift it would have
caught is exactly the kind nobody notices — an extra key the site ignores, a
count that became a string, a null where a number used to be.
"""

from __future__ import annotations

import json
from pathlib import Path

import common

SCHEMA_DIR = common.PIPELINE_DIR / "schemas"
SUFFIX = ".schema.json"


class SchemaViolation(Exception):
    """An artifact does not match its published contract."""


def schema_path(name: str) -> Path:
    return SCHEMA_DIR / f"{name}{SUFFIX}"


def declared() -> list[str]:
    """Every artifact name a schema exists for."""
    return sorted(p.name[: -len(SUFFIX)] for p in SCHEMA_DIR.glob(f"*{SUFFIX}"))


def load(name: str) -> dict:
    path = schema_path(name)
    if not path.exists():
        raise SchemaViolation(
            f"no schema for artifact {name!r}. Every published artifact needs "
            f"one at {path}; see pipeline/artifact_schemas.py for why."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema: dict):
    # Imported here rather than at module import so the failure names what is
    # missing and how to fix it, instead of an ImportError from three frames
    # down in whichever gate happened to run first.
    try:
        import jsonschema
    except ModuleNotFoundError as exc:  # pragma: no cover - environment
        raise SchemaViolation(
            "jsonschema is not installed, so no artifact can be validated "
            "against its contract. Install the pinned toolchain: "
            ".venv/bin/pip install --require-hashes -r pipeline/requirements.lock"
        ) from exc
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


def validate(name: str, payload: object) -> None:
    """Raise `SchemaViolation` naming the first place `payload` breaks contract.

    The message carries the JSON path, because "does not match schema" over a
    2,333-element array is not a finding anybody can act on.
    """
    errors = sorted(_validator(load(name)).iter_errors(payload),
                    key=lambda e: list(e.absolute_path))
    if not errors:
        return
    first = errors[0]
    where = "/".join(str(p) for p in first.absolute_path) or "(root)"
    raise SchemaViolation(
        f"{name}.json does not match {schema_path(name).name}: "
        f"at {where}: {first.message}"
        + (f" ({len(errors) - 1} further violation(s))" if len(errors) > 1 else "")
    )


def validate_all(artifacts: dict[str, object]) -> None:
    """Every artifact against its schema, and the set against the schema set.

    An artifact with no schema is a failure, and so is a schema for an artifact
    that is no longer published: a contract nobody checks is worse than none,
    because it reads as a check.
    """
    have, want = set(artifacts), set(declared())
    if have != want:
        missing = sorted(have - want)
        orphan = sorted(want - have)
        raise SchemaViolation(
            "the published artifacts and the schemas disagree"
            + (f"; no schema for {missing}" if missing else "")
            + (f"; schema with no artifact for {orphan}" if orphan else "")
        )
    for name in sorted(artifacts):
        # Through JSON, so what is validated is what will be written: a date
        # object serialised by `default=str` is a string on disk and must be
        # a string here too.
        validate(name, json.loads(json.dumps(artifacts[name], default=str)))
