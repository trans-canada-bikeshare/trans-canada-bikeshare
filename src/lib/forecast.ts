/** The published ridership models, and the arithmetic that turns one into a number.
 *
 * `forecast.json` ships coefficients, not predictions, so this file is where
 * the site actually computes a prediction. Two consequences worth stating:
 *
 *  1. Nothing here decides anything. Every constant a prediction depends on —
 *     the features, their order, the intercept, the coefficients, the training
 *     envelope, the year the prediction is anchored at — comes from the
 *     artifact. This module knows how to multiply and how to refuse.
 *  2. The feature values are built by NAME, off the artifact's own list, not
 *     from a second hand-written ordering. A hand-written ordering is a thing
 *     that drifts silently: the numbers keep rendering, they are just wrong.
 *
 * It lives outside `data.ts` because `data.ts` states its own job as rendering
 * what the pipeline published and computing nothing. That rule is worth
 * keeping, so the one artifact that genuinely needs arithmetic in the browser
 * gets its own module rather than an exception inside that one.
 */

import forecastJson from "@/data/generated/forecast.json";
import type { SystemId } from "@/lib/systems";

/** [min, max] plus the median, over the days the model was trained on. */
export interface Span {
  min: number;
  max: number;
  median: number;
}

export interface ForecastFit {
  days: number;
  parameters: number;
  /** How many of those parameters are month levels rather than weather. */
  month_levels: number;
  weather_parameters: number;
  first_day: string;
  last_day: string;
  /** In-sample R² on ln(daily trips), the scale the model was fitted on. */
  r2_log: number;
  adj_r2_log: number;
  /** Residual standard deviation on the log scale — a multiplicative spread. */
  residual_sd_log: number;
  /** In-sample R² after exp(), on the trips a reader actually sees. */
  r2_trips: number;
  mae_trips: number;
  median_abs_pct_error: number;
  mean_daily_trips: number;
  /** The busiest single day in the training window, and when it was. */
  max_daily_trips: number;
  max_daily_date: string;
  /** How much higher the AVERAGE day runs than the typical day this predicts. */
  smearing_factor: number;
}

export interface MonthBlock {
  month: number;
  days: number;
  first_year: number;
  last_year: number;
  years: number;
  /** Mean daily trips in this month of the year, across the whole window. */
  mean_trips: number;
  /** …and in the reference year alone, which is the level the page anchors on. */
  reference_days: number;
  reference_mean_trips: number | null;
  ranges: Record<string, Span>;
}

export interface ForecastModel {
  system_id: SystemId;
  /** Per system: the systems do not cover the same calendar months. */
  features: string[];
  /** Every calendar month the model has a level for, as "YYYY-MM". */
  blocks: string[];
  reference_level_block: string;
  intercept: number;
  coefficients: Record<string, number>;
  fit: ForecastFit;
  excluded_days: {
    before_common_window: number;
    incomplete_month: number;
    no_weather_observation: number;
  };
  envelope: Record<string, Span>;
  months: MonthBlock[];
  weather_station: { name: string; climate_id: string; km_from_centroid: number };
}

export interface InputMeta {
  key: string;
  label: string;
  unit?: string;
  feature?: string;
  transform: string;
}

export const forecast = forecastJson as {
  first_year: number;
  reference_year: number;
  years: number[];
  weather_features: string[];
  inputs: InputMeta[];
  calendar_inputs: InputMeta[];
  reference_levels: { note: string };
  response: string;
  fit_basis: string;
  envelope_note: string;
  prediction_note: string;
  models: ForecastModel[];
};

/** The four weather dials, in the order the artifact lists them. */
export const WEATHER_KEYS = forecast.inputs.map((i) => i.key);

export interface Conditions {
  month: number;
  temp_max_c: number;
  temp_min_c: number;
  precip_mm: number;
  snow_cm: number;
  is_weekend: boolean;
  /** Defaults to the artifact's reference year, which is where every panel sits. */
  year?: number;
}

