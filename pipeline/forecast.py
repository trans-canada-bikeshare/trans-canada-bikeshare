"""One weather-and-calendar ridership model per system, published as coefficients.

Spec 023. What ships is the *model*, not its predictions: an intercept, a named
coefficient per feature, the training envelope, and in-sample fit statistics.
The browser does the arithmetic, so a reader can move the inputs and watch the
number move — and so every prediction on the site is reproducible from numbers
that are visible in the artifact.

Five choices this file is built around, each of which could reasonably have
gone the other way and is therefore stated rather than assumed.

**One model per system, never pooled.** A pooled model with city dummies would
force one temperature response on three cities, which is precisely the
difference the site exists to show — Vancouver rides in the rain, and Montreal
does not ride at -20 °C partly because until December 2023 BIXI was not running.

**The common window, 2017 onward.** `forecast` is `comparable: true` in the
metric registry, and comparable means the same window as well as the same
definition. Montreal's 2014-2016 and Toronto's 2016 are dropped from training
for that reason and counted as dropped. Per-city depth was the alternative; it
would have bought Montreal ~640 more days at the cost of the one property the
registry exists to enforce.

**log trips, not trips.** Two reasons, one statistical and one that would show
on screen. Ridership responses are proportional — rain costs a share of the
day's riding, not a fixed count — and a linear model on counts predicts
NEGATIVE daily trips inside its own envelope (a cold wet Montreal January),
which is not a number any honest UI can render. exp() of a linear fit cannot go
below zero and `Math.exp` reproduces it exactly in the browser.

**A level per calendar month, not month-of-year plus year.** This is the choice
that changed during the build, and it changed because the first specification
was checked against reality and failed. With separate month-of-year and year
effects the model is additive: it can say August is busy and that 2025 was a
big year, but it has no way to say August 2025 specifically was weak. Vancouver
2025 was exactly that — up on 2024 in January, down 18% in August — and the
additive model answered a warm dry August 2025 weekday with **7,636 trips**
where the comparable days actually averaged **5,331**, a 43% overstatement on
the number the page puts in the largest type on the section. Giving each
calendar month its own level removes the error by construction and lifts every
fit statistic besides. The cost is honest and stated on the page: most of the
parameters are monthly levels, so the weather coefficients measure only
*within-month* variation, which is the cleanest identification of a weather
effect available here but is not a claim about seasonality. The site's
seasonality section makes that claim, from its own artifact.

**Operating days only, and no synthesised zeros.** A day BIXI was closed is
absent from `fact_trips`; it stays absent. Manufacturing a zero for it would
teach the model that January in Montreal means no riding when what it means is
no service, and would put a service decision inside a temperature coefficient.

Fit statistics are IN-SAMPLE and labelled so everywhere they appear. There is
no holdout: the artifact describes how ridership varied with weather over the
observed window, which is a different and weaker claim than forecasting a
future day, and the site makes that claim in those words.
"""

from __future__ import annotations

import math

import numpy as np

# The weather the model is given, and the exact fields it is given them in.
#
# temp_mean_c is deliberately ABSENT. Spec 013 established that ECCC's mean is
# exactly (min+max)/2 on all 12,670 rows, so it is a linear combination of two
# features already here and carries no information at all.
#
# snow_ground_cm is deliberately absent too, and for the opposite reason: it is
# NULL on 66-96% of days, NULL means NOT REPORTED, and the only way to use it
# would be to decide that unreported means zero. That substitution is the one
# this project has named its cardinal sin.
WEATHER_INPUTS = ("temp_max_c", "temp_min_c", "precip_mm", "snow_cm")

# Features shared by every system, in canonical order. The per-month level
# features follow, and differ per system because the systems cover different
# months.
#
# The transform on precipitation and snowfall: the first millimetre of rain
# changes a riding day far more than the twentieth, and log1p is the standard
# way to say so while keeping zero at zero — every dry day has precip 0.0 and
# log1p(0) is exactly 0, so no dry day is displaced by it. `Math.log1p` in the
# browser is the same function.
SHARED_FEATURES = (
    "temp_max_c",
    "temp_min_c",
    "precip_log1p_mm",
    "snow_log1p_cm",
    "is_weekend",
)

