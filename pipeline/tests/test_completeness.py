"""The completeness declaration has to be the only place a threshold lives.

Spec 030. `publish.py` said "incomplete months are excluded from every series"
and meant it for the metrics whose author was thinking about it: the rule was
written five times, once with a different boundary, and three artifacts applied
no rule at all with nothing saying so.

Two kinds of test here.

The first ask the declaration about itself: every published artifact has a
policy, every policy names a rule that exists, every rule and threshold carries
a reason, and nothing is declared that nothing consumes.

The second plant a rogue threshold in the publisher's real source — the actual
text of `pipeline/publish.py`, mutated in memory — and assert the scan names
it. A scan nobody has watched fail is a scan nobody knows works, which is the
lesson `test_check_metrics.py` was written from: `make check-metrics` printed
"stub" and exited 0 for a fortnight while the registry claimed it was enforced.
"""

import json
from pathlib import Path

import pytest

import common
import completeness

PUBLISH = common.PIPELINE_DIR / "publish.py"
FORECAST = common.PIPELINE_DIR / "forecast.py"


# --- the declaration itself --------------------------------------------------

def test_the_declaration_is_internally_consistent():
    completeness.validate()


def test_every_artifact_the_publisher_writes_has_a_policy():
    """Against the committed artifacts, which is what the site serves."""
    names = sorted(p.stem for p in common.GENERATED_DIR.glob("*.json"))
    if not names:
        pytest.skip("no artifacts published yet")
    completeness.validate(names)


def test_a_new_artifact_with_no_policy_is_refused():
    with pytest.raises(completeness.UndeclaredThreshold) as exc:
        completeness.validate(sorted(set(completeness.POLICIES) | {"hourly_demand"}))
    assert "hourly_demand" in str(exc.value)


def test_a_policy_for_an_artifact_that_no_longer_ships_is_refused():
    remaining = sorted(set(completeness.POLICIES) - {"seasonality"})
    with pytest.raises(completeness.UndeclaredThreshold) as exc:
        completeness.validate(remaining)
    assert "seasonality" in str(exc.value)


def test_every_policy_states_a_reason_in_its_own_words():
    """Not a copy of the rule's general reason: the point of a per-artifact
    entry is why THIS metric answers the way it does."""
    general = {r["reason"] for r in completeness.RULES.values()}
    for name, policy in completeness.POLICIES.items():
        reason = policy["reason"]
        assert len(reason) > 80, name
        assert reason not in general, name


def test_a_rule_nobody_applies_is_refused(monkeypatch):
    rules = dict(completeness.RULES)
    rules["exclude_short_years"] = {"statement": "…", "reason": "…"}
    monkeypatch.setattr(completeness, "RULES", rules)
    with pytest.raises(completeness.UndeclaredThreshold) as exc:
        completeness.validate()
    assert "exclude_short_years" in str(exc.value)


def test_a_threshold_nobody_applies_is_refused(monkeypatch):
    admission = dict(completeness.ADMISSION)
    admission["MIN_DOCKS"] = {"value": 4, "reason": "…"}
    monkeypatch.setattr(completeness, "ADMISSION", admission)
    with pytest.raises(completeness.UndeclaredThreshold) as exc:
        completeness.validate()
    assert "MIN_DOCKS" in str(exc.value)


def test_a_policy_naming_a_rule_that_does_not_exist_is_refused(monkeypatch):
    policies = {k: dict(v) for k, v in completeness.POLICIES.items()}
    policies["trips_monthly"]["rule"] = "exclude_thin_months"
    monkeypatch.setattr(completeness, "POLICIES", policies)
    with pytest.raises(completeness.UndeclaredThreshold) as exc:
        completeness.validate()
    assert "exclude_thin_months" in str(exc.value)


# --- the scan, planted into the publisher's own source -----------------------

def publish_source() -> str:
    return PUBLISH.read_text(encoding="utf-8")


def test_the_publisher_embeds_no_threshold_of_its_own():
    """The passing state, over the real files. If this fails, a number that
    decides what a reader sees was written somewhere other than the
    declaration."""
    for name, checks in completeness.SCANNED.items():
        findings = completeness.scan_file(common.PIPELINE_DIR / name, checks)
        assert findings == [], "\n".join(findings)


