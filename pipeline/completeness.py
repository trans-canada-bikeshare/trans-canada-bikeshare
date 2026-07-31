"""What is complete enough to publish — declared once, consumed everywhere.

`publish.py` has stated since spec 014 that "incomplete months are excluded
from every series". That sentence was true of the metrics whose author was
thinking about it and false of the rest, because the rule was written five
separate times: a `HAVING` in the incomplete-months query, a Python filter over
monthly rows, a `NOT IN` predicate for the series that cannot filter
afterwards, a second `HAVING` in the seasonality CTE that admitted any month
with more than three observed days, and a fourth copy inside
`forecast.daily_rows`. Four of the five agreed. Nothing checked that they did,
and nothing said what the metrics with no rule at all were doing instead.

This module is the single declaration. Every threshold the publisher admits or
excludes rows by is a named constant here with the reason it is that number,
and `POLICIES` records, for each of the fifteen published artifacts, which rule
governs it and why — **including the artifacts that apply no month rule**, so
"this metric does not exclude incomplete months" is a stated decision with a
reason rather than an omission nobody noticed.

Two things follow from that, and they are the point:

  * A metric's rule can be read without reading its query, so two metrics
    diverging is visible in one file instead of implied across a thousand
    lines of SQL.
  * `scan_thresholds()` reads the publisher's own source and reports every
    numeric literal that gates rows and did not come from here. A rogue
    threshold planted in a query fails `pipeline/tests/test_completeness.py`
    — the 009b discipline, where the gate is watched failing before it is
    trusted.

**Not everything here is a completeness rule.** `station_flows` shows eight
pairs and a station is drawn at a hundred lifetime events; those are
presentation thresholds, not statements about whether a month is whole. They
live here anyway, under `ADMISSION`, because the property the scan needs is
that no number in the publisher decides which rows a reader sees without a
declared reason — and splitting the declaration by which kind of number it is
would put half of them back out of reach of the check.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# The month rule
# ---------------------------------------------------------------------------

# A system-month observed on this many days or fewer is a stub: not a low
# month, a month we do not have. Three is deliberately small. A blanket
# coverage threshold (say, 80% of the month's days) deletes BIXI's real April
# and November, when the system genuinely runs for half the month, and punches
# fake gaps into the middle of Montreal's chart. So the rule catches only what
# no reading can rescue — a handful of days standing in for a month — and the
# trailing-month clause below catches the other case, a month the source has
# simply not finished publishing.
STUB_MONTH_MAX_OBSERVED_DAYS = 3

# ---------------------------------------------------------------------------
# The other admission thresholds
# ---------------------------------------------------------------------------

ADMISSION: dict[str, dict[str, object]] = {
    "EBIKE_MIN_CLASSIFIED_SHARE": {
        "value": 0.5,
        "reason": "A month where 15 of 39,000 trips carry a bike-type field "
                  "cannot state an e-bike share. The classified rows must be "
                  "most of the month or the month is not measured.",
    },
    "MEMBERSHIP_MIN_GROUP_TRIPS": {
        "value": 0,
        "reason": "Structural, any system: a month publishing only one of "
                  "member and casual has stopped publishing the distinction, "
                  "so its share is not the same measurement as its "
                  "neighbours'.",
    },
    "DWELL_MIN_BIKE_ID_COVERAGE": {
        "value": 0.99,
        "reason": "A dwell chain built from a partly-identified year silently "
                  "skips the trips it cannot see, so a bike's 'next departure' "
                  "is whichever later trip happens to carry an id and the "
                  "interval between them is not dwell.",
    },
    "STATION_MIN_LIFETIME_EVENTS": {
        "value": 100,
        "reason": "Presentation, not completeness: the floor at which a dot is "
                  "drawn on the station maps. Published in stations_meta.json "
                  "and rendered, so the page states the threshold its own "
                  "omission count was computed at.",
    },
    "FLOWS_TOP_PAIRS_SHOWN": {
        "value": 8,
        "reason": "Presentation: the OD matrix is 1.2M pairs for Montreal "
                  "alone, so every pair list is a truncation. Eight ship and "
                  "eight render — an earlier version shipped 250 and rendered "
                  "five.",
    },
    "FLOWS_CONCENTRATION_TIERS": {
        "value": (10, 100, 1000),
        "reason": "Reporting only: the top-N tiers whose shares the artifact "
                  "publishes so the truncation above can be read as a number "
                  "rather than trusted. They admit no rows and exclude none.",
    },
    "DURATION_MIN_SECONDS": {
        "value": 1,
        "reason": "Definitional, from the metric registry: a trip of zero or "
                  "negative seconds is not a journey.",
    },
    "DURATION_MAX_SECONDS": {
        "value": 86400,
        "reason": "Definitional, from the metric registry: over 24 hours is a "
                  "bike that was not returned, not a ride.",
    },
    "FORECAST_MIN_REFERENCE_BLOCK_DAYS": {
        "value": 20,
        "reason": "A calendar month whose level is fitted on fewer days than "
                  "this may exist in training — it is real data — but may not "
                  "be the month the page anchors its three-city comparison on, "
                  "because a thin block makes one city's panel answer a "
                  "different question from the other two.",
    },
}

EBIKE_MIN_CLASSIFIED_SHARE: float = ADMISSION["EBIKE_MIN_CLASSIFIED_SHARE"]["value"]
MEMBERSHIP_MIN_GROUP_TRIPS: int = ADMISSION["MEMBERSHIP_MIN_GROUP_TRIPS"]["value"]
DWELL_MIN_BIKE_ID_COVERAGE: float = ADMISSION["DWELL_MIN_BIKE_ID_COVERAGE"]["value"]
STATION_MIN_LIFETIME_EVENTS: int = ADMISSION["STATION_MIN_LIFETIME_EVENTS"]["value"]
FLOWS_TOP_PAIRS_SHOWN: int = ADMISSION["FLOWS_TOP_PAIRS_SHOWN"]["value"]
FLOWS_CONCENTRATION_TIERS: tuple[int, ...] = ADMISSION["FLOWS_CONCENTRATION_TIERS"]["value"]
DURATION_MIN_SECONDS: int = ADMISSION["DURATION_MIN_SECONDS"]["value"]
DURATION_MAX_SECONDS: int = ADMISSION["DURATION_MAX_SECONDS"]["value"]
FORECAST_MIN_REFERENCE_BLOCK_DAYS: int = ADMISSION["FORECAST_MIN_REFERENCE_BLOCK_DAYS"]["value"]

# ---------------------------------------------------------------------------
# The rules, named
# ---------------------------------------------------------------------------

# Bike Share Toronto's member label is corrupted in its published files, and
# the corruption is FILE-SCOPED: it begins at 2021-10, not at the 2018
# vocabulary change publish.py first assumed. Daily member share steps at file
# boundaries and nowhere else:
#
#   2021-09-30  68.2%  ->  2021-10-01  37.8%     hard step down
#   2021-11-30  35.4%  ->  2021-12-01  78.9%     hard recovery
#   2022-06-30  19.2%  ->  2022-07-01  35.5%     hard step
#   ... decaying file by file until the label is absent entirely from 2023-09,
#   while ridership is at its yearly peak.
#
# 2018-2019 are indistinguishable from the clean eras by two independent tests:
# monthly share tracks 2017 within a couple of points across the whole seasonal
# cycle, and the behavioural discriminant (member minus casual commute-hour
# rate) runs 12-20pp in 2016-2019 exactly as it does before and after,
# collapsing only from 2022. An earlier exclusion used the vocabulary change at
# 2018-01 as its boundary and withheld 45 extra months — 10,092,788 trips
# showing no sign of the defect.
#
# From 2021-10 the era is a patchwork (2021-12 alone looks clean inside it), so
# the withheld window is the contiguous span from the first corrupted file to
# the last. Recorded in docs/decisions.md.
#
# LIFT THIS if Toronto ever republishes those months with labels intact.
MEMBERSHIP_UNRELIABLE_LABEL_ERAS: dict[str, list[tuple[str, str]]] = {
    "tor-bikeshare": [("2021-10", "2023-12")],
}

RULES: dict[str, dict[str, object]] = {
    "exclude_incomplete_months": {
        "statement": (
            f"A system-month observed on {STUB_MONTH_MAX_OBSERVED_DAYS} days or "
            "fewer, or a system's trailing month observed on fewer days than "
            "the calendar month holds, is excluded. Both are listed in "
            "incomplete_months.json with their day counts, so the site renders "
            "the gap and says why."
        ),
        "reason": (
            "A month observed on 3 days of 31 is not a low month; it is a "
            "month we do not have. Published as a data point it lied twice: "
            "the trailing partial month made Vancouver's 'latest' read 26 "
            "trips against a 144,105 prior month, and Vancouver's 2022-10 (37 "
            "trips, the download that 500s) rendered as a ridership collapse "
            "under a lede promising that gaps are drawn as gaps."
        ),
    },
    "whole_archive": {
        "statement": (
            "No month rule. The series has no per-month point and no per-month "
            "denominator, so a partial month cannot be read as a low one."
        ),
        "reason": (
            "The month rule exists to stop a fraction of a month being drawn "
            "beside whole ones. Where nothing is drawn per month, applying it "
            "would drop real trips from a total that is meant to be a total — "
            "and would put the archive's own accounting (what was loaded, what "
            "was flagged) out of step with the quality report, which counts "
            "every row."
        ),
    },
    "operating_days_only": {
        "statement": (
            "A per-day denominator counts days the system operated, evidenced "
            "by a linked DEPARTURE that starts on that day. A date carrying "
            "only returns is not a day the system ran."
        ),
        "reason": (
            "Every archive has two edges. Montreal's ends 2026-06-30 and trips "
            "departing on the last days return after it: 21 July dates carry "
            "Montreal returns and no departures, one of them 617 returns "
            "against a 3,000-move norm, and averaging over them diluted "
            "Montreal's implied rebalancing by 3.8%. This is the month rule's "
            "problem one level down — the month rule is keyed on the departure "
            "month, so a month with no departures at all is invisible to it."
        ),
    },
    "whole_calendar_years_only": {
        "statement": (
            "A yearly series marks the years the archive covers 1 January to "
            "31 December, and the page draws only those."
        ),
        "reason": (
            "A year the archive clips cannot be told apart from a year the "
            "system only operated part of. Montreal's 2014 opens in April "
            "because BIXI opens in April; its 2026 stops in June because the "
            "archive does. From inside the data those are identical, so the "
            "chart draws only full years and the page names the ones it "
            "dropped."
        ),
    },
    "withhold_unreliable_label_eras": {
        "statement": (
            "A month inside a system's declared unreliable-label era is "
            "withheld from the membership series and published in "
            "`label_lost` with the basis that removed it. The declared eras "
            "are MEMBERSHIP_UNRELIABLE_LABEL_ERAS. Two structural rules apply "
            "to every system besides: a month publishing only one of member "
            "and casual, and a month where the unlabelled trips outnumber the "
            "labelled ones, are withheld on the same footing."
        ),
        "reason": (
            "Bike Share Toronto's 'Annual Member' decays to nothing inside "
            "2021-10..2023-12 while ridership is at its yearly peak, and the "
            "steps land exactly on file boundaries. Imputing membership from "
            "trip behaviour would be inventing data. Dropping data that cannot "
            "be validated beats keeping data that cannot be checked — and "
            "naming the withheld months in the artifact beats a chart with a "
            "quiet hole in it."
        ),
    },
}

# ---------------------------------------------------------------------------
# One entry per published artifact
# ---------------------------------------------------------------------------
#
# `rule` is the month rule. `extra_rules` names the other rules the artifact
# applies, by their key in RULES; `also` names the numeric admission
# thresholds, by their key in ADMISSION. `reason` says why this metric has that
# month rule — the general reason lives on the rule, the specific one lives
# here.
#
# `whole_archive` is a decision, not an omission, and every one of them was
# MEASURED against the archive of 2026-07-31 before it was written: the three
# incomplete months are Montreal 2022-12 (1 day, 3 trips), Toronto 2016-06 (1
# day, 372 trips) and Vancouver 2026-07 (1 day, 26 trips), and each `reason`
# below states what applying the rule would have moved. 401 trips in 135.6
# million is not an argument for either answer on its own — what decides it is
# whether the artifact has a per-month point that a fraction of a month could
# be misread as.

POLICIES: dict[str, dict[str, object]] = {
    "meta": {
        "metric": None,
        "rule": "whole_archive",
        "reason": "The window and the headline totals are the archive's own "
                  "accounting: first trip, last trip, rows landed, rows "
                  "flagged. Excluding a month here would state a trip total "
                  "the warehouse does not hold and a window the data does not "
                  "have.",
    },
    "incomplete_months": {
        "metric": None,
        "rule": "exclude_incomplete_months",
        "reason": "This artifact IS the rule's output — the months every other "
                  "monthly series drops, with the day counts that dropped "
                  "them, so the site can name them rather than leave a hole.",
    },
    "trips_monthly": {
        "metric": "trips",
        "rule": "exclude_incomplete_months",
        "reason": "One point per month is exactly the shape the rule exists "
                  "for: a stub month draws as a collapse in ridership.",
    },
    "seasonality": {
        "metric": "seasonality",
        "rule": "exclude_incomplete_months",
        "reason": "A mean over months, so a stub is not merely a low point but "
                  "drags the mean of its month-of-year. A one-day stub took "
                  "10% off Montreal's July mean and handed the peak-month "
                  "title to August.",
    },
    "stations_yearly": {
        "metric": "active_stations",
        "rule": "exclude_incomplete_months",
        "reason": "A distinct count per year, taken over the same trips the "
                  "monthly series draws. Counting stations from a month no "
                  "other series admits would let a year's network size rest on "
                  "trips the site says it excluded. This artifact had NO month "
                  "rule until spec 030 and moves no row by gaining one — the "
                  "stations seen in the three stub months are all seen again "
                  "in the same year — so the rule costs nothing and closes a "
                  "divergence nothing was checking.",
    },
    "ebike_share": {
        "metric": "ebike_share",
        "rule": "exclude_incomplete_months",
        "also": ("EBIKE_MIN_CLASSIFIED_SHARE",),
        "reason": "A share per month, so both rules bite: the month must be "
                  "whole, and most of its trips must carry the field the share "
                  "is computed from.",
    },
    "duration": {
        "metric": "duration",
        "rule": "whole_archive",
        "also": ("DURATION_MIN_SECONDS", "DURATION_MAX_SECONDS"),
        "reason": "One distribution per system over the whole archive. A month "
                  "is not a unit of this metric, so there is no per-month "
                  "point to misread, and a stub month's trips have ordinary "
                  "durations — nothing about a one-day month makes the "
                  "seconds it recorded untrustworthy. Measured: applying the "
                  "month rule moves no quartile in any city and only shrinks "
                  "`basis_trips` by 3, 372 and 25 trips. That would make the "
                  "published basis smaller than the population the median was "
                  "actually taken over, which is the one number here a reader "
                  "could check.",
    },
    "stations_meta": {
        "metric": "active_stations",
        "rule": "whole_archive",
        "also": ("STATION_MIN_LIFETIME_EVENTS",),
        "reason": "Counts of stations omitted from the maps, taken from "
                  "dim_station's lifetime totals. The denominator has to be "
                  "the same population the map is drawn from.",
    },
    "stations": {
        "metric": "active_stations",
        "rule": "whole_archive",
        "also": ("STATION_MIN_LIFETIME_EVENTS",),
        "reason": "Lifetime position, lifetime events and lifetime net flow, "
                  "none of them per month. The dot's SIZE comes from "
                  "dim_station's lifetime_events, which is built in "
                  "40_model.sql over every row and cannot be filtered from "
                  "here; filtering only the net flow would widen the "
                  "already-stated gap between what sizes a dot and what "
                  "colours it, for no gain. Measured: 105 stations would move "
                  "their net, 73 of them drawn, every one by 1 to 6 events "
                  "against nets in the thousands.",
    },
    "membership": {
        "metric": "membership_mix",
        "rule": "exclude_incomplete_months",
        "extra_rules": ("withhold_unreliable_label_eras",),
        "also": ("MEMBERSHIP_MIN_GROUP_TRIPS",),
        "reason": "A share per month, and the withheld months are already "
                  "published as `label_lost`. A stub month's share is computed "
                  "on a few days and nothing on the chart would say so.",
    },
    "flows": {
        "metric": "station_flows",
        "rule": "whole_archive",
        "also": ("FLOWS_TOP_PAIRS_SHOWN", "FLOWS_CONCENTRATION_TIERS"),
        "reason": "Pair counts and concentration shares over the whole "
                  "archive, with no month anywhere in the output. Both sides "
                  "of every share come from the same population, which is what "
                  "makes the concentration comparable, and the artifact's own "
                  "`linked_trips` is the denominator a reader divides by. "
                  "Measured: applying the month rule moves no pair in any "
                  "city's top eight and changes the top-10 share of Toronto's "
                  "linked trips in the sixth decimal place.",
    },
    "forecast": {
        "metric": "forecast",
        "rule": "exclude_incomplete_months",
        "also": ("FORECAST_MIN_REFERENCE_BLOCK_DAYS",),
        "reason": "The model fits one level per calendar month, so a month "
                  "represented by three days would carry a level of its own "
                  "estimated from those three days. The exclusions are "
                  "inherited rather than reinvented: a day that is not in "
                  "trips_monthly is not in the model.",
    },
    "rebalancing": {
        "metric": "rebalancing_pressure",
        "rule": "exclude_incomplete_months",
        "extra_rules": ("operating_days_only", "whole_calendar_years_only"),
        "reason": "Per-day means within a year, so a stub month contributes "
                  "days to a denominator the trips series does not count. The "
                  "rule has to be applied in SQL here, not to the output rows: "
                  "a day inside a three-day stub is still a day and would land "
                  "in a yearly mean as if it were a normal one.",
    },
    "dwell": {
        "metric": "bike_dwell",
        "rule": "exclude_incomplete_months",
        "also": ("DWELL_MIN_BIKE_ID_COVERAGE",),
        "reason": "Dwell chains a bike's return to its next departure, so an "
                  "admitted stub month would splice an interval across the gap "
                  "the stub sits in. Applied in SQL, before the chain is "
                  "built.",
    },
    "exclusions": {
        "metric": None,
        "rule": "whole_archive",
        "reason": "Row accounting: how many trips are unterminated and how "
                  "many were matched to a station by name. It must count every "
                  "row in the fact, because the quality report it has to agree "
                  "with does.",
    },
}


class UndeclaredThreshold(Exception):
    """A number in the publisher that gates rows and is not declared here."""


def validate(artifacts: list[str] | None = None) -> None:
    """The declaration must be complete and internally consistent.

    Called at publish time with the artifacts actually built, so an artifact
    that gains a policy nobody wrote — or a policy for an artifact that no
    longer ships — is a refusal rather than a stale paragraph.
    """
    named_rules = set(RULES)
    used_rules: set[str] = set()
    used_thresholds: set[str] = set()

    for name, policy in POLICIES.items():
        rules = (policy["rule"], *policy.get("extra_rules", ()))
        for rule in rules:
            if rule not in named_rules:
                raise UndeclaredThreshold(
                    f"{name} names rule {rule!r}, which is not in RULES")
        used_rules.update(rules)
        if not str(policy.get("reason", "")).strip():
            raise UndeclaredThreshold(f"{name} declares no reason")
        for key in policy.get("also", ()):
            if key not in ADMISSION:
                raise UndeclaredThreshold(
                    f"{name} names admission threshold {key!r}, "
                    "which is not declared")
        used_thresholds.update(policy.get("also", ()))

    for key, entry in ADMISSION.items():
        if not str(entry.get("reason", "")).strip():
            raise UndeclaredThreshold(f"ADMISSION[{key}] declares no reason")
    for rule, entry in RULES.items():
        if not str(entry.get("reason", "")).strip():
            raise UndeclaredThreshold(f"RULES[{rule}] declares no reason")

    # A declaration nothing consumes is a paragraph, not a policy.
    orphan_rules = sorted(named_rules - used_rules)
    if orphan_rules:
        raise UndeclaredThreshold(
            f"rule(s) {orphan_rules} are declared and governed by no artifact")
    orphan_thresholds = sorted(set(ADMISSION) - used_thresholds)
    if orphan_thresholds:
        raise UndeclaredThreshold(
            f"threshold(s) {orphan_thresholds} are declared and applied by no "
            "artifact")

    if artifacts is not None:
        undeclared = sorted(set(artifacts) - set(POLICIES))
        if undeclared:
            raise UndeclaredThreshold(
                f"artifact(s) {undeclared} are published with no completeness "
                "policy. Declare the rule and the reason in "
                "pipeline/completeness.py — including 'whole_archive', which "
                "is an answer and not an absence.")
        unpublished = sorted(set(POLICIES) - set(artifacts))
        if unpublished:
            raise UndeclaredThreshold(
                f"policy declared for artifact(s) {unpublished}, which this "
                "run does not publish")


# ---------------------------------------------------------------------------
# The rule, as SQL and as Python
# ---------------------------------------------------------------------------

def incomplete_month_having(table: str = "fact_trips") -> str:
    """The `HAVING` that defines an incomplete system-month.

    Grouped by system and `trip_month`. Two distinct things look alike here and
    must not be conflated:

        a month we do not HAVE                    -> exclude
        a month the system only OPERATED part of  -> keep, it is real

    BIXI opens mid-April and closed mid-November for most of its history, so
    ~16 observed days in those months is genuine ridership.
    """
    return (
        f"HAVING count(DISTINCT date_key) <= {STUB_MONTH_MAX_OBSERVED_DAYS}\n"
        f"    OR (trip_month = (SELECT max(f2.trip_month) FROM {table} f2\n"
        f"                      WHERE f2.system_id = {table}.system_id)\n"
        f"        AND count(DISTINCT date_key) < day(last_day(trip_month)))"
    )


def incomplete_months_sql(trusted: str, table: str = "fact_trips") -> str:
    """Every incomplete system-month, with the counts that made it one."""
    return f"""
      SELECT system_id, strftime(trip_month, '%Y-%m') AS month,
             count(DISTINCT date_key) AS days_observed,
             day(last_day(trip_month)) AS days_in_month,
             count(*) AS trips
      FROM {table} WHERE {trusted}
      GROUP BY 1, 2, trip_month
      {incomplete_month_having(table)}
      ORDER BY 1, 2
    """


def month_keys(rows: list[dict]) -> list[str]:
    """`system|YYYY-MM` for every row of `incomplete_months_sql`, sorted.

    Sorted because the keys become a bound parameter list, and an unstable
    parameter order is an artifact that does not byte-reproduce.
    """
    return sorted(f"{r['system_id']}|{r['month']}" for r in rows)


def excluded_months_predicate(keys: list[str], alias: str = "") -> str:
    """A SQL predicate dropping the months `incomplete_months` lists.

    For series aggregated by something other than a month, which cannot filter
    afterwards: a day inside a three-day stub is still a day, and it lands in a
    yearly mean as if it were a normal one. Takes a table alias because one
    caller joins `fact_trips` against another relation carrying `system_id`,
    where an unqualified reference is ambiguous rather than merely untidy.
    """
    if not keys:
        return ""
    p = f"{alias}." if alias else ""
    return (
        f" AND ({p}system_id || '|' || strftime({p}trip_month, '%Y-%m')) NOT IN ("
        + ",".join("?" * len(keys)) + ")"
    )


def is_complete(row: dict, keys: set[tuple[str, str]]) -> bool:
    """Whether a row keyed by `system_id` and `month` survives the month rule."""
    return (row["system_id"], row["month"]) not in keys


# ---------------------------------------------------------------------------
# The scan
# ---------------------------------------------------------------------------
#
# What a rogue threshold looks like: a number written into a publisher query
# that decides which rows, months or years a reader sees, without passing
# through this file. The scan reads the source rather than the runtime, because
# the failure it guards against is a query that was never run in a test.
#
# Three checks, named so a caller can say which apply to which file:
#
#   "sql"      every numeric literal in a comparison, a BETWEEN or a modulus
#              inside a SQL string — the three forms a number can gate rows in
#              — including literals written into an f-string's interpolations,
#              so `f"... > {3}"` is not a way round it.
#   "named"    every numeric constant bound directly to a name, since that is
#              how MIN_EVENTS = 100 and BIKE_ID_MIN_COVERAGE = 0.99 lived in
#              publish.py before this file existed.
#   "compare"  every numeric literal compared against in Python.
#
# `publish.py` is scanned by all three: it is the module that decides what
# ships, and after spec 030 it declares no numeric constant of its own.
# `forecast.py` is scanned for SQL only. Its numbers are model arithmetic — an
# earth radius, a squared residual, a percentage — which admit and exclude
# nothing, and requiring them to be declared in a completeness file would teach
# whoever met the failure to add exceptions rather than to think.
#
# Values interpolated from this module are invisible to the scan, which is the
# mechanism: `f"... <= {STUB_MONTH_MAX_OBSERVED_DAYS}"` has no digit in its
# source at all. Numbers that legitimately remain are declared below with the
# reason they are not thresholds.

# Numbers that appear in publisher SQL and admit nothing.
SQL_CONSTANTS: dict[float, str] = {
    0: "exact zero: a remainder, a sign test, or an empty count",
    1: "one: a single event contributed per row of a UNION ALL",
    -1: "minus one: the departure side of a net-flow event",
    3600: "seconds in an hour",
    3600000: "milliseconds in an hour (BIXI 2022+ publishes epoch ms)",
}

# Numbers compared against in the publisher's Python and admitting nothing.
PY_CONSTANTS: dict[float, str] = {
    0: "presence: the boundary between 'any' and 'none', not a threshold",
    1: "one: a single item",
}

# Case-sensitive, and deliberately. Every query in this pipeline writes its
# keywords in capitals, while prose does not — so `re.IGNORECASE` here would
# hand the number scanner a docstring, where "68.2% -> 37.8%" reads as a
# comparison against 37.8. `sql_literals()` exists so a test can check the scan
# still reaches every query the publisher runs rather than trusting that it
# does.
_SQL_MARKERS = re.compile(r"\bSELECT\b[\s\S]*\bFROM\b|\bHAVING\b|\bWHERE\b")
_NUM = r"-?\d+(?:\.\d+)?"
_GATES = re.compile(
    rf"(?:(?:<=|>=|<>|!=|=|<|>)\s*({_NUM}))"          # x <op> 3
    rf"|(?:({_NUM})\s*(?:<=|>=|<>|!=|<|>))"           # 3 <op> x
    rf"|(?:\bBETWEEN\s+({_NUM})\s+AND\s+({_NUM}))"    # BETWEEN 1 AND 86400
    rf"|(?:%\s*({_NUM}))"                             # x % 3600 = 0
)


def _numbers_in_sql(text: str) -> list[float]:
    found: list[float] = []
    for match in _GATES.finditer(text):
        for group in match.groups():
            if group is not None:
                found.append(float(group))
    return found


def _is_sql(text: str) -> bool:
    return bool(_SQL_MARKERS.search(text))


def sql_literals(source: str) -> list[str]:
    """Every string in `source` the scan treats as SQL.

    Exported so the reach of the scan is testable. A scan that quietly failed
    to recognise a query would report nothing about it and look exactly like a
    scan that found nothing wrong.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _is_sql(node.value):
                found.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            text = "".join(p.value for p in node.values
                           if isinstance(p, ast.Constant) and isinstance(p.value, str))
            if _is_sql(text):
                found.append(text)
    return found


