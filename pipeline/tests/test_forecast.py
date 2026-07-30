"""Spec 023 — the per-system ridership models.

Two kinds of test here, and the split is deliberate.

The pure ones fit a model to data generated from coefficients this file chose,
and check the coefficients come back. That is the only way to test a fitting
routine without grading it against its own output: a test that recomputes R²
the way `fit_system` does and asserts they agree proves nothing at all.

The warehouse-backed ones re-derive from SQL written here, not by calling
`forecast.daily_rows`, so a mistake in that function fails rather than
propagating into both sides of an assertion.
"""

import json
import math

import pytest

numpy = pytest.importorskip("numpy")
duckdb = pytest.importorskip("duckdb")

import common  # noqa: E402
import forecast  # noqa: E402

TRUSTED = "NOT list_contains(quality_flags, 'implausible_date')"

# Three years of calendar months, which is what a synthetic fit needs to have
# more days than parameters.
BLOCKS = [forecast.block_key(y, m) for y in (2017, 2018, 2019) for m in range(1, 13)]


@pytest.fixture(scope="module")
def con():
    db = common.DATA_WAREHOUSE / "bikeshare.duckdb"
    if not db.exists():
        pytest.skip(f"warehouse not built at {db}")
    c = duckdb.connect(str(db), read_only=True)
    yield c
    c.close()


@pytest.fixture(scope="module")
def artifact():
    path = common.GENERATED_DIR / "forecast.json"
    if not path.exists():
        pytest.skip(f"{path} not published yet")
    return json.loads(path.read_text(encoding="utf-8"))


# --- the feature map ---------------------------------------------------------

def test_the_first_calendar_month_is_the_reference_level():
    """A full set of level dummies alongside an intercept is a singular design.

    The solver would still return an answer; it would just be one of infinitely
    many, chosen by whatever LAPACK does that day. That is a determinism bug as
    much as a statistical one, and `make check-artifacts` would find it as
    drift with no cause anyone could name.
    """
    names = forecast.feature_names(BLOCKS)
    assert "level_2017-01" not in names
    assert "level_2017-02" in names
    assert "level_2019-12" in names
    assert len(names) == len(forecast.SHARED_FEATURES) + len(BLOCKS) - 1


def test_the_mean_temperature_is_not_a_feature():
    """Spec 013 measured it: ECCC's mean is exactly (min+max)/2 on all 12,670
    rows, so it is a linear combination of two features already present."""
    assert "temp_mean_c" not in forecast.feature_names(BLOCKS)
    assert "temp_mean_c" not in forecast.WEATHER_INPUTS


def test_snow_on_the_ground_is_not_a_feature():
    """NULL on 66-96% of days and NULL means NOT REPORTED. The only way to use
    it is to decide unreported means zero, which is the substitution this
    project exists to refuse."""
    assert "snow_ground_cm" not in forecast.WEATHER_INPUTS
    assert not any("snow_ground" in n for n in forecast.feature_names(BLOCKS))


def test_feature_vector_pins_its_transforms():
    day = {
        "temp_max_c": 21.5, "temp_min_c": 12.0, "precip_mm": 3.0,
        "snow_cm": 0.0, "is_weekend": True, "block": "2018-07",
    }
    vec = forecast.feature_vector(day, BLOCKS)
    assert vec["temp_max_c"] == 21.5
    assert vec["temp_min_c"] == 12.0
    # ln(1 + 3) = ln 4. Written as the arithmetic, not as log1p(3), so the test
    # would fail if the transform silently became log().
    assert vec["precip_log1p_mm"] == pytest.approx(math.log(4.0), abs=1e-12)
    # A dry day is exactly zero after the transform, not merely small. That is
    # the property that makes log1p safe for a field whose modal value is 0.
    assert vec["snow_log1p_cm"] == 0.0
    assert vec["is_weekend"] == 1.0
    assert vec["level_2018-07"] == 1.0
    assert vec["level_2018-06"] == 0.0
    assert vec["level_2019-07"] == 0.0


