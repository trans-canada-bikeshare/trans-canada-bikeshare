# Spec 023 — Forecast

## Status

**Complete. 2026-07-30.** One model per system, published as coefficients and
fit statistics; the browser computes the prediction so a reader can move the
inputs. Rendering verified in a headed browser.

## Context

A ridership model per system trained on weather and calendar features, with the
out-of-range guard the Vancouver project already proved it needs — a model
asked to predict outside the conditions it was trained on should refuse, not
extrapolate.

## Scope

- **Sources touched:** ECCC daily climate via [spec 013](013-weather.md), and
  `fact_trips` aggregated to a day.
- **Cities touched:** all three. **Tier:** 1.
- **Published artifacts change:** yes — `src/data/generated/forecast.json`,
  33,805 B raw and 6,755 B gzip. Model coefficients and fit statistics, never
  predictions.

## The model

`ln(daily trips)` by ordinary least squares, one model per system, on:

| feature | transform |
| --- | --- |
| `temp_max_c` | as ECCC publishes it |
| `temp_min_c` | as ECCC publishes it |
| `precip_mm` | `ln(1 + mm)` |
| `snow_cm` | `ln(1 + cm)` |
| weekend | one indicator, Saturday and Sunday |
| calendar month | **one level per month in the window** |

`temp_mean_c` is absent because spec 013 measured it as exactly `(min+max)/2`
on all 12,670 rows, so it carries nothing the other two do not.
`snow_ground_cm` is absent because it is NULL on 66-96% of days and NULL means
**not reported**; the only way to use it would be to decide unreported means
zero, which is the substitution this project exists to prevent. Both absences
are asserted by tests rather than left to care.

Holidays are **not** a feature. There is no holiday calendar in the warehouse
and inventing one is out of scope; the page says so.

## Decisions, and why

### The common window, 2017 onward — not each system's full range

`forecast` is `comparable: true` in the metric registry, and comparable means
the same window as well as the same definition. Montreal's 2014-2016 (645 days)
and Toronto's 2016 (185 days) are therefore dropped from training and counted
as dropped in the artifact. Per-city depth was the alternative and it would
have bought Montreal about 640 more days at the cost of the one property the
registry exists to enforce.

### Operating days only, and never a synthesised zero

A day BIXI was closed is absent from `fact_trips` and stays absent. The model
is fitted on days each system actually ran — one definition, applied
identically to all three. Manufacturing a zero for a closed day would teach the
model that January in Montreal means no riding when what it means is no
service, and would bury a service decision inside a temperature coefficient.

The consequence ships as data: Montreal's January weather response rests on 85
days across 3 years (2024-2026), because BIXI ran no winter service before
December 2023, where Toronto's rests on 306 across 10. Both figures are in
`forecast.json` and the page states them from it.

### A level per calendar month, not month-of-year plus year

**This is the choice that changed during the build, and it changed because the
first specification was checked against reality and failed.**

The first model had month-of-year dummies and calendar-year dummies. It is
additive: it can say August is busy and that 2025 was a big year, but it has no
way to say August 2025 specifically was weak. Vancouver 2025 was exactly that —
up on 2024 in January, down 18% in August — and the additive model answered a
warm dry August 2025 weekday in Vancouver with **7,636 trips** where the
comparable days (24-29 °C, no rain, weekday, n=6) actually averaged **5,331**.
A 43% overstatement on the number the section puts in its largest type.

Giving each calendar month its own level removes the error by construction and
raises every fit statistic besides. Validation against the same slice, after
the change:

| system | actual mean | model at that slice's mean weather | ratio |
| --- | --- | --- | --- |
| van-mobi | 5,331 | 5,806 | 1.089 |
| mtl-bixi | 80,387 | 82,963 | 1.032 |
| tor-bikeshare | 40,301 | 44,269 | 1.098 |

The cost is stated on the page: most parameters are monthly levels, so the
weather coefficients measure only **within-month** variation. That is the
cleanest identification of a weather effect available here, and it is not a
claim about seasonality — the seasons section makes that claim from its own
artifact.

