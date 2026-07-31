"""Fail if the warehouse cannot still account for every source record.

Extraction counts the records in every file it reads and refuses to continue
when that differs from what landed (`etl.ReconciliationFailed`). That check
fires once, at extract time, against the bytes that were on disk that morning.
This one is STANDING: it runs in `make check`, it runs against the warehouse as
it is now, and it asks whether the audit is still true of the archive the
manifests currently pin.

The difference matters because the two can drift apart without anyone doing
anything wrong. `download.py --accept-changes` re-pins a source a publisher has
republished; the archive on disk changes; `make check-manifest` passes, because
the archive matches the manifest; `make check-artifacts` passes, because the
artifacts still match a publish run over the unchanged warehouse. Every gate is
green and the row accounting now describes bytes that no longer exist. So the
audit records the checksum it was written from, and this compares it.

What runs by default is cheap — table arithmetic and a set comparison against
the manifests, no file reads at all — with one exception that is the whole
point: **any period whose pinned checksum no longer matches the one the audit
was written from gets its source records recounted**, and the failure says by
how much. That is bounded by how much was re-pinned, which is normally nothing.

    make check-reconciliation           # read-only; part of `make check`
    python pipeline/check_reconciliation.py --recount

`--recount` is the write path and it exists for exactly one situation: a
warehouse extracted before the checksum column existed (a row's sha is NULL,
and re-reading 20 GB on every `make check` is not a gate anyone leaves
switched on). It re-reads the source and stamps ONLY such bootstrap rows, and
only where the recounted records still equal what landed. A row whose sha is
present but no longer matches the pin is REFUSED regardless of count — an
equal record count is not equal content, and a publisher fixing values in
place keeps the count while changing every row. The fix for a moved pin is
to extract the system again, never to overwrite the number that says which
bytes the rows came from.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

import common
import etl

WAREHOUSE = common.DATA_WAREHOUSE / "bikeshare.duckdb"

# Columns that may never be NULL. `source_sha256` is treated separately, since
# a NULL there has its own remedy and its own message.
REQUIRED = ("system_id", "source_period", "source_file", "source_records",
            "rows_landed", "lines_repaired", "kind")


class ReconciliationGateFailure(Exception):
    """The gate could not run at all — a missing table, an unbuilt warehouse."""


def has_column(con, table: str, column: str) -> bool:
    return bool(con.execute(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = ? AND column_name = ?", [table, column]
    ).fetchone()[0])


def audit_rows(con) -> list[tuple]:
    """One tuple per audited file, checksum last.

    A warehouse extracted before spec 029 has no `source_sha256` column at all,
    which is the same condition as a NULL in it and gets the same answer — the
    gate cannot ALTER anything, because it opens the warehouse read-only on
    purpose. `--recount` is the one path that writes.
    """
    sha = "source_sha256" if has_column(con, "raw_file_audit", "source_sha256") else "NULL"
    return con.execute(
        "SELECT system_id, source_period, source_file, source_records, "
        f"rows_landed, lines_repaired, kind, {sha} "
        "FROM raw_file_audit ORDER BY 1, 2, 3"
    ).fetchall()


def require_audit(con) -> None:
    exists = con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_name = 'raw_file_audit'"
    ).fetchone()[0]
    if not exists:
        raise ReconciliationGateFailure(
            "this warehouse has no raw_file_audit table, so nothing records "
            "what each source file contained. Run `python pipeline/etl.py "
            "--stage extract`. An absent audit is not a pass."
        )
    if not con.execute("SELECT count(*) FROM raw_file_audit").fetchone()[0]:
        raise ReconciliationGateFailure(
            "raw_file_audit is empty. An empty audit reconciles trivially and "
            "means nothing; run the extract stage."
        )


def manifests() -> dict[str, dict]:
    """Every manifest, read once. The gate asks about all 241 audit rows and
    `load_manifest` re-parses the file on every call."""
    return {s: common.load_manifest(s).get("sources", {})
            for s in sorted(common.SYSTEMS)}


def expected_periods(system_id: str, sources: dict[str, dict] | None = None) -> dict[str, dict]:
    """Manifest periods this pipeline is supposed to have landed."""
    if sources is None:
        sources = common.load_manifest(system_id).get("sources", {})
    return {p: e for p, e in sources.items()
            if (system_id, p) not in etl.EXCLUDED}


def recount_period(system_id: str, period: str, entry: dict,
                   landed: dict[str, int]) -> dict[str, int]:
    """Re-derive source record counts for one period, file by file.

    Mirrors what extraction does, with one deliberate difference: it counts the
    ORIGINAL files, never the UTF-8-repaired copies. The repair is line for
    line, so the counts are identical, and reading the originals means a gate
    run cannot trigger a 1.6 GB re-repair as a side effect of asking a
    question.
    """
    counts: dict[str, int] = {}
    for path in etl.tabular_files(system_id, period, entry):
        if path.suffix.lower() == ".xlsx":
            names = etl.sheets_in(path)
            units = ([(path, n) for n in names] if len(names) > 1
                     else [(path, None)])
        else:
            units = [(path, None)]
        for file_path, sheet in units:
            label = file_path.name if sheet is None else f"{file_path.name}#{sheet.strip()}"
            n = etl.source_record_count(file_path, sheet)
            if n != landed.get(label) and file_path.suffix.lower() == ".csv":
                n = etl.exact_record_count(file_path)
            counts[label] = n
    return counts


def check(con, verbose: bool = True) -> list[str]:
    """Returns a list of failures. Empty means the gate passes."""
    require_audit(con)
    rows = audit_rows(con)
    pinned_by_system = manifests()
    failures: list[str] = []

    # 1. Internal consistency. Every one of these is a claim the audit makes
    #    about itself, so none of them costs a file read.
    for row in rows:
        system_id, period, label = row[0], row[1], row[2]
        for name, value in zip(REQUIRED, row):
            if value is None:
                failures.append(
                    f"{system_id} {period} {label}: {name} is NULL. Every "
                    "column of the audit is a measurement; a NULL is the "
                    "absence of one wearing the shape of a value."
                )
        if row[3] is not None and row[4] is not None and row[3] != row[4]:
            failures.append(
                f"{system_id} {period} {label}: the source holds {row[3]:,} "
                f"records and {row[4]:,} landed — {row[3] - row[4]:,} "
                "unaccounted for. Extraction aborts on this, so an audit row "
                "carrying it means the row was written by something else, or "
                "edited after the fact."
            )

    # 2. The audit and the manifests must describe the same archive. A period
    #    missing from the audit is a system that was never fully extracted;
    #    one the manifest does not have is a warehouse built from a manifest
    #    that has since changed.
    audited: dict[str, set[str]] = {}
    for row in rows:
        audited.setdefault(row[0], set()).add(row[1])
    for system_id in sorted(common.SYSTEMS):
        want = set(expected_periods(system_id, pinned_by_system.get(system_id, {})))
        got = audited.get(system_id, set())
        if not want and not got:
            # Nothing pinned and nothing landed is consistent. Whether a system
            # SHOULD have pinned sources is `make check-manifest`'s question,
            # and a fixture tree legitimately carries a subset of the three.
            continue
        if not got:
            failures.append(
                f"{system_id}: the manifest pins {len(want)} period(s) and the "
                "audit has no row for any of them. The warehouse does not "
                "contain this system, or it was extracted before the audit "
                "existed. Re-run `etl.py --stage extract`."
            )
            continue
        missing = sorted(want - got)
        if missing:
            failures.append(
                f"{system_id}: {len(missing)} manifest period(s) landed "
                f"nothing and are absent from the audit: {missing[:8]}"
                + (" ..." if len(missing) > 8 else "")
                + ". A pinned period that contributed no rows is a silently "
                "smaller warehouse."
            )
        extra = sorted(got - want)
        if extra:
            failures.append(
                f"{system_id}: {len(extra)} audited period(s) the manifest no "
                f"longer pins: {extra[:8]}" + (" ..." if len(extra) > 8 else "")
                + ". Either the manifest lost an entry or the warehouse holds "
                "rows from a source nothing vouches for."
            )
        for period in sorted(got & want):
            if (system_id, period) in etl.EXCLUDED:
                failures.append(
                    f"{system_id} {period}: audited, but etl.EXCLUDED says it "
                    f"is {etl.EXCLUDED[(system_id, period)]} and must not be "
                    "loaded at all."
                )

    # 3. The standing part. The audit stores the checksum it was written from;
    #    the manifest stores the checksum currently pinned. Where they differ,
    #    recount — the answer is what makes the failure actionable rather than
    #    merely alarming.
    # Keyed by PERIOD, not by file: one manifest entry covers every member of
    # an archive, and BIXI's 2024 unpacks to a dozen. Recounting a period once
    # per member would read the same 2.8 GB twelve times to say one thing.
    stale: dict[tuple[str, str], tuple[str, str]] = {}
    unstamped: list[tuple[str, str]] = []
    for row in rows:
        system_id, period, stored = row[0], row[1], row[7]
        entry = pinned_by_system.get(system_id, {}).get(period)
        if entry is None:
            continue                      # already reported above
        pinned = entry.get("sha256")
        if stored is None:
            unstamped.append((system_id, period))
        elif pinned and stored != pinned:
            stale[(system_id, period)] = (stored, pinned)

    if unstamped:
        systems = sorted({s for s, _ in unstamped})
        failures.append(
            f"{len(unstamped)} audited file(s) across {systems} record no "
            "source checksum, so nothing says which bytes the counts were "
            "taken from. This warehouse predates the column. Run `python "
            "pipeline/check_reconciliation.py --recount` once — it re-reads "
            "the archive, confirms every count against what landed, and "
            "stamps the checksum. Assuming they match is the one thing this "
            "gate exists not to do."
        )

    for (system_id, period), (stored, pinned) in sorted(stale.items()):
        entry = pinned_by_system[system_id][period]
        landed = dict(con.execute(
            "SELECT source_file, rows_landed FROM raw_file_audit "
            "WHERE system_id = ? AND source_period = ?", [system_id, period]
        ).fetchall())
        try:
            fresh = recount_period(system_id, period, entry, landed)
        except FileNotFoundError as exc:
            failures.append(f"{system_id} {period}: re-pinned, and {exc}")
            continue
        moved = {k: (landed.get(k), v) for k, v in fresh.items() if landed.get(k) != v}
        gone = sorted(set(landed) - set(fresh))
        detail = (f"record counts changed for {len(moved)} file(s): "
                  + "; ".join(f"{k} {a} -> {b}" for k, (a, b) in sorted(moved.items())[:5])
                  if moved else "the record counts are unchanged")
        if gone:
            detail += f"; {len(gone)} audited file(s) no longer present: {gone[:5]}"
        failures.append(
            f"{system_id} {period}: the manifest now pins {pinned[:12]}… and "
            f"the audit was written from {stored[:12]}…. The source was "
            f"re-published and re-pinned; {detail}. The warehouse has not been "
            f"re-extracted, so every count for this period describes bytes "
            f"that are gone. Run `etl.py --stage extract --system {system_id}`."
        )

    # 4. The audit and etl_metrics must agree on the total. They are written by
    #    the same run, so disagreement means one of them was regenerated alone.
    landed_metric = con.execute(
        "SELECT value FROM etl_metrics WHERE stage = 'extract' AND metric = 'rows_landed'"
    ).fetchone()
    audit_total = con.execute(
        "SELECT coalesce(sum(rows_landed), 0) FROM raw_file_audit WHERE kind = 'trips'"
    ).fetchone()[0]
    if landed_metric and landed_metric[0] != audit_total:
        failures.append(
            f"the per-file audit accounts for {audit_total:,} landed trip rows "
            f"and etl_metrics.extract.rows_landed says {landed_metric[0]:,}. "
            "One of them is stale."
        )

    if verbose and not failures:
        files, records, landed_rows, systems = con.execute(
            "SELECT count(*), coalesce(sum(source_records), 0), "
            "coalesce(sum(rows_landed), 0), count(DISTINCT system_id) "
            "FROM raw_file_audit WHERE kind = 'trips'"
        ).fetchone()
        print(f"  {files} trip file(s) across {systems} system(s): "
              f"{records:,} source records, {landed_rows:,} landed")
        print("  every audited period matches the checksum its manifest pins")
    return failures


def recount(con, verbose: bool = True) -> list[str]:
    """Re-read the archive, confirm every count, and stamp the checksum.

    Only rows whose checksum is missing or has moved are touched, so the second
    run of this costs nothing. A count that no longer matches what landed is
    reported and NOT written: the audit's job is to say what the extraction
    measured, and quietly replacing that with a fresh measurement would erase
    the only evidence that the warehouse is stale.
    """
    require_audit(con)
    etl.ensure_audit_table(con)      # adds source_sha256 to a pre-029 warehouse
    failures: list[str] = []
    stamped = confirmed = 0
    pinned_by_system = manifests()
    for system_id in sorted(common.SYSTEMS):
        for period, entry in sorted(
                expected_periods(system_id, pinned_by_system[system_id]).items()):
            pinned = entry.get("sha256")
            if not pinned:
                failures.append(
                    f"{system_id} {period}: pinned by nothing — see "
                    "etl.require_sha; download it or remove the entry."
                )
                continue
            rows = con.execute(
                "SELECT source_file, source_records, rows_landed, source_sha256 "
                "FROM raw_file_audit WHERE system_id = ? AND source_period = ?",
                [system_id, period],
            ).fetchall()
            if not rows:
                continue                  # reported by check(), not re-reported
            if all(r[3] == pinned for r in rows):
                confirmed += len(rows)
                continue
            landed = {r[0]: r[2] for r in rows}
            fresh = recount_period(system_id, period, entry, landed)
            for label, was, land, stored in rows:
                if stored == pinned:
                    confirmed += 1
                    continue
                if stored is not None:
                    # The pin MOVED under rows extracted from different bytes.
                    # An equal record count is not equal content — a publisher
                    # fixing values in place keeps the count and changes every
                    # row, which is exactly the republish shape Toronto's
                    # membership defect would take. Stamping here would launder
                    # it: the audit would claim these rows came from the new
                    # pin. Only a re-extract can make that claim true.
                    failures.append(
                        f"{system_id} {period} {label}: the manifest pin moved "
                        f"({stored[:12]}… -> {pinned[:12]}…) after these rows "
                        "were extracted. A matching record count does not make "
                        "the content the same; re-extract this system instead "
                        "of restamping the audit."
                    )
                    continue
                now = fresh.get(label)
                if now is None:
                    failures.append(
                        f"{system_id} {period} {label}: audited, but the "
                        "archive no longer contains a file by that name."
                    )
                elif now != land:
                    failures.append(
                        f"{system_id} {period} {label}: the source on disk now "
                        f"holds {now:,} records against {land:,} landed "
                        f"(the audit recorded {was:,}). The archive and the "
                        "warehouse have diverged; re-extract this system "
                        "rather than restamping the audit."
                    )
                else:
                    # Bootstrap only: a pre-029 audit row that never carried a
                    # sha gains one, having just proven its count in full.
                    con.execute(
                        "UPDATE raw_file_audit SET source_records = ?, "
                        "source_sha256 = ? WHERE system_id = ? AND "
                        "source_period = ? AND source_file = ?",
                        [now, pinned, system_id, period, label],
                    )
                    stamped += 1
                    if verbose:
                        print(f"  {system_id} {period} {label}: {now:,} records, "
                              f"pinned {pinned[:12]}…", flush=True)
    print(f"recount: {stamped} audit row(s) stamped, {confirmed} already current")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=WAREHOUSE)
    ap.add_argument("--recount", action="store_true",
                    help="re-read the archive for periods whose checksum is "
                         "missing or has moved, and stamp it (writes)")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"warehouse missing at {args.db}; nothing to reconcile.\n"
              "Build it with `python pipeline/etl.py --stage all` first.",
              file=sys.stderr)
        return 1

    print(f"check-reconciliation: {args.db}")
    con = duckdb.connect(str(args.db), read_only=not args.recount)
    try:
        failures = recount(con) if args.recount else check(con)
    except ReconciliationGateFailure as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        con.close()

    if failures:
        print(f"\nFAIL: {len(failures)} finding(s)\n", file=sys.stderr)
        for f in failures:
            print(f"  - {f}\n", file=sys.stderr)
        return 1

    print("\nevery source file still reconciles to the rows it landed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