def test_a_missing_observation_is_never_a_zero():
    base = {
        "temp_max_c": 10.0, "temp_min_c": 2.0, "precip_mm": 0.0,
        "snow_cm": 0.0, "is_weekend": False, "block": "2018-04", "trips": 500,
    }
    # All-zero weather is a real day and must be kept: 0 °C, 0 mm and 0 cm all
    # happen, which is exactly why a fill could never be spotted afterwards.
    assert forecast.usable_day(base)
    for field in forecast.WEATHER_INPUTS:
        missing = dict(base, **{field: None})
        assert not forecast.usable_day(missing), field


# --- the fit -----------------------------------------------------------------

def _synthetic(coefficients: dict, intercept: float, per_block: int = 26) -> list[dict]:
    """Days generated FROM a known model, so the fit has a right answer."""
    rng = numpy.random.default_rng(20260730)
    days = []
    for block in BLOCKS:
        for i in range(per_block):
            day = {
                "temp_max_c": float(rng.uniform(-10, 32)),
                "precip_mm": float(rng.uniform(0, 20)),
                # Not a constant. A column that never varies is a column of
                # zeros after log1p, the design loses rank, and `fit_system`
                # rightly refuses — which is the behaviour the rank guard adds
                # and the reason this generator has to produce real variation.
                "snow_cm": float(rng.uniform(0, 5)),
                "is_weekend": bool(i % 7 in (5, 6)),
                "block": block,
                "date": f"{block}-{(i % 28) + 1:02d}",
            }
            # A varying diurnal range, not a constant one. With a fixed offset
            # the low is an exact linear function of the high and the intercept,
            # the design is singular, and lstsq returns the minimum-norm
            # solution rather than the coefficients that generated the data.
            day["temp_min_c"] = day["temp_max_c"] - float(rng.uniform(4, 12))
            vec = forecast.feature_vector(day, BLOCKS)
            log_trips = intercept + sum(
                coefficients.get(k, 0.0) * v for k, v in vec.items())
            day["trips"] = float(math.exp(log_trips))
            days.append(day)
    return days


def test_the_fit_recovers_coefficients_it_was_not_told():
    truth = {"temp_max_c": 0.04, "precip_log1p_mm": -0.25,
             "is_weekend": -0.10, "level_2018-07": 0.30, "level_2019-03": 0.15}
    days = _synthetic(truth, intercept=6.5)
    model = forecast.fit_system(days, BLOCKS)
    assert model["intercept"] == pytest.approx(6.5, abs=1e-6)
    for name, value in truth.items():
        assert model["coefficients"][name] == pytest.approx(value, abs=1e-6), name
    # Noiseless data: the model is the data-generating process exactly.
    assert model["fit"]["r2_log"] == pytest.approx(1.0, abs=1e-9)


def test_the_same_input_fits_the_same_coefficients_twice():
    """`make check-artifacts` byte-compares a fresh run against the committed
    one, so a fit that is not bit-stable makes the feature unmergeable."""
    days = _synthetic({"temp_max_c": 0.03, "precip_log1p_mm": -0.2}, intercept=7.0)
    first = forecast.fit_system(days, BLOCKS)
    second = forecast.fit_system(list(days), BLOCKS)
    assert first["intercept"] == second["intercept"]
    assert first["coefficients"] == second["coefficients"]
    assert first["fit"] == second["fit"]