DEFAULT_FIRST_YEAR = 2017

# A calendar month whose level is fitted on fewer days than this is a level
# fitted on a fraction of a month. Such a block may still exist in training —
# it is real data — but it may not be the year the page anchors its comparison
# at, because a thin block makes one city's panel answer a different question
# from the other two.
MIN_REFERENCE_BLOCK_DAYS = 20

# Coefficients are rounded before anything is computed from them, so the fit
# statistics the artifact publishes are the fit of the coefficients the artifact
# publishes — not of an unrounded model the reader never sees. 9 decimals is far
# below any plausible LAPACK jitter (~1e-13 on an intercept of order 10) and far
# above any precision the prediction needs.
COEF_DP = 9
STAT_DP = 6


class NotEnoughData(Exception):
    """A system has too little usable data to fit a model at all."""


def block_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def block_feature(key: str) -> str:
    return f"level_{key}"


def feature_names(blocks: list[str]) -> list[str]:
    """Canonical feature order for a system covering `blocks`.

    The first block is the reference level, so its feature is absent — a full
    set of level dummies alongside an intercept is a singular design, and the
    solver would return one of infinitely many answers rather than failing. That
    is a determinism bug as much as a statistical one: `make check-artifacts`
    would report drift with no cause anybody could name.
    """
    return list(SHARED_FEATURES) + [block_feature(b) for b in blocks[1:]]


def feature_vector(day: dict, blocks: list[str]) -> dict[str, float]:
    """The model's view of one day. Pure, so tests can pin it.

    `day` needs temp_max_c, temp_min_c, precip_mm, snow_cm, is_weekend and
    block. Every one must be present and non-NULL: a day missing an observation
    is dropped upstream by `usable_day`, never patched here.
    """
    vec = {
        "temp_max_c": float(day["temp_max_c"]),
        "temp_min_c": float(day["temp_min_c"]),
        "precip_log1p_mm": math.log1p(float(day["precip_mm"])),
        "snow_log1p_cm": math.log1p(float(day["snow_cm"])),
        "is_weekend": 1.0 if day["is_weekend"] else 0.0,
    }
    for b in blocks[1:]:
        vec[block_feature(b)] = 1.0 if day["block"] == b else 0.0
    return vec


def usable_day(day: dict) -> bool:
    """A day with a complete weather observation and at least one trip.

    NULL is never imputed. ECCC's record has real gaps — spec 013 counted them
    per city per year — and 0 °C, 0 mm and 0 cm are all common legitimate
    values, so a fill would be indistinguishable from an observation.
    """
    if any(day.get(f) is None for f in WEATHER_INPUTS):
        return False
    return day["trips"] > 0


def _round_stats(d: dict) -> dict:
    return {k: (round(v, STAT_DP) if isinstance(v, float) else v) for k, v in d.items()}


def _ols(design: "np.ndarray", log_trips: "np.ndarray") -> "np.ndarray":
    """The one OLS core, shared by the full fit and every CV fold.

    A rank-deficient design has infinitely many least-squares solutions and
    lstsq silently returns the minimum-norm one — coefficients that fit
    equally well and mean something different, chosen by the linear algebra
    library rather than by the data. That would also break byte
    reproducibility across any change in that library, which is the gate this
    feature has to pass. Stop instead. Coefficients are rounded to COEF_DP
    before anything is computed from them, so LAPACK jitter at 1e-13 is
    absorbed.
    """
    beta, _residuals, rank, _singular = np.linalg.lstsq(design, log_trips, rcond=None)
    if rank < design.shape[1]:
        raise NotEnoughData(
            f"design matrix has rank {rank} for {design.shape[1]} columns: some "
            "feature is a linear combination of the others, so the coefficients "
            "would not be unique"
        )
    return np.round(beta, COEF_DP)