Passed on: month-of-year × year interactions (120 parameters per system and
Montreal has three winters), and shortening the training window to recent years
(throws away data and breaks the stated common window).

### `ln(trips)`, not trips

Ridership responses are proportional — rain costs a share of the day, not a
fixed count — and a linear model on counts predicts **negative daily trips**
inside its own envelope for a cold wet Montreal January, which is not a number
any honest surface can render. `exp()` of a linear fit cannot go below zero and
`Math.exp` reproduces it exactly in the browser.

`exp()` of a fitted log-mean is the **typical** day, near the median, not the
average. Duan's smearing factor is published rather than silently applied
(1.0338 / 1.0425 / 1.0293), and the card states both numbers.

### The reference year is derived, not typed

Every prediction is made at a calendar month, and the page compares three
cities at the same one, so that month must exist and be substantial in all
three. `reference_year()` returns the most recent year in which every system
has at least 20 training days in all twelve months. Today that is **2025**;
when 2026 fills in it moves on its own. If no such year exists the build stops
rather than anchoring the comparison on a month one city barely covered.

### The envelope is per month, and the union drives one shared set of dials

A whole-year envelope is too loose to be a guard: Toronto's overall high runs
-16.4 °C to 36.0 °C, so a 30 °C January would pass it while being a day the
city has never had. The published envelope is therefore per month of the year,
per system, and the UI enforces that one.

One set of dials drives all three panels, and the dial bounds are the **union**
across cities rather than the intersection. That is deliberate: a -15 °C
January day is ordinary in Montreal and outside anything Vancouver has
recorded, and an intersection would make the difference unreachable, which is
to say it would hide the finding.

Three refusal paths, all rendered: a weather value outside the month's range
(naming the range and the value asked for); a daily low above the daily high,
which is not a day; and a month the model has no level for.

## Acceptance Criteria

- [x] **One model per system, never pooled.** Three independent fits;
      `guard(registry, "forecast", ...)` runs at publish time and
      `check-metrics` reports `forecast  forecast  3/3 supported systems`
- [x] **Coefficients and fit statistics ship, not predictions.** `forecast.json`
      carries an intercept and one named coefficient per feature per system;
      `src/lib/forecast.ts` computes the prediction in the browser
- [x] **Features and transforms are on the page**, rendered from the
      artifact's own `inputs`/`calendar_inputs` rather than typed into JSX
- [x] **Refusal outside the envelope**, with the envelope stated. Verified in a
      headed browser: January at -11.4 °C answers in Montreal and Toronto and
      refuses in Vancouver, quoting `-6.4` to `14.3`
- [x] **Fit reported honestly, in-sample and labelled as such**, including
      where it is poor:

      | system | days | parameters (of which month levels) | R² ln(trips) | R² trips | median error | residual SD (log) |
      |---|---|---|---|---|---|---|
      | van-mobi | 3,373 | 119 (114) | 0.896488 | 0.913705 | 11.92% | 0.252607 |
      | mtl-bixi | 2,415 | 91 (86) | 0.940046 | 0.919062 | 12.29% | 0.275125 |
      | tor-bikeshare | 3,341 | 116 (111) | 0.908647 | 0.904186 | 14.58% | 0.304755 |

      Toronto fits worst on the trips scale and the page names it. Every panel
      also draws a 95% band from the residual SD, because a point estimate
      alone overstates what any of these models know.
- [x] **Montreal's winter closure handled explicitly.** Closed days are absent,
      not zero; December-March rest on 2024-2026 only; the page states it from
      the artifact's per-month `days`, `years` and `first_year`
- [x] **NULL weather days excluded and counted**, never imputed: 95 Vancouver,
      51 Montreal, 36 Toronto. Published under `excluded_days` and stated on
      the page
- [x] **Exclusions inherited.** Same `TRUSTED` filter and the same
      incomplete-month rule as every other artifact. A pytest re-derives the
      day counts from SQL written in the test, not by calling the pipeline