def test_published_fit_statistics_are_the_fit_of_the_published_coefficients():
    """Rounding happens before the statistics are computed, not after.

    Otherwise the artifact states an R² that its own coefficients do not
    produce, and the browser — which has only the rounded numbers — quietly
    disagrees with the page's own claim about how well it does.
    """
    days = _synthetic({"temp_max_c": 0.041234567891, "precip_log1p_mm": -0.2},
                      intercept=6.8)
    model = forecast.fit_system(days, BLOCKS)
    names = forecast.feature_names(BLOCKS)
    predicted = numpy.array([
        model["intercept"]
        + sum(model["coefficients"][n] * forecast.feature_vector(d, BLOCKS)[n]
              for n in names)
        for d in days
    ])
    observed = numpy.log(numpy.array([d["trips"] for d in days]))
    r2 = 1 - ((observed - predicted) ** 2).sum() / (
        (observed - observed.mean()) ** 2).sum()
    assert round(float(r2), 6) == model["fit"]["r2_log"]


def test_too_few_days_refuses_rather_than_fitting_noise():
    days = _synthetic({"temp_max_c": 0.03}, intercept=7.0, per_block=1)
    with pytest.raises(forecast.NotEnoughData):
        forecast.fit_system(days, BLOCKS)


def test_a_feature_that_never_varies_refuses_rather_than_returning_a_zero():
    """A column of zeros makes the design singular, and lstsq answers anyway.

    It returns the minimum-norm solution: coefficients that fit exactly as well
    as infinitely many others and were chosen by LAPACK rather than the data.
    That is a wrong number AND a reproducibility hazard, since another BLAS
    could pick a different member of the same solution set.
    """
    days = _synthetic({"temp_max_c": 0.03}, intercept=7.0)
    for day in days:
        day["snow_cm"] = 0.0
    with pytest.raises(forecast.NotEnoughData, match="rank"):
        forecast.fit_system(days, BLOCKS)


def test_the_reference_year_is_the_latest_all_systems_cover_completely():
    def year(y, months, days_each=25):
        return [{"year": y, "month": m} for m in months for _ in range(days_each)]

    full_ = list(range(1, 13))
    by_system = {
        "a": year(2024, full_) + year(2025, full_) + year(2026, [1, 2, 3]),
        "b": year(2024, full_) + year(2025, full_) + year(2026, [1, 2, 3, 4]),
    }
    assert forecast.reference_year(by_system) == 2025
    # One system short of a full year everywhere -> no shared anchor, so the
    # comparison has no honest year to sit at and the build stops.
    with pytest.raises(forecast.NotEnoughData):
        forecast.reference_year({"a": year(2025, full_), "b": year(2025, [1, 2])})


def test_a_month_covered_by_only_a_few_days_cannot_anchor_the_comparison():
    """A thin month makes one city's panel answer a different question."""
    def year(y, months, days_each):
        return [{"year": y, "month": m} for m in months for _ in range(days_each)]

    full_ = list(range(1, 13))
    thin = year(2025, [1], 3) + year(2025, list(range(2, 13)), 28)
    with pytest.raises(forecast.NotEnoughData):
        forecast.reference_year({"a": year(2025, full_, 28), "b": thin})


# --- what actually shipped ---------------------------------------------------

def test_every_supported_system_has_a_model(artifact):
    registry = json.loads(
        (common.MAPPINGS_DIR / "metric_support.json").read_text(encoding="utf-8"))
    supported = {k for k, v in registry["metrics"]["forecast"]["systems"].items()
                 if v.get("supported")}
    assert {m["system_id"] for m in artifact["models"]} == supported


def test_no_published_coefficient_is_infinite_or_missing(artifact):
    for model in artifact["models"]:
        assert math.isfinite(model["intercept"]), model["system_id"]
        assert set(model["coefficients"]) == set(model["features"]), \
            model["system_id"]
        for name, value in model["coefficients"].items():
            assert math.isfinite(value), f"{model['system_id']} {name}"


def test_every_model_carries_a_level_for_every_month_of_the_reference_year(artifact):
    """The page holds the calendar year at this value and compares three
    cities at the same month, so all three must have that exact month."""
    for model in artifact["models"]:
        for month in range(1, 13):
            key = forecast.block_key(artifact["reference_year"], month)
            assert key in model["blocks"], f"{model['system_id']} {key}"
            block = next(b for b in model["months"] if b["month"] == month)
            assert block["reference_days"] >= forecast.MIN_REFERENCE_BLOCK_DAYS


