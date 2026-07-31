"""Publish-time schema validation has to refuse, not merely exist.

Spec 030. The site's TypeScript interfaces over `src/data/generated/*.json`
were declarations, not checks: a renamed key, a dropped one or an integer that
became a string would pass pytest (which asserts values), pass typecheck (the
interface simply asserted itself) and reach a browser.

`src/schemas.test.ts` asks the same question of the committed bytes with ajv.
This file asks it of the publisher, where the refusal has to happen before
anything is written — half a directory of fresh files beside half a directory
of stale ones is a state no gate here can describe.
"""

import copy
import json

import pytest

import artifact_schemas
import common

jsonschema = pytest.importorskip("jsonschema")


@pytest.fixture(scope="module")
def artifacts():
    directory = common.GENERATED_DIR
    names = sorted(p.stem for p in directory.glob("*.json"))
    if not names:
        pytest.skip("no artifacts published yet")
    return {n: json.loads((directory / f"{n}.json").read_text(encoding="utf-8"))
            for n in names}


def test_every_schema_is_itself_a_valid_draft_2020_12_schema():
    for name in artifact_schemas.declared():
        schema = artifact_schemas.load(name)
        assert schema["$schema"].endswith("2020-12/schema"), name
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)


def test_there_is_one_schema_per_published_artifact(artifacts):
    assert artifact_schemas.declared() == sorted(artifacts)


def test_the_committed_artifacts_match_their_schemas(artifacts):
    artifact_schemas.validate_all(artifacts)


def test_an_artifact_with_no_schema_is_refused(artifacts):
    with pytest.raises(artifact_schemas.SchemaViolation) as exc:
        artifact_schemas.validate_all({**artifacts, "hourly_demand": []})
    assert "hourly_demand" in str(exc.value)


def test_a_schema_with_no_artifact_is_refused(artifacts):
    rest = {k: v for k, v in artifacts.items() if k != "dwell"}
    with pytest.raises(artifact_schemas.SchemaViolation) as exc:
        artifact_schemas.validate_all(rest)
    assert "dwell" in str(exc.value)


# Each of these is a change a publisher edit could plausibly make, planted into
# a real committed artifact. The assertion is on the MESSAGE as well as the
# failure: a validator that says only "does not match schema" over a
# 2,333-element array is one nobody can act on.
PLANTED = [
    ("trips_monthly", lambda a: a[0].pop("trips"), "trips"),
    ("trips_monthly", lambda a: a[0].update(trips="8000"), "8000"),
    ("trips_monthly", lambda a: a[0].update(month="2026-7"), "2026-7"),
    ("seasonality", lambda a: a["series"][0].update(month_of_year=13), "13"),
    ("meta", lambda a: a["systems"][0].update(system_id="cal-bikeshare"),
     "cal-bikeshare"),
    ("meta", lambda a: a.update(extra_note="added upstream"), "extra_note"),
    ("stations", lambda a: a["stations"][0].update(y=1000), "1000"),
    ("stations", lambda a: a["stations"][0].update(a="yes"), "yes"),
    ("duration", lambda a: a[0].update(median_s=-1), "-1"),
    ("rebalancing", lambda a: a["hourly"][0].update(hour=24), "24"),
    ("dwell", lambda a: a["withheld"][0].update(basis="unclear"), "unclear"),
    ("forecast", lambda a: a["models"][0]["fit"].pop("cv_r2_log"), "cv_r2_log"),
    ("forecast",
     lambda a: a["models"][0]["coefficients"].update(temp_max_c="0.03"), "0.03"),
    ("forecast",
     lambda a: a["models"][0]["coefficients"].update(level_2017=0.1), "level_2017"),
    ("membership", lambda a: a["label_lost"][0].update(basis="looked wrong"),
     "looked wrong"),
    ("flows", lambda a: a["pairs"][0].update(r="true"), "true"),
]


@pytest.mark.parametrize("name,break_it,expected", PLANTED,
                         ids=[f"{n}-{e}" for n, _, e in PLANTED])
def test_a_planted_shape_drift_is_refused(artifacts, name, break_it, expected):
    payload = copy.deepcopy(artifacts[name])
    break_it(payload)
    with pytest.raises(artifact_schemas.SchemaViolation) as exc:
        artifact_schemas.validate(name, payload)
    message = str(exc.value)
    assert name in message
    assert expected in message, message


def test_the_message_names_where_the_violation_is(artifacts):
    payload = copy.deepcopy(artifacts["stations"])
    payload["stations"][7]["t"] = None
    with pytest.raises(artifact_schemas.SchemaViolation) as exc:
        artifact_schemas.validate("stations", payload)
    assert "stations/7/t" in str(exc.value)


def test_a_valid_artifact_is_accepted_after_a_repair(artifacts):
    """The counterpart, so the tests above are not passing because everything
    fails."""
    payload = copy.deepcopy(artifacts["trips_monthly"])
    kept = payload[0]["trips"]
    payload[0]["trips"] = "8000"
    with pytest.raises(artifact_schemas.SchemaViolation):
        artifact_schemas.validate("trips_monthly", payload)
    payload[0]["trips"] = kept
    artifact_schemas.validate("trips_monthly", payload)