export function modelFor(id: SystemId): ForecastModel | undefined {
  return forecast.models.find((m) => m.system_id === id);
}

export function monthBlock(model: ForecastModel, month: number): MonthBlock | undefined {
  return model.months.find((b) => b.month === month);
}

/**
 * One feature's value for a set of conditions.
 *
 * Returns NaN for a name it does not recognise, deliberately. A published
 * feature this file cannot build is a drift between the pipeline and the site,
 * and NaN propagates to a visibly broken prediction instead of a plausible
 * wrong one — zero would silently mean "this condition does not apply today".
 * `src/forecast.test.ts` asserts every published feature name resolves.
 */
export function featureValue(name: string, c: Conditions, year: number): number {
  switch (name) {
    case "temp_max_c":
      return c.temp_max_c;
    case "temp_min_c":
      return c.temp_min_c;
    // The pipeline's transform, by the same name, computed by the same
    // function. log1p keeps a dry day at exactly zero.
    case "precip_log1p_mm":
      return Math.log1p(c.precip_mm);
    case "snow_log1p_cm":
      return Math.log1p(c.snow_cm);
    case "is_weekend":
      return c.is_weekend ? 1 : 0;
  }
  const level = /^level_(\d{4})-(\d{2})$/.exec(name);
  if (level) {
    return year === Number(level[1]) && c.month === Number(level[2]) ? 1 : 0;
  }
  return Number.NaN;
}

/** The calendar month a prediction sits in, as the artifact keys it. */
export function blockKey(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}

export interface Refusal {
  /** the input key, e.g. "temp_max_c" */
  key: string;
  label: string;
  unit: string;
  value: number;
  span: Span;
}

export type Prediction =
  | {
      ok: true;
      /** The typical day for these conditions, in trips. */
      trips: number;
      /** Central 95% of the days the model was fitted at these conditions. */
      low: number;
      high: number;
      /** What the AVERAGE such day runs, using the published smearing factor. */
      mean: number;
      /** Mean daily trips in that month of the reference year, all weather. */
      monthMean: number;
    }
  | { ok: false; refusals: Refusal[]; impossible?: string };

/** ±1.96 σ on the log scale: the central 95% of the fitted residuals. */
const Z95 = 1.96;

/**
 * Predict, or refuse.
 *
 * The refusal is the point of the exercise, not an edge case. Every model here
 * is a straight line through a cloud of days that actually happened, and a
 * straight line will cheerfully answer for -30 °C in Vancouver, where the
 * coldest day the model has ever seen had a high of -7.8 °C. The per-month
 * training range is what it has seen; outside it there is no answer, only an
 * extrapolation dressed as one.
 */
export function predict(model: ForecastModel, c: Conditions): Prediction {
  const year = c.year ?? forecast.reference_year;
  const block = monthBlock(model, c.month);
  if (!block) {
    return {
      ok: false,
      refusals: [],
      impossible: "this system has no training days in that month at all",
    };
  }
  // The model carries a level per calendar month, so a month it never ran in
  // has no level and no answer. Nothing here invents one from the neighbours.
  // `blocks` is authoritative: a block exists exactly when that month had
  // training days.
  if (!model.blocks.includes(blockKey(year, c.month))) {
    return {
      ok: false,
      refusals: [],
      impossible: `this system published no ${blockKey(year, c.month)}, so the model has no level for it`,
    };
  }

  const refusals: Refusal[] = [];
  for (const input of forecast.inputs) {
    const span = block.ranges[input.key];
    const value = (c as unknown as Record<string, number>)[input.key];
    if (span && (value < span.min || value > span.max)) {
      refusals.push({
        key: input.key,
        label: input.label,
        unit: input.unit ?? "",
        value,
        span,
      });
    }
  }
  if (refusals.length) return { ok: false, refusals };

  // Not an envelope check but a physical one: no day has a low above its high,
  // so no training day does either, and the model has no basis for one.
  if (c.temp_min_c > c.temp_max_c) {
    return {
      ok: false,
      refusals: [],
      impossible: "the daily low is above the daily high, which is not a day",
    };
  }

  let logTrips = model.intercept;
  for (const name of model.features) {
    logTrips += model.coefficients[name] * featureValue(name, c, year);
  }
  const trips = Math.exp(logTrips);
  return {
    ok: true,
    trips,
    low: Math.exp(logTrips - Z95 * model.fit.residual_sd_log),
    high: Math.exp(logTrips + Z95 * model.fit.residual_sd_log),
    mean: trips * model.fit.smearing_factor,
    monthMean: block.reference_mean_trips ?? block.mean_trips,
  };
}

