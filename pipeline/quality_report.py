"""Regenerate docs/data-quality-report.md from the warehouse.

Every row this pipeline drops or flags is accounted for here. The report is
generated, committed, and never hand-edited — if a number in it is wrong, the
fix is upstream, not in the prose.

Nothing in this file states a figure it did not just ask the warehouse for.
That rule is not decoration: this report shipped **0.0%** for Montreal's
canonical station resolution, because the query joined the fact's
already-canonical id against the bridge's era-local one and matched nothing;
and it described an encoding loss the pipeline had already stopped taking, in
prose written before the repair existed and never revised after. A generated
report that carries remembered numbers is worse than no report, because it
reads like evidence.

`make check-report` regenerates this and fails on any difference from the
committed copy, so a stale figure cannot survive a run of `make check`.

Usage: python pipeline/quality_report.py [--db PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import duckdb

import common

OUT = common.REPO_ROOT / "docs" / "data-quality-report.md"

# The one line that legitimately differs between two runs over identical data.
# `check_report.py` drops it before comparing, and nothing else in the document
# may vary — every other line is a query result.
GENERATED_PREFIX = "Generated "

# The drop reasons, in the order the clean stage applies them. Each is counted
# on its own at the stage that makes the drop; see etl.run_clean.
DROP_LABELS = {
    "rows_dropped_no_departure_time": "no parseable departure time",
    "rows_dropped_no_departure_station": "no departure station",
    "rows_dropped_duplicates": "exact duplicate",
}

# A trip whose timestamp survived parsing but landed outside the plausible
# window is flagged, not deleted — and must not set a system's first or last
# date. Toronto's is the whole reason: one 2016 row parsed to a year that
# printed as this system's first trip for as long as the table existed.
IMPLAUSIBLE = "implausible_date"


class ReportInvariant(Exception):
    """The warehouse contradicts something this report is about to publish."""


def table(headers: list[str], rows: list[tuple], align: str | None = None) -> list[str]:
    sep = align or "| " + " | ".join("---" for _ in headers) + " |"
    out = ["| " + " | ".join(headers) + " |", sep]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return out + [""]


def fmt(n) -> str:
    return f"{n:,}" if isinstance(n, (int, float)) and n is not None else str(n)


def pct(n, d, places: int = 3) -> str:
    return f"{100 * n / d:.{places}f}%" if d else "—"


def metrics(con) -> dict[tuple[str, str], int]:
    return dict(((s, m), v) for s, m, v in
                con.execute("SELECT stage, metric, value FROM etl_metrics").fetchall())


def funnel(con) -> tuple[int, int, list[tuple[str, int]], int]:
    """(landed, kept, [(reason, rows)], residual).

    The residual is a CHECK, not an identity. Every term is counted separately
    by the stage that produces it, so they can disagree — and when the
    duplicate count was landed-minus-everything-else, they could not.
    """
    m = metrics(con)
    landed = m.get(("extract", "rows_landed"), 0)
    kept = m.get(("clean", "rows_kept"), 0)
    named = [(r, m.get(("clean", r), 0)) for r in DROP_LABELS]
    return landed, kept, named, landed - kept - sum(n for _, n in named)


def landing_reconciliation(con) -> tuple[int, int, int, int, int]:
    """(trip files, source records, rows landed, files that disagree, unpinned).

    Extraction counts the records in every file it reads and aborts if that
    differs from what landed (`etl.ReconciliationFailed`). This reads back what
    it wrote, so the report can say where the accounting starts instead of
    calling it an open gap.

    The last column is spec 029's: how many of those counts do NOT record the
    checksum they were taken from. A count with no checksum beside it describes
    bytes nobody can identify, which is a weaker claim than this paragraph
    makes — so it is asserted to zero rather than reported.
    """
    sha = "source_sha256" if con.execute(
        "SELECT count(*) FROM information_schema.columns WHERE table_name = "
        "'raw_file_audit' AND column_name = 'source_sha256'").fetchone()[0] else "NULL"
    return con.execute(f"""
        SELECT count(*), coalesce(sum(source_records), 0),
               coalesce(sum(rows_landed), 0),
               count(*) FILTER (source_records <> rows_landed),
               count(*) FILTER ({sha} IS NULL)
        FROM raw_file_audit WHERE kind = 'trips'""").fetchone()


def encoding_repairs(con) -> list[tuple[str, int, int, int]]:
    """(system, trip files, files repaired, lines repaired), per system."""
    return con.execute("""
        SELECT system_id, count(*), count(*) FILTER (lines_repaired > 0),
               coalesce(sum(lines_repaired), 0)
        FROM raw_file_audit WHERE kind = 'trips'
        GROUP BY 1 ORDER BY 1""").fetchall()


def montreal_resolution(con) -> list[tuple[str, int, int]]:
    """(resolution, trips, distinct identities) for Montreal departures.

    THE query this file exists to get right. `fact_trips.departure_station_id`
    has already been through the bridge, so a station the bridge resolved
    carries the canonical id `mtl-bixi:s<gbfs id>`; joining it back to
    `mtl_station_bridge.era_id`, which holds the PRE-bridge key, matches
    nothing at all and published 0.0% for two specs.

    So ask the question directly: is this id one the bridge produces? What is
    left over is not a guess about retired stations — it is era-local identity,
    and it splits cleanly into the two eras that produced it.
    """
    return con.execute("""
        SELECT CASE
                 WHEN departure_station_id IN (SELECT canonical_id FROM mtl_station_bridge)
                   THEN 'canonical'
                 WHEN departure_station_id LIKE '%:name:%' THEN 'era-local name'
                 ELSE 'era-local key' END AS resolution,
               count(*), count(DISTINCT departure_station_id)
        FROM fact_trips WHERE system_id = 'mtl-bixi'
        GROUP BY 1 ORDER BY 2 DESC, 1""").fetchall()


def null_labels(con) -> list[tuple[str, int, int, int, int]]:
    """(system, departures, returns, distinct stations, unresolved) for 'NULL'.

    Toronto publishes the literal four-character string 'NULL' in the station
    NAME column of a large block of trips whose station ids are real. The fact
    keeps the label exactly as published; the report says what it is.
    """
    return con.execute("""
        SELECT system_id,
               count(*) FILTER (upper(trim(departure_label)) = 'NULL'),
               count(*) FILTER (upper(trim(return_label)) = 'NULL'),
               count(DISTINCT CASE WHEN upper(trim(departure_label)) = 'NULL'
                                   THEN departure_station_id END),
               count(*) FILTER (upper(trim(departure_label)) = 'NULL'
                                AND departure_station_id IS NULL)
        FROM fact_trips
        GROUP BY 1
        HAVING count(*) FILTER (upper(trim(departure_label)) = 'NULL') > 0
            OR count(*) FILTER (upper(trim(return_label)) = 'NULL') > 0
        ORDER BY 1""").fetchall()


def assert_invariants(con) -> None:
    """Refuse to publish a report whose own numbers contradict each other."""
    landed, kept, named, residual = funnel(con)
    if residual:
        raise ReportInvariant(
            f"funnel residual is {residual:,}, not zero: {landed:,} landed, "
            f"{kept:,} kept, "
            + ", ".join(f"{n:,} {DROP_LABELS[r]}" for r, n in named)
            + ". Every term is counted independently, so a non-zero residual "
            "means rows left the pipeline under no named reason, or one reason "
            "counted another's rows. Fix the pipeline, not this report."
        )
    files, source_records, audit_landed, disagree, unpinned = landing_reconciliation(con)
    if disagree:
        raise ReportInvariant(
            f"{disagree:,} source file(s) landed a different number of rows than "
            "they contain. Extraction is supposed to abort on that."
        )
    if unpinned:
        raise ReportInvariant(
            f"{unpinned:,} source file(s) have a record count with no checksum "
            "recorded beside it, so nothing says which bytes were counted. The "
            "paragraph this report opens with claims a reconciliation against "
            "the pinned archive; without the checksum it is a reconciliation "
            "against whatever happened to be on disk. Run `python "
            "pipeline/check_reconciliation.py --recount` once."
        )
    if audit_landed != landed:
        raise ReportInvariant(
            f"the per-file audit accounts for {audit_landed:,} landed rows and "
            f"etl_metrics says {landed:,}. One of them is stale — re-run the "
            "extract stage, or `etl.py --backfill-encoding-repairs` if only the "
            "audit's derived columns are missing."
        )
    orphans = con.execute(
        "SELECT count(*) FROM fact_trips WHERE departure_station_id IS NULL"
    ).fetchone()[0]
    if orphans:
        raise ReportInvariant(
            f"{orphans:,} kept trip(s) have no departure station identity. The "
            "clean stage drops a row that cannot say WHERE it started; a kept "
            "row with no departure station means the drop rule and the identity "
            "rule are asking different questions again."
        )
    named_stations = con.execute(
        "SELECT count(*) FROM dim_station WHERE upper(trim(station_name)) = 'NULL'"
    ).fetchone()[0]
    if named_stations:
        raise ReportInvariant(
            f"{named_stations:,} station(s) are named 'NULL'. That is a raw label "
            "reaching a display surface; a station the source did not name is "
            "nameless, which every surface here already handles."
        )


def build(con, now: datetime | None = None) -> str:
    """The whole report. Every figure below comes from a query above it."""
    assert_invariants(con)
    q = lambda sql, p=None: con.execute(sql, p or []).fetchall()
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")

    landed, kept, named, residual = funnel(con)
    files, source_records, _, _, _ = landing_reconciliation(con)

    doc = [
        "# Data Quality Report",
        "",
        "Generated by `pipeline/quality_report.py` from the warehouse. Not "
        "hand-edited — if a figure here is wrong, the fix is upstream.",
        "",
        f"{GENERATED_PREFIX}{stamp}.",
        "",
        "## Row funnel",
        "",
        "Every row that **landed** is either kept or dropped for a named "
        "reason, and the two sum exactly to what landed. Each term is counted "
        "on its own by the stage that produces it, so the residual below is a "
        "check rather than an identity — the generator refuses to write this "
        "file if it is not zero.",
        "",
        f"**Where the accounting starts.** Extraction reads {fmt(files)} trip "
        f"files and counts the records in each one: {fmt(source_records)} "
        "records in the sources, the same number landed, and a file that "
        "disagreed would abort the run rather than be reported here. Rows are "
        "no longer lost to invalid encoding either — they are repaired, and "
        "the counts are below.",
        "",
        "Each of those counts is stored with the sha256 of the manifest entry "
        "it was read from, and `make check-reconciliation` compares that "
        "against the checksum the manifest pins **now**. Without it the "
        "reconciliation would be a statement about one morning: a source its "
        "publisher replaced and `download.py --accept-changes` re-pinned "
        "leaves every other gate green — the archive still matches the "
        "manifest, the artifacts still match a publish run — while the numbers "
        "in this section quietly describe bytes that are gone. Any file whose "
        "pin has moved is re-counted, and this report refuses to generate if a "
        "count has no checksum beside it at all.",
        "",
    ]

    doc += table(
        ["stage", "rows", "share"],
        [("landed", fmt(landed), pct(landed, landed))]
        + [(f"dropped — {DROP_LABELS[r]}", fmt(n), pct(n, landed)) for r, n in named]
        + [("**kept**", f"**{fmt(kept)}**", f"**{pct(kept, landed)}**")],
    )
    doc += [
        f"Funnel residual: **{residual:,}**. Duplicate removal is an actual "
        "count of the rows the dedupe step took out of Vancouver — the only "
        "system deduplicated, for the reason `20_clean.sql` states — not "
        "landed minus everything else. While it was the latter, this residual "
        "was zero by construction and tested nothing.",
        "",
        "### Encoding repairs",
        "",
        "Some Toronto and Vancouver months carry cp1252 bytes in station "
        "names, which DuckDB's CSV reader discards a row at a time and without "
        "complaint. That loss would be station-biased rather than random — a "
        "dock can lose a run of consecutive months and read as though it "
        "closed — so extraction repairs each line instead, UTF-8 strict then "
        "cp1252 then latin-1, and records how many lines it repaired in each "
        "file. The rows land. Nothing in this table is missing data; it is the "
        "measure of how much of the archive needed the repair.",
        "",
    ]
    doc += table(
        ["system", "trip files", "files repaired", "lines repaired"],
        [(s, fmt(f), fmt(r), fmt(n)) for s, f, r, n in encoding_repairs(con)],
    )

    doc += ["## Per system", "",
            "First and last trip exclude rows flagged `" + IMPLAUSIBLE + "` — a "
            "timestamp that parsed but cannot be true is not evidence of when a "
            "system started. The flagged rows are still counted in `trips` and "
            "still listed under quality flags below.", ""]
    doc += table(
        ["system", "trips", "first", "last", "stations", "active", "flagged"],
        [(f"{common.SYSTEMS[s]['city']} — {common.SYSTEMS[s]['system']}",
          fmt(n), str(a), str(b), fmt(st), fmt(act), f"{fmt(fl)} ({pct(fl, n, 2)})")
         for s, n, a, b, st, act, fl in q(f"""
            SELECT f.system_id, count(*),
                   min(f.departure_ts) FILTER (
                     NOT list_contains(f.quality_flags, '{IMPLAUSIBLE}'))::DATE,
                   max(f.departure_ts) FILTER (
                     NOT list_contains(f.quality_flags, '{IMPLAUSIBLE}'))::DATE,
                   count(DISTINCT f.departure_station_id),
                   (SELECT count(*) FROM dim_station d
                     WHERE d.system_id = f.system_id AND d.is_active),
                   sum(CASE WHEN f.has_quality_issue THEN 1 ELSE 0 END)
            FROM fact_trips f GROUP BY 1 ORDER BY 1""")],
    )

    doc += ["## Quality flags", "",
            "Flags mark; they never delete. A flagged trip is still a trip.", ""]
    flags = q("""
      SELECT system_id, flag, count(*) AS n
      FROM (SELECT system_id, unnest(quality_flags) AS flag FROM fact_trips)
      GROUP BY 1, 2 ORDER BY 1, 3 DESC, 2
    """)
    totals = dict(q("SELECT system_id, count(*) FROM fact_trips GROUP BY 1"))
    doc += table(["system", "flag", "trips", "share of system"],
                 [(s, f, fmt(n), pct(n, totals[s], 2)) for s, f, n in flags])

    doc += ["## Station identity", "",
            "A station resolved by name is a weaker claim than one resolved by "
            "a published id. This is how much of each system rests on name "
            "matching.", ""]
    doc += table(
        ["system", "trips by id", "trips by name", "name share"],
        [(s, fmt(t - n), fmt(n), pct(n, t, 2)) for s, t, n in q("""
           SELECT system_id, count(*),
                  count(*) FILTER (list_contains(quality_flags, 'station_matched_by_name'))
           FROM fact_trips GROUP BY 1 ORDER BY 1""")],
    )

    nulls = null_labels(con)
    if nulls:
        doc += ["### The literal label `NULL`", "",
                "Some source files carry the four-character string `NULL` in "
                "the station **name** column beside a real station id. It is a "
                "serialization accident in the export, not a station: the trips "
                "are ordinary trips, and their identity comes from the id, "
                "which resolves normally. The raw label is kept on the fact "
                "exactly as published — this file reports what the source said "
                "— and is treated as absent wherever a label would become a "
                "displayed name, so no station is drawn or listed as \"NULL\".", ""]
        doc += table(
            ["system", "departures labelled NULL", "returns labelled NULL",
             "stations affected", "with no identity"],
            [(s, fmt(d), fmt(r), fmt(st), fmt(u)) for s, d, r, st, u in nulls],
        )
        doc += ["The last column is the one that matters and it is zero. Rows "
                "whose departure station is *only* this token — no id beside it "
                "— have no identity at all, and the clean stage drops them under "
                "\"no departure station\" above rather than keeping a trip that "
                "cannot say where it started.", ""]

    # Tie-broken on the label, like every other ordering here. `pk` and `code`
    # match the same number of entries, so a bare ORDER BY 2 DESC let two runs
    # over one warehouse produce two different documents — which would have
    # made the gate below fire on nothing at all.
    bridge = q("SELECT via, count(*) FROM mtl_station_bridge "
               "GROUP BY 1 ORDER BY 2 DESC, 1")
    if bridge:
        doc += ["## Montreal station bridge", "",
                "BIXI published station identity three incompatible ways — "
                "four-digit codes to 2020, small-integer `emplacement_pk` in "
                "2021, and names only from 2022. These are reconciled through "
                "the GBFS feed, which carries the code and the pk on the same "
                "row. Anything unmatched keeps its era-local identity and is "
                "counted below rather than dropped.", ""]
        doc += table(["matched via", "entries"], [(v, fmt(n)) for v, n in bridge])
        unb = q("""SELECT system_id, count(*) FILTER (station_id LIKE '%:name:%'),
                          count(*) FROM dim_station GROUP BY 1 ORDER BY 1""")
        doc += table(["system", "unbridged identities", "total", "share"],
                     [(s_, fmt(u), fmt(t_), pct(u, t_, 1)) for s_, u, t_ in unb])

        res = montreal_resolution(con)
        total = sum(n for _, n, _ in res)
        by = {k: (n, s) for k, n, s in res}
        canon, canon_st = by.get("canonical", (0, 0))
        name_n, name_st = by.get("era-local name", (0, 0))
        key_n, key_st = by.get("era-local key", (0, 0))
        doc += table(
            ["departure identity", "trips", "share", "distinct identities"],
            [(k, fmt(n), pct(n, total, 1), fmt(s)) for k, n, s in res],
        )
        doc += [
            f"**{pct(canon, total, 1)}** of Montreal trip volume — "
            f"{fmt(canon)} of {fmt(total)} — departs from a station the bridge "
            f"resolved to one of {fmt(canon_st)} canonical docks. The remainder "
            "is era-local identity that nothing reconciled, and it is two "
            f"different things: {fmt(name_n)} trips across {fmt(name_st)} "
            "name-only identities from the 2022+ era, whose published name "
            "matches no station in the pinned GBFS feed by name or by position; "
            f"and {fmt(key_n)} trips across {fmt(key_st)} identities that do "
            "carry a published key, which the feed matches by neither code, id, "
            "name nor position. Those keep their era-local identity and are "
            "counted here rather than dropped or merged on a guess.", "",
            "The figure above is the share of trips whose id **is** a canonical "
            "id. It published 0.0% until this was corrected, because the query "
            "joined that already-canonical id back against the bridge's "
            "pre-bridge key, which matches nothing.", "",
        ]

    doc += ["## Membership labels", "",
            "Raw labels are mapped explicitly. An unmapped label is reported "
            "here rather than silently bucketed.", ""]
    doc += table(["system", "raw label", "group", "trips"],
                 [(s, r, g if g else "**UNMAPPED**", fmt(n)) for s, r, g, n in q("""
                    SELECT f.system_id, f.membership_raw, m.membership_group, count(*)
                    FROM fact_trips f
                    LEFT JOIN dim_membership m
                      ON m.system_id = f.system_id AND m.membership_raw = f.membership_raw
                    WHERE f.membership_raw IS NOT NULL
                    GROUP BY 1, 2, 3 ORDER BY 1, 4 DESC, 2""")])

    if q("SELECT count(*) FROM information_schema.tables "
         "WHERE table_name = 'weather_daily'")[0][0]:
        doc += ["## Weather coverage", "",
                "ECCC daily climate, one airport station per city (spec 013). "
                "A day the record does not cover stays absent or NULL — never "
                "zero-filled, because 0 °C is a legitimate and common value "
                "here and a zero standing in for a gap would be "
                "indistinguishable from an observation.", "",
                "Counted against each system's own trip window, since weather "
                "outside it conditions nothing.", ""]
        doc += table(
            ["system", "station", "window days", "days with a row",
             "no row", "row but no mean temp", "no mean temp (total)"],
            [(s, st, fmt(w), fmt(r), fmt(a), fmt(t), fmt(n))
             for s, st, w, r, a, t, n in q(f"""
                WITH win AS (
                  SELECT system_id, min(departure_ts)::DATE AS f,
                         max(departure_ts)::DATE AS l
                  FROM fact_trips
                  WHERE NOT list_contains(quality_flags, '{IMPLAUSIBLE}')
                  GROUP BY 1),
                cal AS (
                  SELECT w.system_id,
                         unnest(generate_series(w.f, w.l, INTERVAL 1 DAY))::DATE AS d
                  FROM win w)
                SELECT cal.system_id,
                       any_value(s.station_name),
                       count(*),
                       count(wd.date_key),
                       count(*) - count(wd.date_key),
                       -- The date_key guard matters: over a LEFT JOIN a bare
                       -- `temp_mean_c IS NULL` also matches days with no row
                       -- at all, so the two columns could not be added
                       -- without counting the same days twice.
                       count(*) FILTER (wd.date_key IS NOT NULL
                                        AND wd.temp_mean_c IS NULL),
                       count(*) FILTER (wd.temp_mean_c IS NULL)
                FROM cal
                LEFT JOIN weather_daily wd
                  ON wd.system_id = cal.system_id AND wd.date_key = cal.d
                LEFT JOIN weather_station s ON s.system_id = cal.system_id
                GROUP BY 1 ORDER BY 1""")])

    doc += ["## Trips per month", "", "<details><summary>Full series</summary>", ""]
    doc += table(["system", "month", "trips"],
                 [(s, m, fmt(n)) for s, m, n in q("""
                    SELECT system_id, strftime(trip_month, '%Y-%m'), count(*)
                    FROM fact_trips GROUP BY 1, 2 ORDER BY 1, 2""")])
    doc += ["</details>", ""]
    return "\n".join(doc)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=common.DATA_WAREHOUSE / "bikeshare.duckdb")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    try:
        text = build(con)
        landed, kept, named, residual = funnel(con)
    except ReportInvariant as exc:
        print(f"REFUSING to write the report: {exc}")
        return 1
    finally:
        con.close()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"funnel: {landed:,} landed = {kept:,} kept + "
          + " + ".join(f"{n:,} {DROP_LABELS[r]}" for r, n in named)
          + f"; residual {residual:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
