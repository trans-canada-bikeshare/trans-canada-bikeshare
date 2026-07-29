"""Staged ETL: the acquired archive -> a DuckDB star schema.

  extract  land every file into raw_trips / raw_stations, headers unified by
           the per-system era maps. An unmapped header ABORTS the run.
  clean    type values, parse timestamps, drop the unusable, dedupe
  conform  station identity, canonical month, quality flags
  model    fact_trips + dim_system / dim_station / dim_date / dim_membership

Each stage is re-runnable. Transform logic lives in pipeline/sql/; this module
only orchestrates and records row accounting into etl_metrics.

Usage: python pipeline/etl.py [--stage extract|clean|conform|model|all]
                              [--system SYSTEM] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

import duckdb

import common

SQL_DIR = common.PIPELINE_DIR / "sql"
WAREHOUSE = common.DATA_WAREHOUSE / "bikeshare.duckdb"
STAGES = ("extract", "clean", "conform", "model")
SQL_FILES = {"clean": "20_clean.sql", "conform": "30_conform.sql", "model": "40_model.sql"}

# Sources that exist in the manifest but are deliberately not trip-level.
# Toronto 2014-2015 is a workbook of pre-aggregated OD matrices: no timestamps,
# no per-trip rows. Loading it into fact_trips would mix grains, which is the
# one thing this project's comparability claim cannot survive.
EXCLUDED: dict[tuple[str, str], str] = {
    ("tor-bikeshare", "2014-2015"): "pre-aggregated OD matrices, not trip rows",
}


class UnknownColumns(Exception):
    """A source file has headers the era map does not know about."""


def load_map(system_id: str) -> dict:
    path = common.MAPPINGS_DIR / f"{system_id}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        "trips": {k: v for k, v in raw.get("trips", {}).items() if not k.startswith("_")},
        "stations": {k: v for k, v in raw.get("stations", {}).items() if not k.startswith("_")},
    }


def extracted_dir(system_id: str, period: str) -> Path:
    return common.DATA_RAW / system_id / "_extracted" / period


def tabular_files(system_id: str, period: str, entry: dict) -> list[Path]:
    """Every CSV/XLSX for a period, unpacking archives once and caching them."""
    path = common.local_path(system_id, period, entry.get("content_format"))
    if not path.exists():
        return []
    if path.suffix.lower() in (".csv", ".xlsx"):
        return [path]

    out_dir = extracted_dir(system_id, period)
    if not out_dir.exists():
        tmp = out_dir.with_suffix(".partial")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                name = info.filename
                if name.endswith("/") or name.startswith("__MACOSX"):
                    continue
                if not name.lower().endswith((".csv", ".xlsx")):
                    continue
                dest = tmp / Path(name).name
                with zf.open(info) as src, dest.open("wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
        tmp.replace(out_dir)
    return sorted(p for p in out_dir.iterdir() if p.suffix.lower() in (".csv", ".xlsx"))


def reader_expr(path: Path) -> str:
    quoted = str(path).replace("'", "''")
    if path.suffix.lower() == ".xlsx":
        return f"read_xlsx('{quoted}', all_varchar = true)"
    # ignore_errors keeps a single ragged row from killing a 3 GB file; the
    # count difference is recorded as a drop, never hidden.
    return (
        f"read_csv('{quoted}', header = true, all_varchar = true, "
        "sample_size = -1, ignore_errors = true, null_padding = true)"
    )


def read_header(con, path: Path) -> list[str]:
    rows = con.execute(f"DESCRIBE SELECT * FROM {reader_expr(path)}").fetchall()
    return [r[0] for r in rows]


def plan(header: list[str], column_map: dict, source: str) -> list[tuple[str, str]]:
    """(raw, unified) pairs to load. Raises on any header the map omits."""
    unknown = [h for h in header if h.strip() not in column_map]
    if unknown:
        raise UnknownColumns(
            f"{source}: unmapped header(s) {unknown!r}. Add them to the era map "
            "in pipeline/mappings/ — deliberately, not reflexively."
        )
    pairs = [(h, column_map[h.strip()]) for h in header if column_map[h.strip()]]
    targets = [t for _, t in pairs]
    if len(targets) != len(set(targets)):
        raise UnknownColumns(f"{source}: two headers map to the same column: {targets}")
    return pairs


def classify(header: list[str], maps: dict) -> str | None:
    """Is this file trips, stations, or neither? Decided by header, not name."""
    clean = [h.strip() for h in header]
    if clean and all(h in maps["stations"] for h in clean) and maps["stations"]:
        return "stations"
    if any(h in maps["trips"] for h in clean):
        return "trips"
    return None


def run_extract(con, systems: list[str], limit: int | None) -> None:
    run_sql(con, "10_extract.sql")
    # Reloading a system replaces only that system's rows. Without this, a
    # re-run would double every count instead of refreshing it.
    for system_id in systems:
        con.execute("DELETE FROM raw_trips WHERE system_id = ?", [system_id])
        con.execute("DELETE FROM raw_stations WHERE system_id = ?", [system_id])
    for system_id in systems:
        maps = load_map(system_id)
        manifest = common.load_manifest(system_id)
        loaded = skipped = 0
        for period in sorted(manifest.get("sources", {})):
            entry = manifest["sources"][period]
            if not entry.get("sha256"):
                continue
            if (system_id, period) in EXCLUDED:
                print(f"  {system_id} {period}: excluded — {EXCLUDED[(system_id, period)]}")
                skipped += 1
                continue
            for path in tabular_files(system_id, period, entry):
                header = read_header(con, path)
                kind = classify(header, maps)
                if kind is None:
                    raise UnknownColumns(
                        f"{system_id} {period} {path.name}: header matches neither "
                        f"the trips nor the stations map: {header!r}"
                    )
                pairs = plan(header, maps[kind], f"{system_id} {period} {path.name}")
                cols = ", ".join(f'"{u}"' for _, u in pairs)
                sel = ", ".join(f'"{r}"' for r, _ in pairs)
                table = "raw_trips" if kind == "trips" else "raw_stations"
                con.execute(
                    f"INSERT INTO {table} (system_id, source_period, source_file, {cols}) "
                    f"SELECT ?, ?, ?, {sel} FROM {reader_expr(path)}",
                    [system_id, period, path.name],
                )
                loaded += 1
                print(f"  {system_id} {period} {path.name}: {kind}", flush=True)
            if limit and loaded >= limit:
                break
        print(f"{system_id}: {loaded} file(s) loaded, {skipped} excluded")

    record(con, "extract", "rows_landed", "SELECT count(*) FROM raw_trips")
    record(con, "extract", "files_landed",
           "SELECT count(DISTINCT system_id || source_period || source_file) FROM raw_trips")
    record(con, "extract", "station_rows", "SELECT count(*) FROM raw_stations")
    for system_id in systems:
        record(con, "extract", f"rows_{system_id}",
               f"SELECT count(*) FROM raw_trips WHERE system_id = '{system_id}'")


def run_sql(con, name: str) -> None:
    con.execute((SQL_DIR / name).read_text(encoding="utf-8"))


def run_clean(con) -> None:
    """Clean, then account for every row that did not survive it.

    The funnel must close: landed = kept + dropped-by-reason. If it does not,
    something is being lost silently, which is the failure this project's
    quality report exists to make impossible.
    """
    run_sql(con, "20_clean.sql")
    record(con, "clean", "rows_kept", "SELECT count(*) FROM clean_trips")
    record(
        con, "clean", "rows_dropped_no_departure_time",
        """SELECT count(*) FROM raw_trips
           WHERE coalesce(parse_ts(departure_raw),
                          epoch_ms(try_cast(departure_ms AS BIGINT))) IS NULL""",
    )
    record(
        con, "clean", "rows_dropped_no_departure_station",
        """SELECT count(*) FROM raw_trips
           WHERE coalesce(parse_ts(departure_raw),
                          epoch_ms(try_cast(departure_ms AS BIGINT))) IS NOT NULL
             AND nullif(trim(departure_station_key), '') IS NULL
             AND nullif(trim(departure_station_name), '') IS NULL""",
    )
    # Whatever the two named reasons do not account for is exact-duplicate
    # removal by SELECT DISTINCT. Deriving it keeps the funnel closed by
    # construction rather than by hope.
    con.execute("DELETE FROM etl_metrics WHERE stage='clean' AND metric='rows_dropped_duplicates'")
    con.execute(
        """INSERT INTO etl_metrics
           SELECT 'clean', 'rows_dropped_duplicates',
             (SELECT value FROM etl_metrics WHERE stage='extract' AND metric='rows_landed')
           - (SELECT value FROM etl_metrics WHERE stage='clean' AND metric='rows_kept')
           - (SELECT value FROM etl_metrics WHERE stage='clean' AND metric='rows_dropped_no_departure_time')
           - (SELECT value FROM etl_metrics WHERE stage='clean' AND metric='rows_dropped_no_departure_station')"""
    )
    dupes = con.execute(
        "SELECT value FROM etl_metrics WHERE stage='clean' AND metric='rows_dropped_duplicates'"
    ).fetchone()[0]
    print(f"clean.rows_dropped_duplicates = {dupes:,}")
    if dupes < 0:
        raise SystemExit(
            f"funnel does not close: derived duplicate count is negative ({dupes:,}). "
            "A drop reason is being double-counted."
        )
    record(con, "clean", "rows_unterminated",
           "SELECT count(*) FROM clean_trips WHERE return_ts IS NULL")
    record(con, "clean", "station_rows", "SELECT count(*) FROM clean_stations")


def record(con, stage: str, metric: str, query: str) -> None:
    con.execute("DELETE FROM etl_metrics WHERE stage = ? AND metric = ?", [stage, metric])
    value = con.execute(query).fetchone()[0]
    con.execute("INSERT INTO etl_metrics VALUES (?, ?, ?)", [stage, metric, value])
    print(f"{stage}.{metric} = {value:,}")


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute("INSTALL excel; LOAD excel;")
    # 135M rows on a 16 GB machine: bound memory explicitly and give the spill
    # a home on the data volume. Left to its own devices DuckDB will take ~80%
    # of RAM and then thrash.
    con.execute("SET preserve_insertion_order = false;")
    con.execute("SET memory_limit = '10GB';")
    con.execute("SET threads = 8;")
    (common.DATA_WAREHOUSE / "tmp").mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory = '{common.DATA_WAREHOUSE / 'tmp'}';")
    return con


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES + ("all",), default="all")
    parser.add_argument("--system", choices=sorted(common.SYSTEMS), action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--db", type=Path, default=WAREHOUSE)
    args = parser.parse_args()

    systems = args.system or sorted(common.SYSTEMS)
    con = connect(args.db)
    stages = STAGES if args.stage == "all" else (args.stage,)
    try:
        for stage in stages:
            print(f"\n=== {stage}")
            if stage == "extract":
                run_extract(con, systems, args.limit)
            elif stage == "clean":
                run_clean(con)
            else:
                run_sql(con, SQL_FILES[stage])
    except UnknownColumns as exc:
        print(f"\nABORT: {exc}", file=sys.stderr)
        return 1
    finally:
        con.close()
    print(f"\nwarehouse: {args.db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
