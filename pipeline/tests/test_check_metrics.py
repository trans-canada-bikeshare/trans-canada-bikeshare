"""The metric gate has to FIRE, not merely exist.

`make check-artifacts` once used `git diff --cached` before anything was
staged, so it was silent for every commit it was supposed to guard. A gate
nobody has watched fail is a gate nobody knows works, so every test here plants
a specific violation and asserts the failure names it.
"""

import json

import pytest

import check_metrics


def write(directory, name, payload):
    (directory / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def generated(tmp_path):
    """A minimal artifact set that passes, for tests to then break."""
    write(tmp_path, "trips_monthly", [{"system_id": "van-mobi", "trips": 1}])
    write(tmp_path, "meta", {"systems": [{"system_id": "van-mobi"}]})
    return tmp_path


def test_passes_on_the_real_committed_artifacts():
    # Not a tautology: these are the files the site actually serves.
    assert check_metrics.check(verbose=False) == []


def test_clean_fixture_passes(generated):
    assert check_metrics.check(generated, verbose=False) == []


def test_undeclared_artifact_fails(generated):
    """The spec 021 case: a new per-system artifact nobody declared.

    021 published stations.json and stations_meta.json across all three cities
    and called guard() for neither. A checker that only validated artifacts it
    already knew about would have been equally silent.
    """
    write(generated, "station_flows", [{"system_id": "van-mobi", "flow": 3}])
    failures = check_metrics.check(generated, verbose=False)
    assert len(failures) == 1
    assert "station_flows.json is not declared" in failures[0]
    assert "van-mobi" in failures[0]


def test_undeclared_artifact_fails_even_with_no_system_ids(generated):
    """Silence is not consent. An artifact with no ids today may gain them."""
    write(generated, "mystery", {"note": "no system ids here"})
    failures = check_metrics.check(generated, verbose=False)
    assert len(failures) == 1
    assert "mystery.json is not declared" in failures[0]


def test_unsupported_system_in_a_governed_series_fails(generated):
    """Montreal publishes no bike-type field in any era (spec 001)."""
    write(
        generated,
        "ebike_share",
        {"series": [{"system_id": "mtl-bixi", "share": 0.2}]},
    )
    failures = check_metrics.check(generated, verbose=False)
    assert len(failures) == 1
    assert "ebike_share" in failures[0]
    assert "mtl-bixi" in failures[0]
    # The registry's stated reason has to reach the operator, not just the id.
    assert "reason" in failures[0] or len(failures[0]) > 80


def test_unknown_system_id_fails(generated):
    write(generated, "trips_monthly", [{"system_id": "cal-scooters", "trips": 1}])
    failures = check_metrics.check(generated, verbose=False)
    assert any("unknown system id" in f and "cal-scooters" in f for f in failures)


def test_finds_ids_under_the_compact_key(generated):
    """stations.json keys system as `s` to keep the largest artifact small."""
    write(generated, "stations", {"stations": [{"s": "mtl-bixi", "t": 100}]})
    assert check_metrics.check(generated, verbose=False) == []

    write(generated, "stations", {"stations": [{"s": "nope-transit", "t": 100}]})
    failures = check_metrics.check(generated, verbose=False)
    assert any("nope-transit" in f for f in failures)


def test_nested_series_are_walked(generated):
    """seasonality nests its rows; the walker must not assume a flat shape."""
    write(
        generated,
        "seasonality",
        {"first_year": 2017, "series": [{"system_id": "not-a-system", "m": 1}]},
    )
    failures = check_metrics.check(generated, verbose=False)
    assert any("not-a-system" in f for f in failures)


def test_empty_directory_is_not_a_pass(tmp_path):
    with pytest.raises(check_metrics.MetricGateFailure, match="not a pass"):
        check_metrics.check(tmp_path, verbose=False)


def test_every_exemption_carries_a_reason():
    for name, reason in check_metrics.EXEMPT.items():
        assert len(reason) > 40, f"{name} needs a real reason, not a label"


def test_declared_and_exempt_are_disjoint():
    overlap = set(check_metrics.ARTIFACT_METRIC) & set(check_metrics.EXEMPT)
    assert not overlap, f"{overlap} cannot be both governed and exempt"


def test_every_declared_metric_exists_in_the_registry():
    registry = check_metrics.load_registry()
    for artifact, metric in check_metrics.ARTIFACT_METRIC.items():
        assert metric in registry["metrics"], f"{artifact} -> unknown metric {metric}"