def _cross_validate(days: list[dict], blocks: list[str], folds: int = 5) -> dict:
    """K-fold cross-validation over DAYS, deterministic, no randomness.

    Fold assignment is index mod K over the date-sorted day list. Folding over
    days rather than month blocks is deliberate: holding out a whole block
    would leave its level unidentified — the model could not predict it at all
    — while day folds keep every level identified and measure exactly the
    thing in question, which is whether the five weather coefficients
    generalise to days the fit never saw.

    Identifiability guard: a day whose month block would lose its LAST
    training day in some fold stays in training for that fold instead, and is
    counted in `always_in_train`. Never silently dropped, and no fold is ever
    allowed to go rank-deficient by construction.

    Out-of-sample errors use the same conventions as the in-sample statistics:
    log-scale residuals, and trip-scale errors through a raw exp() with no
    smearing.
    """
    names = feature_names(blocks)
    n = len(days)
    trips_all = np.array([d["trips"] for d in days], dtype=float)
    log_all = np.log(trips_all)
    design_all = np.array(
        [[1.0] + [feature_vector(d, blocks)[n_] for n_ in names] for d in days],
        dtype=float,
    )
    block_of = [d["block"] for d in days]

    oos_pred_log = np.full(n, np.nan)
    always_in_train = 0
    for f in range(folds):
        test_idx = [i for i in range(n) if i % folds == f]
        train_mask = np.ones(n, dtype=bool)
        train_mask[test_idx] = False
        # Guard: every block must keep at least one training day.
        train_blocks = {block_of[i] for i in range(n) if train_mask[i]}
        kept_test = []
        for i in test_idx:
            if block_of[i] not in train_blocks:
                train_mask[i] = True
                always_in_train += 1
            else:
                kept_test.append(i)
        if not kept_test:
            continue
        beta = _ols(design_all[train_mask], log_all[train_mask])
        for i in kept_test:
            oos_pred_log[i] = float(design_all[i] @ beta)

    held = ~np.isnan(oos_pred_log)
    held_n = int(held.sum())
    if held_n < n // 2:
        raise NotEnoughData(
            f"cross-validation held out only {held_n} of {n} days — the "
            "identifiability guard has swallowed the test set"
        )
    resid = log_all[held] - oos_pred_log[held]
    ss_oos = float((resid ** 2).sum())
    ss_tot = float(((log_all[held] - log_all[held].mean()) ** 2).sum())
    pred_trips = np.exp(oos_pred_log[held])
    pct = np.abs(trips_all[held] - pred_trips) / trips_all[held]
    out = {
        "cv_folds": int(folds),
        "cv_held_out_days": held_n,
        "cv_r2_log": float(1.0 - ss_oos / ss_tot),
        "cv_median_abs_pct_error": float(np.median(pct) * 100.0),
    }
    if always_in_train:
        out["cv_always_in_train"] = int(always_in_train)
    return out