def _literal_numbers(node: ast.AST) -> list[float]:
    return [n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool)]


CHECKS = ("sql", "named", "compare")


def scan_thresholds(source: str, *, filename: str = "<source>",
                    checks: tuple[str, ...] = CHECKS) -> list[str]:
    """Findings: one line per undeclared number that gates rows.

    An empty list is the passing answer. Every finding names the line and the
    value, because a scan that says only "something is wrong" is one nobody
    will act on.
    """
    unknown = sorted(set(checks) - set(CHECKS))
    if unknown:
        raise ValueError(f"unknown check(s) {unknown}; known: {list(CHECKS)}")
    tree = ast.parse(source)
    findings: list[str] = []

    def report(line: int, value: float, what: str) -> None:
        findings.append(
            f"{filename}:{line}: {what} {value!r} is not declared in "
            "pipeline/completeness.py"
        )

    for node in ast.walk(tree):
        # SQL held in a plain string.
        if "sql" in checks and isinstance(node, ast.Constant) \
                and isinstance(node.value, str):
            if _is_sql(node.value):
                for value in _numbers_in_sql(node.value):
                    if value not in SQL_CONSTANTS:
                        report(node.lineno, value, "SQL threshold")
        # SQL held in an f-string: the static parts, and any number written
        # into an interpolation.
        elif "sql" in checks and isinstance(node, ast.JoinedStr):
            text = "".join(p.value for p in node.values
                           if isinstance(p, ast.Constant) and isinstance(p.value, str))
            if not _is_sql(text):
                continue
            for value in _numbers_in_sql(text):
                if value not in SQL_CONSTANTS:
                    report(node.lineno, value, "SQL threshold")
            for part in node.values:
                if isinstance(part, ast.FormattedValue):
                    for value in _literal_numbers(part.value):
                        if value not in SQL_CONSTANTS:
                            report(node.lineno, value,
                                   "SQL threshold interpolated from a literal")
        # A threshold given a name in the publisher instead of here. Only a
        # number bound DIRECTLY to a name: `MIN_EVENTS = 100`, not a number
        # somewhere inside a dict literal being assigned, which is rounding,
        # indexing and formatting rather than admission.
        elif "named" in checks and isinstance(node, ast.Assign):
            value = node.value
            if isinstance(value, ast.Constant) and \
                    isinstance(value.value, (int, float)) and \
                    not isinstance(value.value, bool) and \
                    value.value not in PY_CONSTANTS:
                report(node.lineno, value.value, "named constant")
        # A threshold compared against in Python.
        elif "compare" in checks and isinstance(node, ast.Compare):
            for operand in [node.left, *node.comparators]:
                if isinstance(operand, ast.Constant) and \
                        isinstance(operand.value, (int, float)) and \
                        not isinstance(operand.value, bool):
                    if operand.value not in PY_CONSTANTS:
                        report(node.lineno, operand.value, "Python threshold")

    return sorted(set(findings))


def scan_file(path: Path, checks: tuple[str, ...] = CHECKS) -> list[str]:
    return scan_thresholds(path.read_text(encoding="utf-8"),
                           filename=path.name, checks=checks)


# What each publisher module is scanned for, and why it is not the same list.
SCANNED: dict[str, tuple[str, ...]] = {
    "publish.py": CHECKS,
    "forecast.py": ("sql",),
}