@pytest.mark.parametrize("original,planted,label", [
    # The exact divergence spec 030 found: seasonality admitting any month with
    # more than three observed days, in its own HAVING.
    ("GROUP BY 1, 2, 3\n",
     "GROUP BY 1, 2, 3\n        HAVING count(DISTINCT date_key) > 3\n",
     "3"),
    # A coverage threshold nobody declared.
    ("WHERE lat IS NOT NULL",
     "WHERE lat IS NOT NULL AND lifetime_events >= 250",
     "250"),
    # A range filter.
    ("WHERE return_ts IS NOT NULL",
     "WHERE return_ts IS NOT NULL AND duration_s BETWEEN 60 AND 7200",
     "60"),
    # A modulus, which is how a timestamp grid gets quietly redefined.
    ("FROM ev GROUP BY 1, 2",
     "FROM ev WHERE epoch_ms(d) % 900000 = 0 GROUP BY 1, 2",
     "900000"),
])
def test_a_rogue_threshold_in_a_publisher_query_fails(original, planted, label):
    source = publish_source()
    assert original in source, "the anchor this test plants at has moved"
    findings = completeness.scan_thresholds(
        source.replace(original, planted, 1), filename="publish.py")
    assert findings, f"a rogue {label} in a query was not reported"
    assert any(label in f for f in findings), findings


def test_a_rogue_threshold_interpolated_as_a_literal_fails():
    """`f"... rk <= {12}"` writes a threshold into SQL without a digit in the
    static text. The scan reads the interpolation too."""
    source = publish_source().replace(
        "rk <= {TOP_PAIRS}", "rk <= {12}", 1)
    findings = completeness.scan_thresholds(source, filename="publish.py")
    assert any("12" in f for f in findings), findings


def test_a_threshold_given_a_name_in_the_publisher_fails():
    """How MIN_EVENTS = 100 and BIKE_ID_MIN_COVERAGE = 0.99 lived before the
    declaration existed."""
    source = publish_source().replace(
        "    MIN_EVENTS = completeness.STATION_MIN_LIFETIME_EVENTS",
        "    MIN_EVENTS = 100", 1)
    findings = completeness.scan_thresholds(source, filename="publish.py")
    assert any("100" in f for f in findings), findings


def test_a_threshold_compared_against_in_python_fails():
    source = publish_source().replace(
        "        if not (row[\"member\"] > MIN_GROUP",
        "        if not (row[\"member\"] > 25", 1)
    findings = completeness.scan_thresholds(source, filename="publish.py")
    assert any("25" in f for f in findings), findings


def test_the_declared_constants_are_not_a_way_round_the_scan():
    """Zero, one, an hour in seconds and an hour in milliseconds are declared
    as NOT thresholds. Anything else has to be justified in the declaration,
    including a plausible-looking one."""
    assert set(completeness.SQL_CONSTANTS) == {0, 1, -1, 3600, 3600000}
    assert set(completeness.PY_CONSTANTS) == {0, 1}


def test_the_scan_reaches_every_query_the_publisher_runs():
    """A scan that failed to recognise a query would report nothing about it
    and look identical to a scan that found nothing wrong."""
    openers = ('rows(con, f"""', 'rows(con, """',
               'con.execute(f"""', 'con.execute("""')
    for path in (PUBLISH, FORECAST):
        source = path.read_text(encoding="utf-8")
        call_sites = sum(source.count(opener) for opener in openers)
        seen = completeness.sql_literals(source)
        assert call_sites, f"{path.name}: no literal query found to check against"
        assert len(seen) >= call_sites, \
            f"{path.name}: {len(seen)} SQL strings recognised, " \
            f"{call_sites} literal query call sites"


def test_prose_is_not_mistaken_for_a_query():
    """`68.2% -> 37.8%` in a docstring is not a threshold of 37.8, and the
    decisions log is full of arrows exactly like it."""
    prose = '"""Daily member share steps at file boundaries: 68.2% -> 37.8%."""'
    assert completeness.scan_thresholds(prose) == []


def test_the_scan_refuses_a_check_it_does_not_have():
    with pytest.raises(ValueError):
        completeness.scan_thresholds("x = 1", checks=("sql", "spelling"))


