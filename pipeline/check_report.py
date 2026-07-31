"""Fail if the committed data quality report is not what the warehouse says.

`docs/data-quality-report.md` is the project's public row-accounting: how many
rows landed, how many were dropped and why, what each system's window is, how
much of Montreal resolves to a real station. It is generated and committed, and
until now it sat outside every gate — `check_freshness.py` compares published
artifacts and never touches it. So a report generated in April could describe a
warehouse rebuilt in July and `make check` would pass, which is exactly how it
came to publish **0.0%** for Montreal's canonical station share and an encoding
loss the pipeline had stopped taking.

This regenerates the report into a temporary file and diffs it against the
committed copy. The single `Generated <timestamp>` line is excluded, because it
differs between two runs over identical data and says nothing about either.
Everything else in that document is a query result and must match.

Usage: python pipeline/check_report.py [--db PATH] [--report PATH]
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

import duckdb

import common
import quality_report

MAX_DIFF_LINES = 40


def comparable(text: str) -> list[str]:
    return [ln for ln in text.splitlines()
            if not ln.startswith(quality_report.GENERATED_PREFIX)]


def check(db: Path, report: Path) -> list[str]:
    """Empty list on a pass; the diff, as lines, on a failure."""
    if not report.exists():
        return [f"{report} does not exist — run `python pipeline/quality_report.py`"]
    con = duckdb.connect(str(db), read_only=True)
    try:
        fresh = quality_report.build(con)
    finally:
        con.close()
    committed = report.read_text(encoding="utf-8")
    if comparable(committed) == comparable(fresh):
        return []
    return list(difflib.unified_diff(
        comparable(committed), comparable(fresh),
        fromfile=f"{report} (committed)", tofile="fresh from the warehouse",
        lineterm="", n=1,
    ))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path,
                    default=common.DATA_WAREHOUSE / "bikeshare.duckdb")
    ap.add_argument("--report", type=Path, default=quality_report.OUT)
    args = ap.parse_args()

    if not args.db.exists():
        print(f"warehouse missing at {args.db}; cannot verify the quality report.\n"
              "Build it with `python pipeline/etl.py --stage all` first.",
              file=sys.stderr)
        return 1

    try:
        diff = check(args.db, args.report)
    except quality_report.ReportInvariant as exc:
        print(f"the quality report cannot be generated at all: {exc}", file=sys.stderr)
        return 1

    if diff:
        for line in diff[:MAX_DIFF_LINES]:
            print(line, file=sys.stderr)
        if len(diff) > MAX_DIFF_LINES:
            print(f"... {len(diff) - MAX_DIFF_LINES} more diff line(s)", file=sys.stderr)
        print(f"\n{args.report} is stale. Regenerate it with "
              "`python pipeline/quality_report.py`, read the diff, and commit it.",
              file=sys.stderr)
        return 1

    print(f"{args.report.name} matches a fresh generation from the warehouse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
