"""Every file's trips must live inside the period its name declares.

This check would have caught the worst data defect found in this project:
Toronto's 2016.xlsx Q4 sheet, where Excel had transposed day and month on
every date with day <= 12, scattering 80,109 Q4 trips across January-September
and fabricating six months of ridership that never happened. Row counts
reconciled perfectly — the rows all landed, just on the wrong dates — so no
row-accounting gate could see it. Only containment can.

The tolerance exists because it must: files are published in local time or
UTC, and the UTC->local shift legitimately moves a few first-hours rows into
the neighbouring period. 2% is far above any real boundary spill (measured
maximum ~0.4%) and far below any real defect (the 2016 sheet was 37%).
"""

import re
import collections

import pytest

import common

duckdb = pytest.importorskip("duckdb")


@pytest.fixture(scope="module")
def con():
    db = common.DATA_WAREHOUSE / "bikeshare.duckdb"
    if not db.exists():
        pytest.skip(f"warehouse not built at {db}")
    c = duckdb.connect(str(db), read_only=True)
    yield c
    c.close()


@pytest.fixture(scope="module")
def file_months(con):
    rows = con.execute("""
        SELECT source_file, strftime(departure_ts, '%Y-%m') AS mo, count(*) AS n
        FROM clean_trips GROUP BY 1, 2""").fetchall()
    files = collections.defaultdict(collections.Counter)
    for f, mo, n in rows:
        files[str(f)][mo] += n
    return files


def test_monthly_files_contain_their_named_month(file_months):
    checked = 0
    for f, months in file_months.items():
        m = re.search(r"(20\d\d-\d\d)", f.split("/")[-1])
        if not m:
            continue
        checked += 1
        total = sum(months.values())
        outside = sum(n for mo, n in months.items() if mo != m.group(1))
        assert outside / total <= 0.02, (
            f"{f.split('/')[-1]}: {outside:,} of {total:,} trips "
            f"({100 * outside / total:.1f}%) fall outside {m.group(1)} — "
            "dates are landing in the wrong period"
        )
    assert checked > 100, "the sweep found almost no monthly files — wrong glob?"


def test_annual_files_contain_their_named_year(file_months):
    checked = 0
    for f, months in file_months.items():
        fn = f.split("/")[-1]
        if re.search(r"20\d\d-\d\d", fn):
            continue
        m = re.search(r"(20\d\d)", fn)
        if not m:
            continue
        checked += 1
        total = sum(months.values())
        outside = sum(n for mo, n in months.items() if mo[:4] != m.group(1))
        assert outside / total <= 0.02, (
            f"{fn}: {outside:,} of {total:,} trips outside {m.group(1)}"
        )
    assert checked > 20


def test_no_file_carries_the_excel_coercion_signature(con):
    """Serial-typed dates whose decoded days never exceed 12.

    A real month of data reaches day >= 28. A file whose Excel-serial rows
    top out at day 12 is one whose dates were day/month-transposed at source
    — the 2016 Q4 signature. The repaired sheet is exempted by name; anything
    NEW with this shape must stop the suite.
    """
    rows = con.execute("""
        WITH ser AS (
          SELECT source_file,
                 TIMESTAMP '1899-12-30'
                   + to_microseconds(CAST(round(try_cast(departure_raw AS DOUBLE)
                                                * 86400000000) AS BIGINT)) AS ts
          FROM raw_trips
          WHERE try_cast(departure_raw AS DOUBLE) BETWEEN 20000 AND 80000
        )
        SELECT source_file, count(*), max(day(ts))
        FROM ser GROUP BY 1 HAVING count(*) >= 100 AND max(day(ts)) <= 12
    """).fetchall()
    unexpected = [r for r in rows if "tor_trips_2016_Q4" not in str(r[0])]
    assert not unexpected, (
        f"new Excel-coercion signature: {[(str(f).split('/')[-1], n) for f, n, _ in unexpected]}"
    )