- [x] **Registry and gate.** `forecast` declared in
      `pipeline/check_metrics.py`'s `ARTIFACT_METRIC`; `make check-metrics`
      passes with the declaration and would have refused the artifact without it
- [x] **Deterministic.** Coefficients rounded to 9 decimals *before* the fit
      statistics are computed from them, stable row ordering, no random state,
      and a full-rank design asserted at fit time. `make check-artifacts`
      byte-compares a fresh run
- [x] **Budget.** 85,218 B gzip of 327,680 B (26.0%)
- [x] 112 vitest (was 99), 85 pytest (was 63), typecheck 0, build 0

## Data Integrity Checklist

- [x] **Provenance** — every weather value traces to a checksummed ECCC file
      pinned in the manifests by spec 013; every trip to the source manifests
- [x] **Nothing guessed** — no fill, no interpolation, no default. A day
      missing any of the four weather fields is dropped and counted. A
      rank-deficient design raises rather than accepting LAPACK's minimum-norm
      answer. An unknown feature name in the browser yields NaN, not zero
- [x] **Metrics defined identically** — same window, same features, same
      transforms, same exclusions, same response for all three
- [x] **Row accounting closes** — `fit.days + sum(excluded_days)` equals every
      day the system has a trip on, asserted per system against the warehouse
- [x] **Artifacts reproduce** — `make check-artifacts`
- [x] **Attribution ships with the data** — the ECCC acknowledgement is already
      in the sources note (spec 013) and is not duplicated; the forecast
      section carries the station-distance caveat that spec 013 asked for
- [x] **No raw data committed**

## Testing

**22 pytest**, split deliberately. The pure ones fit a model to data generated
from coefficients the test chose and check they come back, which is the only
way to test a fitting routine without grading it against its own output. The
warehouse-backed ones re-derive from SQL written in the test file rather than
calling `forecast.daily_rows`, so a mistake in that function fails rather than
appearing on both sides of an assertion.

Two of them exist because writing them found real problems:

- The synthetic generator originally set `temp_min_c = temp_max_c - 8`, making
  the low an exact linear function of the high and the intercept. The design
  was singular and `lstsq` returned a minimum-norm solution with an intercept
  of 0.20 where the truth was 6.5. That is what added the **rank guard** to
  `fit_system`, and the guard then caught a second instance: a constant
  `snow_cm` in the same generator, which becomes a column of zeros after
  `log1p`. Both are now tests.

**26 vitest** on the artifact and the prediction function, plus **5 new App
tests**. The prediction cases pin values computed by a separate Python
evaluation of the published coefficients — a different language and a different
loop over the same numbers — because an expectation produced by the code under
test proves only self-consistency.

## Verified in a headed browser

Chromium, `headless: false`, `document.visibilityState === "visible"` confirmed
before any reading, against `vite preview` on the production build.

- The section opens on July with all three panels answering: Vancouver 7,139 /
  Montreal 83,022 / Toronto 41,136, each matching the independent Python
  evaluation to the digit.
- Dragging **Daily high** from 27.9 °C to 19.6 °C changed all three
  simultaneously to 4,525 / 61,113 / 31,377; ticking **Weekend** changed them
  to 6,534 / 73,733 / 35,825; pushing **Precipitation** to 25 mm took Montreal
  and Toronto to 37,214 / 18,198 and put Vancouver outside its July envelope,
  whose wettest July day is 19.0 mm.
- Switching to **January** re-centred every dial and the panels answered
  1,597 / 3,070 / 7,811.
- Dragging January's daily high below **-11 °C** produced the refusal in
  Vancouver — "Outside what this model has seen", quoting the fitted range
  -6.4 to 14.3 °C and the value asked for — while Montreal and Toronto, whose
  Januaries reach -20.4 °C and -16.4 °C, answered 2,066 and 4,862.
- The July **snowfall** control renders as a statement rather than a dead
  slider, because no July in any of the three cities has recorded any.