def test_the_training_day_count_matches_an_independently_written_query(con, artifact):
    """The same window and the same exclusions, expressed in SQL written here.

    Not a call into `forecast.daily_rows`: a test whose two sides come from one
    function cannot fail for the reason it exists.
    """
    first_year = artifact["first_year"]
    rows = con.execute(f"""
      WITH partial_months AS (
        SELECT system_id, strftime(trip_month, '%Y-%m') AS ym
        FROM fact_trips WHERE {TRUSTED}
        GROUP BY 1, 2, trip_month
        HAVING count(DISTINCT date_key) <= 3
            OR (trip_month = (SELECT max(x.trip_month) FROM fact_trips x
                              WHERE x.system_id = fact_trips.system_id)
                AND count(DISTINCT date_key) < day(last_day(trip_month)))
      )
      SELECT t.system_id, count(*) AS n FROM (
        SELECT system_id, date_key, strftime(trip_month, '%Y-%m') AS ym
        FROM fact_trips WHERE {TRUSTED} AND trip_year >= {first_year}
        GROUP BY 1, 2, 3
      ) t
      JOIN weather_daily w
        ON w.system_id = t.system_id AND w.date_key = t.date_key
      WHERE w.temp_max_c IS NOT NULL AND w.temp_min_c IS NOT NULL
        AND w.precip_mm IS NOT NULL AND w.snow_cm IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM partial_months p
                        WHERE p.system_id = t.system_id AND p.ym = t.ym)
      GROUP BY 1 ORDER BY 1
    """).fetchall()
    expected = dict(rows)
    for model in artifact["models"]:
        assert model["fit"]["days"] == expected[model["system_id"]], \
            model["system_id"]


def test_the_dropped_days_account_for_every_day_not_trained_on(con, artifact):
    """Kept plus dropped equals every day the system has a trip on."""
    totals = dict(con.execute(f"""
      SELECT system_id, count(DISTINCT date_key)
      FROM fact_trips WHERE {TRUSTED} GROUP BY 1 ORDER BY 1
    """).fetchall())
    for model in artifact["models"]:
        dropped = sum(model["excluded_days"].values())
        assert model["fit"]["days"] + dropped == totals[model["system_id"]], \
            model["system_id"]


def test_the_envelope_contains_every_day_the_model_was_fitted_on(con, artifact):
    """An envelope narrower than the training data would refuse days the model
    has in fact seen; wider, and it admits days it has not."""
    for model in artifact["models"]:
        for field, span in model["envelope"].items():
            lo, hi = con.execute(f"""
              SELECT min(w.{field}), max(w.{field})
              FROM weather_daily w
              JOIN (SELECT DISTINCT system_id, date_key FROM fact_trips
                    WHERE {TRUSTED} AND trip_year >= {artifact['first_year']}) t
                ON t.system_id = w.system_id AND t.date_key = w.date_key
              WHERE w.system_id = ?
            """, [model["system_id"]]).fetchone()
            assert span["min"] >= round(lo, 1) - 1e-9, (model["system_id"], field)
            assert span["max"] <= round(hi, 1) + 1e-9, (model["system_id"], field)


def test_every_month_range_sits_inside_the_whole_year_range(artifact):
    for model in artifact["models"]:
        for block in model["months"]:
            for field, span in block["ranges"].items():
                whole = model["envelope"][field]
                assert span["min"] >= whole["min"], (model["system_id"], field)
                assert span["max"] <= whole["max"], (model["system_id"], field)
                assert span["min"] <= span["median"] <= span["max"]