/**
 * The range a shared control may span for a month: the union across systems.
 *
 * Deliberately the union rather than the intersection. One set of dials drives
 * all three panels, and the interesting thing about the envelope is that it is
 * a different shape in each city — a -15 °C day is an ordinary Montreal January
 * and outside anything Vancouver has recorded. An intersection would make that
 * unreachable, which is to say it would hide the finding.
 */
export function sharedSpan(month: number, key: string): Span {
  const spans = forecast.models
    .map((m) => monthBlock(m, month)?.ranges[key])
    .filter((s): s is Span => Boolean(s));
  const medians = spans.map((s) => s.median).sort((a, b) => a - b);
  return {
    min: Math.min(...spans.map((s) => s.min)),
    max: Math.max(...spans.map((s) => s.max)),
    // Median of the per-system medians: a middling day everywhere rather than
    // a typical day in whichever city happens to be listed first.
    median: medians[Math.floor(medians.length / 2)],
  };
}

/** Starting conditions for a month: a middling day, from the artifact.
 *
 * The four medians are taken independently, so nothing guarantees on its own
 * that the middling high and the middling low came from the same city or even
 * describe a possible day. They do for every month in the current data, and a
 * test holds that; the clamp is here so a future month cannot open the section
 * on a day that does not exist.
 */
export function defaultConditions(month: number, isWeekend = false): Conditions {
  const high = sharedSpan(month, "temp_max_c").median;
  const low = sharedSpan(month, "temp_min_c").median;
  return {
    month,
    temp_max_c: high,
    temp_min_c: Math.min(low, high),
    precip_mm: sharedSpan(month, "precip_mm").median,
    snow_cm: sharedSpan(month, "snow_cm").median,
    is_weekend: isWeekend,
  };
}

/** The busiest month across the three systems — where the section opens. */
export function busiestMonth(): number {
  let best = 1;
  let bestTrips = -1;
  for (let m = 1; m <= 12; m += 1) {
    const total = forecast.models.reduce(
      (n, model) => n + (monthBlock(model, m)?.reference_mean_trips ?? 0),
      0,
    );
    if (total > bestTrips) {
      bestTrips = total;
      best = m;
    }
  }
  return best;
}

/** The system whose model fits worst, by trip-scale R². Named, not implied. */
export function weakestFit(): ForecastModel {
  return forecast.models.reduce((a, b) =>
    a.fit.r2_trips <= b.fit.r2_trips ? a : b,
  );
}

/** The weather station sitting furthest from the riding it stands in for. */
export function furthestStation(): ForecastModel {
  return forecast.models.reduce((a, b) =>
    a.weather_station.km_from_centroid >= b.weather_station.km_from_centroid ? a : b,
  );
}

/**
 * The busiest day any of the three systems has recorded — the one ceiling all
 * three bars are drawn against.
 *
 * Spec 021 settled this for the station maps and the reasoning transfers
 * intact: three panels side by side under one heading, each scaled to itself,
 * encode at different rates while looking like a comparison. It has to be an
 * observed maximum rather than an average, because a prediction can exceed any
 * average and a clipped bar is a silent lie about a quantity nobody can see.
 */
export function busiestDay(): ForecastModel {
  return forecast.models.reduce((a, b) =>
    a.fit.max_daily_trips >= b.fit.max_daily_trips ? a : b,
  );
}