def fit_system(days: list[dict], blocks: list[str]) -> dict:
    """Ordinary least squares of ln(daily trips) on the feature vector.

    Returns coefficients rounded to `COEF_DP`, and fit statistics computed FROM
    those rounded coefficients.
    """
    names = feature_names(blocks)
    if len(days) <= len(names) + 1:
        raise NotEnoughData(
            f"{len(days)} usable days against {len(names)} features"
        )
    design = np.array(
        [[1.0] + [feature_vector(d, blocks)[n] for n in names] for d in days],
        dtype=float,
    )
    trips = np.array([d["trips"] for d in days], dtype=float)
    log_trips = np.log(trips)

    beta = _ols(design, log_trips)

    predicted_log = design @ beta
    predicted = np.exp(predicted_log)
    residual_log = log_trips - predicted_log

    n, k = design.shape
    ss_res = float((residual_log ** 2).sum())
    ss_tot = float(((log_trips - log_trips.mean()) ** 2).sum())
    r2_log = 1.0 - ss_res / ss_tot
    # Degrees of freedom: n - k, where k already counts the intercept. Worth
    # reporting beside r2_log precisely because most of those parameters are
    # monthly levels rather than anything about weather.
    adj_r2_log = 1.0 - (1.0 - r2_log) * (n - 1) / (n - k)
    residual_sd_log = float(math.sqrt(ss_res / (n - k)))

    ss_res_t = float(((trips - predicted) ** 2).sum())
    ss_tot_t = float(((trips - trips.mean()) ** 2).sum())

    return {
        "intercept": float(beta[0]),
        "coefficients": {n_: float(b) for n_, b in zip(names, beta[1:])},
        "fit": _round_stats({
            "days": int(n),
            "parameters": int(k),
            "month_levels": int(len(blocks)),
            "weather_parameters": int(len(SHARED_FEATURES)),
            "first_day": days[0]["date"],
            "last_day": days[-1]["date"],
            # In-sample, on the scale the model was fitted to.
            "r2_log": float(r2_log),
            "adj_r2_log": float(adj_r2_log),
            "residual_sd_log": residual_sd_log,
            # And on the scale a reader cares about, after exp(). Reported
            # because a good log-scale fit can still be a poor trip-scale one:
            # log flatters the low-count winter days that dominate the count.
            "r2_trips": float(1.0 - ss_res_t / ss_tot_t),
            "mae_trips": float(np.abs(trips - predicted).mean()),
            "median_abs_pct_error": float(
                np.median(np.abs(trips - predicted) / trips) * 100.0
            ),
            "mean_daily_trips": float(trips.mean()),
            # The busiest day in the training window. Published because the
            # site draws three bars on one shared ceiling — spec 021's rule for
            # the station maps, which applies to any encoding sitting in a grid
            # — and a ceiling taken from monthly means is one an ordinary warm
            # dry weekday overshoots, so the bar would clip on the default
            # view. A real observed maximum can still be exceeded by an extreme
            # corner of the envelope; the component clamps and the caption says
            # what the ceiling is.
            "max_daily_trips": int(trips.max()),
            "max_daily_date": days[int(trips.argmax())]["date"],
            # exp() of a fitted log-mean is the TYPICAL day, near the median,
            # not the average one. Duan's smearing factor is how much higher the
            # average runs; published rather than silently applied, so the page
            # can say which quantity it is drawing.
            "smearing_factor": float(np.exp(residual_log).mean()),
            # Out-of-sample. The in-sample R² above partly reflects fitting
            # one level per calendar month; this is the number that cannot.
            # The first model this spec built had excellent in-sample
            # statistics while overstating a checked day by 43%.
            **_cross_validate(days, blocks),
        }),
    }


def _range(values: list[float]) -> dict:
    return {
        "min": round(float(min(values)), 1),
        "max": round(float(max(values)), 1),
        "median": round(float(np.median(values)), 1),
    }


def _envelope(days: list[dict]) -> dict:
    return {f: _range([d[f] for d in days]) for f in WEATHER_INPUTS}


def _month_blocks(days: list[dict], reference_year: int) -> list[dict]:
    """Per-month-of-year training ranges, medians and coverage.

    The per-month envelope is the one the UI enforces, because the whole-year
    one is too loose to be a guard: Toronto's overall high runs -16.4 °C to
    36.0 °C, so a 30 °C January passes it easily while being a day the city has
    never had. Medians ship too, so the UI's starting values are a typical day
    for the month rather than a number somebody picked.

    Ranges span every year in the window, because the weather coefficients are
    fitted across every year in the window. The reference year's own count and
    mean ship alongside, because that is the month the page anchors on.
    """
    out = []
    for m in range(1, 13):
        rows = [d for d in days if d["month"] == m]
        if not rows:
            continue
        ref = [d for d in rows if d["year"] == reference_year]
        out.append({
            "month": m,
            "days": len(rows),
            "first_year": min(d["year"] for d in rows),
            "last_year": max(d["year"] for d in rows),
            "years": len({d["year"] for d in rows}),
            "mean_trips": int(round(sum(d["trips"] for d in rows) / len(rows))),
            "reference_days": len(ref),
            "reference_mean_trips": (
                int(round(sum(d["trips"] for d in ref) / len(ref))) if ref else None
            ),
            "ranges": {f: _range([d[f] for d in rows]) for f in WEATHER_INPUTS},
        })
    return out


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def reference_year(by_system: dict[str, list[dict]]) -> int:
    """The most recent year every system has a usable level for all twelve months.

    Every prediction is made AT a calendar month, and the page compares three
    cities at the same one, so that month has to exist and be substantial in all
    three. Anchoring on the most recent such year also keeps the prediction an
    interpolation: the model is never asked for a month it has not seen, which
    is the same refusal the weather envelope makes.

    Derived, not typed: when 2026 fills in, this moves on its own.
    """
    candidates: set[int] | None = None
    for days in by_system.values():
        counts: dict[tuple[int, int], int] = {}
        for d in days:
            counts[(d["year"], d["month"])] = counts.get((d["year"], d["month"]), 0) + 1
        covered = {
            y for y in {k[0] for k in counts}
            if all(counts.get((y, m), 0) >= MIN_REFERENCE_BLOCK_DAYS
                   for m in range(1, 13))
        }
        candidates = covered if candidates is None else (candidates & covered)
    if not candidates:
        raise NotEnoughData(
            "no calendar year has all twelve months covered by at least "
            f"{MIN_REFERENCE_BLOCK_DAYS} days in every system, so there is no "
            "shared month to anchor a comparable prediction on"
        )
    return max(candidates)