def test_the_station_distance_matches_the_stations_the_warehouse_holds(con, artifact):
    """Derived at publish time from dim_station and weather_station, so this
    checks the derivation rather than a number somebody remembered."""
    for model in artifact["models"]:
        lat, lon, wlat, wlon, name = con.execute("""
          SELECT c.lat, c.lon, w.lat, w.lon, w.station_name FROM (
            SELECT system_id,
                   sum(lat * lifetime_events) / sum(lifetime_events) AS lat,
                   sum(lon * lifetime_events) / sum(lifetime_events) AS lon
            FROM dim_station WHERE lat IS NOT NULL AND lifetime_events > 0
            GROUP BY 1
          ) c JOIN weather_station w USING (system_id)
          WHERE c.system_id = ?
        """, [model["system_id"]]).fetchone()
        km = forecast.haversine_km(lat, lon, wlat, wlon)
        assert model["weather_station"]["km_from_centroid"] == round(km, 1)
        assert model["weather_station"]["name"] == name


def test_montreal_winter_rests_only_on_the_years_bixi_ran_in_winter(con, artifact):
    """BIXI's first winter of service is a fact of the trip data, and the
    artifact's month blocks must not claim any earlier one."""
    first_winter_year = con.execute(f"""
      SELECT min(trip_year) FROM fact_trips
      WHERE {TRUSTED} AND system_id = 'mtl-bixi' AND month(date_key) IN (1, 2, 3)
        AND trip_year >= {artifact['first_year']}
    """).fetchone()[0]
    model = next(m for m in artifact["models"] if m["system_id"] == "mtl-bixi")
    for block in model["months"]:
        if block["month"] in (1, 2, 3):
            assert block["first_year"] >= first_winter_year


def test_no_month_level_is_fitted_on_a_single_day(con, artifact):
    """Every published level is a month, not a stub.

    The incomplete-month rule already removes 1-3 day months, so this is the
    assertion that it actually reached the model rather than only the charts.
    """
    for model in artifact["models"]:
        counts = dict(con.execute(f"""
          SELECT strftime(trip_month, '%Y-%m'), count(DISTINCT date_key)
          FROM fact_trips WHERE {TRUSTED} AND system_id = ?
          GROUP BY 1 ORDER BY 1
        """, [model["system_id"]]).fetchall())
        for block in model["blocks"]:
            assert counts[block] > 3, (model["system_id"], block)


# --- cross-validation (added after review; closes the builder's flagged gap) --

def test_cv_statistics_exist_and_hold_out_every_day(artifact):
    for m in artifact["models"]:
        f = m["fit"]
        assert f["cv_folds"] == 5, m["system_id"]
        # The identifiability guard may keep a day in training, but with
        # 15-31 day blocks and 5 folds it should never actually fire.
        assert f["cv_held_out_days"] == f["days"], m["system_id"]
        assert "cv_always_in_train" not in f, m["system_id"]


def test_cv_is_out_of_sample_not_a_restatement(artifact):
    """CV must be worse than (or ~equal to) in-sample, never better.

    An out-of-sample statistic that beats the in-sample one is a leak: the
    held-out day influenced the fold's fit somehow.
    """
    for m in artifact["models"]:
        f = m["fit"]
        assert f["cv_r2_log"] <= f["r2_log"] + 0.005, m["system_id"]
        assert f["cv_median_abs_pct_error"] >= f["median_abs_pct_error"] - 0.5, m["system_id"]


def test_cv_shows_the_weather_coefficients_generalise(artifact):
    """The reason this statistic exists.

    The first model this spec built had in-sample R² above 0.89 while being
    43% wrong on a checked day. If cv_r2_log ever collapses, the page's
    framing is wrong and the number must NOT be massaged to keep this green —
    the plan's own red line is 0.75.
    """
    for m in artifact["models"]:
        f = m["fit"]
        assert f["cv_r2_log"] > 0.75, (m["system_id"], f["cv_r2_log"])
        # The page says the CV error sits within a fraction of a point of the
        # fitted figure; hold that sentence to under one point.
        assert f["cv_median_abs_pct_error"] - f["median_abs_pct_error"] < 1.0, m["system_id"]
