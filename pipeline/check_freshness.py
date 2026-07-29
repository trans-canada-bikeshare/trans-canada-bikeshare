"""Compare committed artifacts against a fresh publish run.

The site serves the files in src/data/generated/, not the warehouse. So a SQL
change that nobody regenerated leaves the site quietly serving numbers no
current code produces — green tests over stale artifacts prove nothing. This is
the gate that catches it, and it returns an exit code rather than an opinion.

Exits non-zero and names every drifted file. Run it before committing
regenerated artifacts and before any release.

Usage: python pipeline/check_freshness.py [--db PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import duckdb

import common
import publish

# Fields that legitimately change on every run and say nothing about whether
# the DATA changed. Compared for presence, not for value.
VOLATILE = {("meta", "generated_at")}


def normalise(name: str, payload: object) -> object:
    if isinstance(payload, dict):
        return {
            k: ("<volatile>" if (name, k) in VOLATILE else normalise(name, v))
            for k, v in payload.items()
        }
    if isinstance(payload, list):
        return [normalise(name, v) for v in payload]
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=common.DATA_WAREHOUSE / "bikeshare.duckdb")
    args = ap.parse_args()

    committed_dir = common.GENERATED_DIR
    if not committed_dir.exists():
        print("no committed artifacts yet — nothing to compare", file=sys.stderr)
        return 0

    if not args.db.exists():
        print(f"warehouse missing at {args.db}; cannot verify freshness.\n"
              "Build it with `python pipeline/etl.py --stage all` first.",
              file=sys.stderr)
        return 1

    registry = publish.load_registry()
    con = duckdb.connect(str(args.db), read_only=True)
    try:
        fresh = publish.build(con, registry)
    except publish.UnsupportedSeries as exc:
        print(f"publish would fail: {exc}", file=sys.stderr)
        return 1
    finally:
        con.close()

    with tempfile.TemporaryDirectory() as tmp:
        publish.write(fresh, Path(tmp))  # exercises the real writer, not a mock

    drifted: list[str] = []
    missing: list[str] = []
    for name, payload in fresh.items():
        path = committed_dir / f"{name}.json"
        if not path.exists():
            missing.append(f"{name}.json")
            continue
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        if normalise(name, on_disk) != normalise(name, json.loads(
                json.dumps(payload, default=str))):
            drifted.append(f"{name}.json")

    extra = sorted(
        p.name for p in committed_dir.glob("*.json")
        if p.stem not in fresh
    )

    for label, items in (("DRIFTED", drifted), ("MISSING", missing), ("ORPHANED", extra)):
        for item in items:
            print(f"{label}: {item}", file=sys.stderr)

    if drifted or missing or extra:
        print(
            f"\n{len(drifted)} drifted, {len(missing)} missing, {len(extra)} orphaned.\n"
            "Regenerate with `python pipeline/publish.py`, review the diff, and "
            "commit it.",
            file=sys.stderr,
        )
        return 1

    print(f"all {len(fresh)} artifacts match a fresh publish run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