- The three bars read 7.2% / 84.2% / 41.7% of a shared ceiling of 98,618, with
  the caption naming that ceiling and where it came from.
- Layout has no horizontal overflow at 1440, 820 or 390 px
  (`scrollWidth === clientWidth` at all three), and no console errors.

**The browser found a defect no test had asked about.** Dragging the daily-high
dial below the daily-low dial makes a day that cannot exist, and all three
models then refused for *that* reason — technically right, and it hid the only
thing the control exists to show. The dials now carry each other, holding the
diurnal range and clamping to the dial's own reach. A test pins the behaviour
now, but it was written after the browser found it, not before.

## Changes made during the build

- **The metric registry named the wrong weather stations.** `forecast` claimed
  "ECCC 888 Vancouver Harbour CS", "ECCC, downtown Montreal" and "ECCC 31688
  Toronto City". Spec 013 uses the **airports** — 51442 / 51157 / 51459 — and
  has since it landed. Corrected against the manifests and the warehouse, and
  the registry's `definition` for the metric now describes the model that was
  actually built rather than a placeholder.
- **The specification changed after validating against actuals** — see above.
  Finding it needed a query the acceptance criteria did not ask for.
- **The registry definition was written for the discarded model** and had to be
  corrected a second time, after the specification changed. Caught by grepping
  for the old model's vocabulary rather than by any gate; the definition is
  prose in a config file and nothing checks it against the code.
- **One App test had stopped asserting anything.** `moves the prediction when
  the reader moves the weather` skipped every system on a refusal, and its
  target value began crossing the daily low once the dials were coupled, so it
  passed while checking nothing. Fixed to fail rather than skip. The pinned
  prediction tests were then proved capable of failing, by perturbing
  `exp(logTrips)` by 137 trips and watching all three cross-implementation
  cases go red.
- **The rank guard**, and the two singular designs it caught in the tests.
- **The three bars needed a ceiling a prediction cannot overshoot.** The first
  version scaled them to the largest monthly mean, which an ordinary warm dry
  weekday exceeds, so two of the three bars were clipped at full width in the
  opening view — a shared scale that silently stopped being one. The ceiling is
  now the busiest single day in the record (98,618 in Montreal, 11 June 2025),
  published as `max_daily_trips` and stated in the caption. Bars now read
  7.2% / 84.2% / 41.7% in July.
- **Station distances are derived at publish time** from `dim_station` and
  `weather_station` (10.6 / 13.6 / 19.4 km) rather than quoted from spec 013's
  prose (10.6 / 13.5 / 19.3). The small differences are the weighting; the
  point is that the number the page prints cannot drift from the stations the
  warehouse actually loaded.

## Known limits, stated rather than fixed

- **Fit is in-sample.** There is no holdout, and the artifact says so in
  `fit_basis`. R² above 0.89 partly reflects fitting one level per month; the
  page states the parameter split for exactly that reason.
- **The weather is measured at an airport**, 10.6 / 13.6 / 19.4 km from each
  system's trip-weighted centre. Pearson is the weakest proxy: inland, colder
  and snowier than the lake-moderated core Bike Share Toronto runs in. Stated
  in the section.
- **No holidays, no strikes, no closures, no fare changes, no station
  outages.** Weather and the calendar are most of what moves a riding day and
  nowhere near all of it.
- **It is not a forecast of the future.** It describes how ridership varied
  with weather over 2017-2026, anchored at 2025. The copy says that in those
  words rather than implying a prediction about next week.

## Out of Scope

- Hourly weather (spec 013 settled this: 24x the volume for no gain daily).
- Any model the browser cannot reproduce exactly from published coefficients.
  That rules out trees, boosting and anything with a random seed, and it is a
  deliberate constraint rather than a shortcut: a prediction a reader cannot
  check is a prediction this site should not draw.

## Rollback

Single revert. `forecast.json` disappears, the section goes with it, and
`ARTIFACT_METRIC` loses its `forecast` entry — `make check-metrics` reports it
under "registry metrics not yet published", which is where it started.