# --- the rule is one rule, in one text ---------------------------------------

def test_the_month_rule_is_written_once():
    """Both modules that need it call the same function. A second copy is a
    rule that will diverge — it already had, in forecast.py and in the
    seasonality CTE, for four specs."""
    for path in (PUBLISH, FORECAST):
        text = path.read_text(encoding="utf-8")
        assert "count(DISTINCT date_key) <=" not in text, path.name
        assert "completeness.incomplete_month" in text or \
               "completeness.excluded_months_predicate" in text or \
               "complete_months" in text, path.name


def test_the_rule_sql_names_the_declared_threshold():
    sql = completeness.incomplete_month_having()
    assert f"<= {completeness.STUB_MONTH_MAX_OBSERVED_DAYS}" in sql
    assert "last_day(trip_month)" in sql


def test_the_month_key_list_is_sorted_for_reproducibility():
    rows = [{"system_id": "van-mobi", "month": "2026-07"},
            {"system_id": "mtl-bixi", "month": "2022-12"}]
    assert completeness.month_keys(rows) == [
        "mtl-bixi|2022-12", "van-mobi|2026-07"]


def test_no_excluded_months_means_no_predicate():
    """An empty list must produce an empty predicate, not `NOT IN ()`, which is
    a syntax error the fixture run would hit first — its archive excludes
    nothing."""
    assert completeness.excluded_months_predicate([]) == ""


# --- the shipped bytes obey the declaration ----------------------------------

@pytest.fixture(scope="module")
def artifacts():
    directory = common.GENERATED_DIR
    if not (directory / "incomplete_months.json").exists():
        pytest.skip("no artifacts published yet")
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in directory.glob("*.json")}


def test_no_excluded_month_appears_in_a_series_that_excludes_them(artifacts):
    """The declaration is a claim about the bytes. This is the claim, asked of
    the bytes — with no warehouse, so it holds in a clean clone."""
    excluded = {(r["system_id"], r["month"]) for r in artifacts["incomplete_months"]}
    assert excluded, "the archive has no incomplete month; this test proves nothing"

    def month_rows(payload):
        if isinstance(payload, list):
            rows = payload
        else:
            rows = [r for key in ("series", "partial") for r in payload.get(key, [])]
        return [r for r in rows if isinstance(r, dict) and "month" in r]

    for name, policy in completeness.POLICIES.items():
        if policy["rule"] != "exclude_incomplete_months" or name == "incomplete_months":
            continue
        for row in month_rows(artifacts[name]):
            assert (row["system_id"], row["month"]) not in excluded, \
                f"{name}.json publishes {row['system_id']} {row['month']}, " \
                "which incomplete_months.json says was excluded"


def test_the_thresholds_the_artifacts_publish_are_the_declared_ones(artifacts):
    """Three artifacts render their own threshold on the page. A page stating
    one number while the query used another is the failure MIN_EVENTS was
    already collapsed once to prevent."""
    assert artifacts["stations_meta"]["min_lifetime_events"] == \
        completeness.STATION_MIN_LIFETIME_EVENTS
    assert artifacts["flows"]["top_pairs_shown"] == \
        completeness.FLOWS_TOP_PAIRS_SHOWN
    assert artifacts["dwell"]["min_bike_id_coverage"] == \
        completeness.DWELL_MIN_BIKE_ID_COVERAGE


def test_the_withheld_membership_months_are_the_declared_eras(artifacts):
    eras = completeness.MEMBERSHIP_UNRELIABLE_LABEL_ERAS
    withheld = [r for r in artifacts["membership"]["label_lost"]
                if r["basis"] == "labelling era unreliable"]
    assert withheld
    for row in withheld:
        assert any(lo <= row["month"] <= hi
                   for lo, hi in eras.get(row["system_id"], [])), row
    published = {(r["system_id"], r["month"])
                 for r in artifacts["membership"]["series"]
                 + artifacts["membership"]["partial"]}
    for system, spans in eras.items():
        for lo, hi in spans:
            inside = [m for s, m in published if s == system and lo <= m <= hi]
            assert not inside, f"{system} publishes {inside} inside a withheld era"