def daily_rows(con, trusted: str, first_year: int) -> tuple[list[dict], dict]:
    """Daily trip counts joined to that city's weather, plus the drop accounting.

    The exclusions are inherited, not reinvented: the same TRUSTED filter and
    the same incomplete-month rule every other artifact applies, so a day that
    is not in `trips_monthly` is not in the model either.
    """
    rows = con.execute(f"""
      WITH incomplete AS (
        SELECT system_id, strftime(trip_month, '%Y-%m') AS month
        FROM fact_trips WHERE {trusted}
        GROUP BY 1, 2, trip_month
        HAVING count(DISTINCT date_key) <= 3
            OR (trip_month = (SELECT max(f2.trip_month) FROM fact_trips f2
                              WHERE f2.system_id = fact_trips.system_id)
                AND count(DISTINCT date_key) < day(last_day(trip_month)))
      ), daily AS (
        SELECT system_id, date_key, trip_year,
               strftime(trip_month, '%Y-%m') AS month_key, count(*) AS trips
        FROM fact_trips WHERE {trusted}
        GROUP BY 1, 2, 3, 4
      )
      SELECT d.system_id, d.date_key, d.trips, d.month_key,
             (d.trip_year < ?)                                   AS before_window,
             EXISTS (SELECT 1 FROM incomplete i
                     WHERE i.system_id = d.system_id
                       AND i.month = d.month_key)                AS in_incomplete_month,
             w.temp_max_c, w.temp_min_c, w.precip_mm, w.snow_cm,
             dd.is_weekend, dd.month AS month, dd.year AS year
      FROM daily d
      LEFT JOIN weather_daily w
        ON w.system_id = d.system_id AND w.date_key = d.date_key
      LEFT JOIN dim_date dd ON dd.date_key = d.date_key
      ORDER BY d.system_id, d.date_key
    """, [first_year]).fetchall()
    cols = [c[0] for c in con.description]

    kept: list[dict] = []
    dropped: dict[str, dict[str, int]] = {}
    empty = {"before_common_window": 0, "incomplete_month": 0,
             "no_weather_observation": 0}

    for raw in rows:
        day = dict(zip(cols, raw))
        system = day["system_id"]
        counters = dropped.setdefault(system, dict(empty))
        if day["before_window"]:
            counters["before_common_window"] += 1
            continue
        if day["in_incomplete_month"]:
            counters["incomplete_month"] += 1
            continue
        if not usable_day(day):
            # The only remaining reason a day fails usable_day is a missing
            # observation: `trips` is a COUNT over rows that exist, so it is
            # never zero here. If that ever changes this counter would silently
            # absorb it, so it is asserted rather than assumed.
            if day["trips"] <= 0:
                raise NotEnoughData(
                    f"{system} {day['date_key']} aggregated to {day['trips']} trips; "
                    "a day with no trips should have no row at all"
                )
            counters["no_weather_observation"] += 1
            continue
        if day["date_key"].year != day["year"] or day["date_key"].month != day["month"]:
            raise NotEnoughData(
                f"dim_date disagrees with {system} {day['date_key']} on its own "
                "year or month; the calendar join is wrong"
            )
        if day["month_key"] != block_key(day["year"], day["month"]):
            raise NotEnoughData(
                f"{system} {day['date_key']} sits in trip month {day['month_key']} "
                f"but calendar month {block_key(day['year'], day['month'])}"
            )
        day["date"] = day["date_key"].isoformat()
        day["block"] = day["month_key"]
        kept.append(day)
    return kept, dropped


