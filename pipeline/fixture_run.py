"""Run the whole pipeline end to end over the synthetic fixture archive.

`make check-fixture`. Extract -> reference -> clean -> conform -> model ->
publish -> quality report, then every gate that can be asked a meaningful
question about a fixture tree, then a set of assertions about what the run
produced. About two and a half seconds on 2,401 rows, no network, and nothing
the real archive can affect.

Three properties this is built to hold, because a fixture gate that quietly
stops holding them is worse than no fixture gate:

**It is offline.** `BIKESHARE_ALLOW_EXTENSION_INSTALL=0` turns a missing DuckDB
extension into a named refusal instead of a download, and the extension
directory is pointed at an empty directory inside the run tree so a cached
`excel` on the developer's machine cannot make the run look offline when it is
not. The fixtures are CSV-only precisely so `excel` is never needed: `icu` is
statically linked into the DuckDB wheel and loads with no network at all.

**It cannot touch the real project.** `BIKESHARE_DATA_ROOT` moves the archive,
the warehouse and the manifests together into the run directory, and
`BIKESHARE_GENERATED_DIR` moves the artifacts. That is the whole configuration
surface, so the guarantee is checkable rather than asserted — and it is checked:
the modification times of `src/data/generated/`, `docs/data-quality-report.md`,
`data-raw/` and `data-warehouse/` are recorded before the run and compared
after.

**It proves reproduction, not just success.** The committed artifacts are the
real ones; this tree has none, so there is nothing to byte-compare against.
Instead the run publishes, then runs `check_freshness.py` over what it just
published — a second build from the same warehouse, compared byte for byte —
and generates the quality report, then runs `check_report.py` over it. Both
gates are the real ones, and both would catch the class of defect spec 029
found in `stations.json`: a sort that is not a total order and returns tied rows
in whatever order the scan produced.

Usage: python pipeline/fixture_run.py [--run-dir PATH] [--keep]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent
FIXTURES = PIPELINE_DIR / "tests" / "fixtures"
DEFAULT_RUN_DIR = REPO_ROOT / ".fixture-run"

# What the fixture archive is supposed to contain. Stated here rather than
# counted from the tree, so a fixture file that disappears fails loudly instead
# of shrinking the thing the gate is checking.
EXPECT_TRIP_FILES = 16          # 12 Vancouver months + 2 Montreal eras + 2 Toronto
EXPECT_SYSTEMS = ("mtl-bixi", "tor-bikeshare", "van-mobi")
# Six docks per city. Written as a number rather than imported from the
# generator, because importing it would let a change there silently redefine
# what this asserts.
EXPECT_STATIONS = 6

# Every artifact publish.py emits. Counted, so an artifact that stops being
# written — or a new one nobody declared — is a failure here rather than a
# quieter site.
EXPECT_ARTIFACTS = 15

# `incomplete_months` is a list of what was EXCLUDED, and the fixture excludes
# nothing: every month of 2024 is observed on every one of its days, which the
# forecast's reference year requires. An empty list is the right answer and the
# only artifact for which it is.
EMPTY_IS_THE_ANSWER = {"incomplete_months"}

# Every drop reason the clean stage names. The fixture plants one of each, and
# a zero here means the fixture stopped exercising a branch of the funnel — the
# funnel would still close, and would be proving less than it looks like.
DROP_REASONS = (
    "rows_dropped_no_departure_time",
    "rows_dropped_no_departure_station",
    "rows_dropped_duplicates",
)

# Paths outside the run directory that this must not write. The point is not
# that the code is careful; it is that the configuration is complete, and this
# is how that claim is tested rather than believed.
GUARDED = (
    REPO_ROOT / "src" / "data" / "generated",
    REPO_ROOT / "docs" / "data-quality-report.md",
    REPO_ROOT / "data-raw",
    REPO_ROOT / "data-warehouse",
)


def snapshot(paths) -> dict[str, tuple[float, int]]:
    """(mtime, size) for every file under each path that exists."""
    out: dict[str, tuple[float, int]] = {}
    for root in paths:
        if not root.exists():
            continue
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        for p in files:
            if p.is_file():
                st = p.stat()
                out[str(p)] = (st.st_mtime, st.st_size)
    return out


def prepare(run_dir: Path) -> dict[str, str]:
    """A clean run tree, and the environment every step inherits."""
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    shutil.copytree(FIXTURES / "archive", run_dir / "data-raw")
    shutil.copytree(FIXTURES / "manifests", run_dir / "manifests")
    (run_dir / "duckdb-extensions").mkdir()

    env = dict(os.environ)
    env.update({
        # Moves data-raw, data-warehouse AND manifests together. Pointing two of
        # them at the fixture tree and one at the real one would leave every
        # checksum comparison meaningless while continuing to pass.
        "BIKESHARE_DATA_ROOT": str(run_dir),
        "BIKESHARE_GENERATED_DIR": str(run_dir / "generated"),
        # A CI runner is not a 16 GB workstation, and this is the run that
        # proves the limits are configurable rather than merely documented.
        "BIKESHARE_DUCKDB_MEMORY_LIMIT": "1GB",
        "BIKESHARE_DUCKDB_THREADS": "2",
        "BIKESHARE_ALLOW_EXTENSION_INSTALL": "0",
        "BIKESHARE_DUCKDB_EXTENSION_DIR": str(run_dir / "duckdb-extensions"),
    })
    return env


def step(label: str, args: list[str], env: dict[str, str]) -> float:
    print(f"\n=== {label}", flush=True)
    started = time.monotonic()
    result = subprocess.run([sys.executable, *args], env=env, cwd=REPO_ROOT)
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        raise SystemExit(f"\ncheck-fixture FAILED at: {label}")
    print(f"--- {label}: {elapsed:.1f}s", flush=True)
    return elapsed


def assertions(run_dir: Path) -> None:
    """What the run has to be true of, asked of the warehouse it just built."""
    import duckdb

    db = run_dir / "data-warehouse" / "bikeshare.duckdb"
    con = duckdb.connect(str(db), read_only=True)
    try:
        metrics = dict(((s, m), v) for s, m, v in con.execute(
            "SELECT stage, metric, value FROM etl_metrics").fetchall())
        landed = metrics.get(("extract", "rows_landed"), 0)
        kept = metrics.get(("clean", "rows_kept"), 0)
        named = [(r, metrics.get(("clean", r), 0)) for r in DROP_REASONS]

        residual = landed - kept - sum(n for _, n in named)
        if residual:
            raise SystemExit(
                f"funnel does not close: {landed:,} landed, {kept:,} kept, "
                f"residual {residual:,}")
        empty = [r for r, n in named if n == 0]
        if empty:
            raise SystemExit(
                f"the fixture no longer exercises {empty}. Every named drop "
                "reason must be non-zero here or the funnel closes over a "
                "branch nothing tested — see pipeline/tests/fixtures/README.md."
            )
        print(f"funnel closes: {landed:,} landed = {kept:,} kept + "
              + " + ".join(f"{n:,} {r.removeprefix('rows_dropped_')}"
                           for r, n in named))

        files, mismatched = con.execute(
            "SELECT count(*), count(*) FILTER (source_records <> rows_landed) "
            "FROM raw_file_audit WHERE kind = 'trips'").fetchone()
        if files != EXPECT_TRIP_FILES:
            raise SystemExit(
                f"{files} trip file(s) audited, expected {EXPECT_TRIP_FILES}. "
                "A fixture file was added or lost.")
        if mismatched:
            raise SystemExit(f"{mismatched} file(s) landed a different count "
                             "than the source holds")

        systems = tuple(r[0] for r in con.execute(
            "SELECT DISTINCT system_id FROM fact_trips ORDER BY 1").fetchall())
        if systems != EXPECT_SYSTEMS:
            raise SystemExit(f"fact_trips carries {systems}, expected "
                             f"{EXPECT_SYSTEMS}")

        # Montreal's two eras name the same six docks two incompatible ways —
        # four-digit codes in era A, the station name in era D. If the bridge
        # stopped resolving them this would be twelve, and every Montreal
        # station count on the site would double without any gate noticing.
        mtl = con.execute(
            "SELECT count(*) FROM dim_station WHERE system_id = 'mtl-bixi'"
        ).fetchone()[0]
        if mtl != EXPECT_STATIONS:
            raise SystemExit(
                f"Montreal resolves to {mtl} stations, expected "
                f"{EXPECT_STATIONS}: the era bridge in 35_bridge.sql is not "
                "joining the code era to the name era.")
        print(f"station identity: Montreal's two eras resolve to {mtl} docks")
    finally:
        con.close()

    generated = run_dir / "generated"
    artifacts = sorted(generated.glob("*.json"))
    if len(artifacts) != EXPECT_ARTIFACTS:
        raise SystemExit(
            f"{len(artifacts)} artifact(s) published to {generated}, expected "
            f"{EXPECT_ARTIFACTS}: {[p.name for p in artifacts]}")
    for path in artifacts:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload in ({}, [], None) and path.stem not in EMPTY_IS_THE_ANSWER:
            raise SystemExit(f"{path.name} published empty")
    print(f"artifacts: {len(artifacts)} file(s) parse as JSON and carry data")

    forecast = json.loads((generated / "forecast.json").read_text(encoding="utf-8"))
    got = sorted(m["system_id"] for m in forecast["models"])
    if tuple(got) != EXPECT_SYSTEMS:
        raise SystemExit(f"forecast fitted {got}, expected {list(EXPECT_SYSTEMS)}")
    print(f"forecast: one model per system, reference year "
          f"{forecast['reference_year']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR,
                    help=f"scratch tree for the run (default {DEFAULT_RUN_DIR})")
    ap.add_argument("--keep", action="store_true",
                    help="leave the run tree in place for inspection")
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    print(f"check-fixture: {FIXTURES.relative_to(REPO_ROOT)} -> {run_dir}")
    before = snapshot(GUARDED)
    env = prepare(run_dir)
    started = time.monotonic()

    report = run_dir / "data-quality-report.md"
    step("check-manifest (fixture archive)",
         ["pipeline/inventory.py"], env)
    step("etl --stage all",
         ["pipeline/etl.py", "--stage", "all"], env)
    step("publish", ["pipeline/publish.py"], env)
    step("quality report",
         ["pipeline/quality_report.py", "--out", str(report)], env)
    step("check-metrics", ["pipeline/check_metrics.py"], env)
    step("check-artifacts (republish, byte-compare)",
         ["pipeline/check_freshness.py"], env)
    step("check-report (regenerate, diff)",
         ["pipeline/check_report.py", "--report", str(report)], env)
    step("check-reconciliation", ["pipeline/check_reconciliation.py"], env)

    print("\n=== assertions")
    assertions(run_dir)

    after = snapshot(GUARDED)
    if before != after:
        changed = sorted(set(before) ^ set(after)) or sorted(
            k for k in before if before[k] != after.get(k))
        raise SystemExit(
            "the fixture run modified files outside its run directory:\n  "
            + "\n  ".join(changed[:10])
            + "\nThat is a configuration leak: some path is not going through "
              "common's environment overrides.")
    guarded = ", ".join(str(p.relative_to(REPO_ROOT)) for p in GUARDED)
    print(f"untouched: {len(before)} file(s) under {guarded}")

    elapsed = time.monotonic() - started
    if not args.keep:
        shutil.rmtree(run_dir, ignore_errors=True)
    print(f"\ncheck-fixture PASSED in {elapsed:.1f}s"
          + ("" if args.keep else " (run tree removed; --keep to inspect)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