def build(con, first_year: int = DEFAULT_FIRST_YEAR, trusted: str = "TRUE") -> dict:
    """The published `forecast.json` payload."""
    kept, dropped = daily_rows(con, trusted, first_year)

    by_system: dict[str, list[dict]] = {}
    for day in kept:
        by_system.setdefault(day["system_id"], []).append(day)

    ref_year = reference_year(by_system)
    years = sorted({d["year"] for d in kept})

    stations = {
        r[0]: {"name": r[1], "climate_id": r[2], "lat": r[3], "lon": r[4]}
        for r in con.execute("""
          SELECT system_id, station_name, climate_id, lat, lon
          FROM weather_station ORDER BY system_id
        """).fetchall()
    }
    centroids = {
        r[0]: (r[1], r[2])
        for r in con.execute("""
          SELECT system_id,
                 sum(lat * lifetime_events) / sum(lifetime_events),
                 sum(lon * lifetime_events) / sum(lifetime_events)
          FROM dim_station WHERE lat IS NOT NULL AND lifetime_events > 0
          GROUP BY 1 ORDER BY 1
        """).fetchall()
    }

    models = []
    for system in sorted(by_system):
        days = by_system[system]
        blocks = sorted({d["block"] for d in days})
        model = fit_system(days, blocks)
        station = stations[system]
        lat, lon = centroids[system]
        models.append({
            "system_id": system,
            # Per system, because the systems cover different months: Montreal
            # has no January before 2024 and never will have one before then.
            # A shared list padded with zero coefficients would publish an
            # estimate for a month that was never estimated.
            "features": feature_names(blocks),
            "blocks": blocks,
            # The one block with no feature of its own: its level IS the
            # intercept. Named so nobody has to infer it from an absence.
            "reference_level_block": blocks[0],
            "intercept": model["intercept"],
            "coefficients": model["coefficients"],
            "fit": model["fit"],
            "excluded_days": dropped[system],
            "envelope": _envelope(days),
            "months": _month_blocks(days, ref_year),
            "weather_station": {
                "name": station["name"],
                "climate_id": station["climate_id"],
                # Derived here rather than quoted from spec 013's prose, so the
                # caveat the site prints cannot drift from the stations the
                # warehouse actually loaded.
                "km_from_centroid": round(
                    haversine_km(lat, lon, station["lat"], station["lon"]), 1
                ),
            },
        })

    return {
        "first_year": first_year,
        "reference_year": ref_year,
        "years": years,
        "weather_features": list(SHARED_FEATURES),
        # What the reader can move, and exactly what the model does with it.
        # Published rather than written into the component, because spec 023
        # asks for the transformations to be on the page and a hand-typed list
        # beside a generated model is a list that will eventually be wrong.
        "inputs": [
            {"key": "temp_max_c", "label": "Daily high", "unit": "°C",
             "feature": "temp_max_c", "transform": "used as published"},
            {"key": "temp_min_c", "label": "Daily low", "unit": "°C",
             "feature": "temp_min_c", "transform": "used as published"},
            {"key": "precip_mm", "label": "Precipitation", "unit": "mm",
             "feature": "precip_log1p_mm", "transform": "ln(1 + mm)"},
            {"key": "snow_cm", "label": "Snowfall", "unit": "cm",
             "feature": "snow_log1p_cm", "transform": "ln(1 + cm)"},
        ],
        "calendar_inputs": [
            {"key": "is_weekend", "label": "Weekend",
             "transform": "one indicator, Saturday and Sunday"},
            {"key": "month", "label": "Calendar month",
             "transform": "one level per month in the window, so each month "
                          f"carries its own; held at {ref_year} on this page"},
        ],
        "reference_levels": {
            "note": "The earliest calendar month each system covers is its "
                    "reference level and is absorbed into the intercept.",
        },
        "response": "ln(daily trips)",
        "fit_basis": "in-sample: every statistic is computed on the same days "
                     "the model was fitted to, with no holdout",
        "envelope_note": "The per-month range is what the model has actually "
                         "seen in that month of the year. Outside it the model "
                         "refuses rather than extrapolating.",
        "prediction_note": "exp(intercept + sum of coefficient x feature) is the "
                           "typical day for those conditions, near the median. "
                           "The average day runs higher by the smearing factor.",
        "models": models,
    }
