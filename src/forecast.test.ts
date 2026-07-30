import { describe, expect, it } from "vitest";
import {
  forecast, modelFor, monthBlock, predict, featureValue, blockKey,
  sharedSpan, defaultConditions, busiestMonth, weakestFit, furthestStation,
  type Conditions, type ForecastModel,
} from "@/lib/forecast";
import { SYSTEM_ORDER } from "@/lib/systems";

/**
 * The prediction values pinned below were computed by a separate Python script
 * that reads `forecast.json` and evaluates the model independently of this
 * file — a different language, a different loop, the same published
 * coefficients. That is the point: an expectation produced by the code under
 * test proves only that the code is consistent with itself.
 *
 * Regenerate them, if the artifact changes, by re-running that evaluation
 * rather than by pasting whatever the failing test printed.
 */
const JULY: Conditions = {
  month: 7,
  temp_max_c: 27.9,
  temp_min_c: 17.9,
  precip_mm: 0,
  snow_cm: 0,
  is_weekend: false,
};

const PINNED: Record<string, { trips: number; low: number; high: number; mean: number }> = {
  "van-mobi": {
    trips: 7139.17164359502,
    low: 4351.353879389854,
    high: 11713.08359867479,
    mean: 7348.349372752355,
  },
  "mtl-bixi": {
    trips: 83022.01289353015,
    low: 48417.47431927345,
    high: 142358.82234257186,
    mean: 85829.48528153777,
  },
  "tor-bikeshare": {
    trips: 41136.10907612897,
    low: 22636.564613113114,
    high: 74754.25263703305,
    mean: 42882.665995283256,
  },
};

describe("forecast artifact", () => {
  it("carries a model for every system the site compares", () => {
    for (const id of SYSTEM_ORDER) expect(modelFor(id), id).toBeDefined();
    expect(forecast.models).toHaveLength(SYSTEM_ORDER.length);
  });

  it("has a finite coefficient for every feature it lists, and no others", () => {
    for (const m of forecast.models) {
      expect(Object.keys(m.coefficients).sort(), m.system_id).toEqual(
        [...m.features].sort(),
      );
      expect(Number.isFinite(m.intercept), m.system_id).toBe(true);
      for (const name of m.features) {
        expect(Number.isFinite(m.coefficients[name]), `${m.system_id} ${name}`).toBe(true);
      }
    }
  });

  // The drift this guards is silent: a feature the pipeline publishes and the
  // browser cannot build would contribute NaN, and NaN * 0 is still NaN, so
  // one unrecognised name poisons every prediction on the page.
  it("can build a value for every feature name it publishes", () => {
    for (const m of forecast.models) {
      for (const name of m.features) {
        const v = featureValue(name, JULY, forecast.reference_year);
        expect(Number.isNaN(v), `${m.system_id} ${name}`).toBe(false);
      }
    }
  });

  it("treats an unknown feature as NaN rather than as zero", () => {
    expect(Number.isNaN(featureValue("humidity_pct", JULY, 2025))).toBe(true);
  });

  it("reports a plausible in-sample fit for every system", () => {
    for (const m of forecast.models) {
      expect(m.fit.r2_log, m.system_id).toBeGreaterThan(0.5);
      expect(m.fit.r2_log, m.system_id).toBeLessThan(1);
      expect(m.fit.r2_trips, m.system_id).toBeGreaterThan(0.5);
      expect(m.fit.r2_trips, m.system_id).toBeLessThan(1);
      expect(m.fit.adj_r2_log, m.system_id).toBeLessThan(m.fit.r2_log);
      expect(m.fit.residual_sd_log, m.system_id).toBeGreaterThan(0);
      expect(m.fit.median_abs_pct_error, m.system_id).toBeGreaterThan(0);
      // exp() of a fitted log mean is below the arithmetic mean, always.
      expect(m.fit.smearing_factor, m.system_id).toBeGreaterThan(1);
      expect(m.fit.days, m.system_id).toBeGreaterThan(m.fit.parameters * 10);
      expect(m.fit.parameters, m.system_id).toBe(
        m.fit.month_levels + m.fit.weather_parameters,
      );
    }
  });

  it("keeps every month range inside the whole-year envelope", () => {
    for (const m of forecast.models) {
      for (const block of m.months) {
        for (const [key, span] of Object.entries(block.ranges)) {
          expect(span.min, `${m.system_id} ${block.month} ${key}`).toBeLessThanOrEqual(
            span.median,
          );
          expect(span.median).toBeLessThanOrEqual(span.max);
          expect(span.min).toBeGreaterThanOrEqual(m.envelope[key].min);
          expect(span.max).toBeLessThanOrEqual(m.envelope[key].max);
        }
      }
    }
  });

  it("has a level for the reference year in all twelve months of every model", () => {
    for (const m of forecast.models) {
      for (let month = 1; month <= 12; month += 1) {
        const key = blockKey(forecast.reference_year, month);
        expect(m.blocks, `${m.system_id} ${key}`).toContain(key);
        expect(monthBlock(m, month)?.reference_days, key).toBeGreaterThan(0);
      }
    }
  });

  it("names its reference level rather than leaving it to be inferred", () => {
    for (const m of forecast.models) {
      expect(m.blocks[0], m.system_id).toBe(m.reference_level_block);
      expect(m.features, m.system_id).not.toContain(`level_${m.blocks[0]}`);
    }
  });
});

describe("prediction", () => {
  it("reproduces values computed independently from the published coefficients", () => {
    for (const id of SYSTEM_ORDER) {
      const result = predict(modelFor(id)!, JULY);
      expect(result.ok, id).toBe(true);
      if (!result.ok) return;
      // 1e-9 relative: the two implementations differ only in the order the
      // same additions happen and in Math.log1p versus math.log1p.
      expect(result.trips, id).toBeCloseTo(PINNED[id].trips, 6);
      expect(result.low, id).toBeCloseTo(PINNED[id].low, 6);
      expect(result.high, id).toBeCloseTo(PINNED[id].high, 6);
      expect(result.mean, id).toBeCloseTo(PINNED[id].mean, 6);
    }
  });

  // Two of the five inputs moved, so this fails if either the weekend
  // indicator or the log1p on precipitation is wired up wrongly, which a
  // single all-defaults case cannot distinguish.
  it("reproduces a wet weekend independently computed too", () => {
    const result = predict(modelFor("van-mobi")!, {
      ...JULY, precip_mm: 8, is_weekend: true,
    });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.trips).toBeCloseTo(3632.9750782465153, 6);
  });

  it("reproduces a snowy Montreal January independently computed too", () => {
    const result = predict(modelFor("mtl-bixi")!, {
      month: 1, temp_max_c: -4.3, temp_min_c: -11.6,
      precip_mm: 0.4, snow_cm: 5, is_weekend: false,
    });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.trips).toBeCloseTo(2268.059719383046, 6);
  });

  it("puts the prediction inside its own 95% band", () => {
    for (const id of SYSTEM_ORDER) {
      const r = predict(modelFor(id)!, JULY);
      expect(r.ok, id).toBe(true);
      if (!r.ok) return;
      expect(r.low, id).toBeLessThan(r.trips);
      expect(r.trips, id).toBeLessThan(r.high);
      // The average day is above the typical one, by the smearing factor.
      expect(r.mean, id).toBeGreaterThan(r.trips);
    }
  });

  it("refuses a January colder than the coldest Vancouver has recorded", () => {
    const model = modelFor("van-mobi")!;
    const span = monthBlock(model, 1)!.ranges.temp_max_c;
    const result = predict(model, {
      month: 1, temp_max_c: span.min - 10, temp_min_c: span.min - 18,
      precip_mm: 0, snow_cm: 0, is_weekend: false,
    });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.refusals.map((r) => r.key)).toContain("temp_max_c");
    const refusal = result.refusals.find((r) => r.key === "temp_max_c")!;
    expect(refusal.span.min).toBe(span.min);
    expect(refusal.value).toBe(span.min - 10);
  });

  // The same day is inside one city's envelope and outside another's. That is
  // the whole reason the section drives three models from one set of dials.
  it("answers for a deep-freeze January in Montreal and refuses it in Vancouver", () => {
    const conditions: Conditions = {
      month: 1, temp_max_c: -15, temp_min_c: -22,
      precip_mm: 0, snow_cm: 0, is_weekend: false,
    };
    expect(predict(modelFor("mtl-bixi")!, conditions).ok).toBe(true);
    expect(predict(modelFor("van-mobi")!, conditions).ok).toBe(false);
  });

  it("refuses a day whose low is above its high", () => {
    const model = modelFor("tor-bikeshare")!;
    const span = monthBlock(model, 7)!.ranges;
    const result = predict(model, {
      month: 7,
      temp_max_c: span.temp_max_c.min,
      temp_min_c: span.temp_min_c.max,
      precip_mm: 0, snow_cm: 0, is_weekend: false,
    });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.impossible).toMatch(/low is above/);
  });

  it("refuses a month the model has no level for", () => {
    // Constructed rather than found: every real model covers every month of
    // the reference year, and the branch still has to work when one does not.
    const real = modelFor("mtl-bixi")!;
    const gapped: ForecastModel = {
      ...real,
      blocks: real.blocks.filter((b) => b !== blockKey(forecast.reference_year, 7)),
      months: real.months.map((b) =>
        b.month === 7 ? { ...b, reference_days: 0, reference_mean_trips: null } : b,
      ),
    };
    const result = predict(gapped, JULY);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.impossible).toMatch(/no level for it/);
  });
});

describe("the shared controls", () => {
  it("spans the union of the three cities, never the intersection", () => {
    for (let month = 1; month <= 12; month += 1) {
      for (const input of forecast.inputs) {
        const shared = sharedSpan(month, input.key);
        for (const m of forecast.models) {
          const own = monthBlock(m, month)!.ranges[input.key];
          expect(shared.min, `${m.system_id} ${month} ${input.key}`)
            .toBeLessThanOrEqual(own.min);
          expect(shared.max).toBeGreaterThanOrEqual(own.max);
        }
      }
    }
  });

  it("opens on a day every model can answer, in every month", () => {
    for (let month = 1; month <= 12; month += 1) {
      const conditions = defaultConditions(month);
      // The middling high and the middling low are separate medians and can
      // come from different cities, so the day they describe has to be checked
      // rather than assumed.
      expect(conditions.temp_min_c, `month ${month}`)
        .toBeLessThanOrEqual(conditions.temp_max_c);
      for (const m of forecast.models) {
        const result = predict(m, conditions);
        expect(result.ok, `${m.system_id} at the default for ${month}`).toBe(true);
      }
    }
  });

  it("opens on defaults inside the shared range for every month", () => {
    for (let month = 1; month <= 12; month += 1) {
      const conditions = defaultConditions(month) as unknown as Record<string, number>;
      for (const input of forecast.inputs) {
        const span = sharedSpan(month, input.key);
        expect(conditions[input.key], `${month} ${input.key}`)
          .toBeGreaterThanOrEqual(span.min);
        expect(conditions[input.key]).toBeLessThanOrEqual(span.max);
      }
    }
  });
});

describe("the claims the section makes", () => {
  it("names the weakest fit and the furthest station from the artifact", () => {
    const weakest = weakestFit();
    for (const m of forecast.models) {
      expect(m.fit.r2_trips, m.system_id).toBeGreaterThanOrEqual(weakest.fit.r2_trips);
    }
    const furthest = furthestStation();
    for (const m of forecast.models) {
      expect(
        m.weather_station.km_from_centroid, m.system_id,
      ).toBeLessThanOrEqual(furthest.weather_station.km_from_centroid);
    }
  });

  // The airport caveat is only worth printing if the distances are real, and
  // spec 013 measured them at 10.6, 13.5 and 19.3 km from the trip-weighted
  // centroids. These are recomputed at publish time from dim_station, so they
  // may move a little; they may not become nothing.
  it("carries a real station distance for every city", () => {
    for (const m of forecast.models) {
      expect(m.weather_station.km_from_centroid, m.system_id).toBeGreaterThan(5);
      expect(m.weather_station.km_from_centroid, m.system_id).toBeLessThan(40);
      expect(m.weather_station.name, m.system_id).toMatch(/\S/);
      expect(m.weather_station.climate_id, m.system_id).toMatch(/^\d+$/);
    }
  });

  // The section says all three stations are airports. That is true of the
  // stations spec 013 pinned, and it is the kind of sentence that rots
  // silently if a station is ever swapped for a downtown one.
  it("still stands on the airport stations the copy describes", () => {
    for (const m of forecast.models) {
      expect(m.weather_station.name, m.system_id).toMatch(/INTL A$/);
    }
  });

  // The three bars are drawn on one ceiling, so it has to be a value no
  // prediction can exceed. A monthly mean is not; an observed daily maximum is.
  it("publishes a busiest day above every month's mean, in every system", () => {
    for (const m of forecast.models) {
      expect(m.fit.max_daily_trips, m.system_id).toBeGreaterThan(
        m.fit.mean_daily_trips,
      );
      for (const b of m.months) {
        expect(m.fit.max_daily_trips, `${m.system_id} ${b.month}`)
          .toBeGreaterThanOrEqual(b.mean_trips);
      }
      expect(m.fit.max_daily_date, m.system_id).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(m.fit.max_daily_date >= m.fit.first_day, m.system_id).toBe(true);
      expect(m.fit.max_daily_date <= m.fit.last_day, m.system_id).toBe(true);
    }
  });

  it("counts every day it dropped instead of hiding them", () => {
    for (const m of forecast.models) {
      const d = m.excluded_days;
      expect(d.no_weather_observation, m.system_id).toBeGreaterThan(0);
      for (const v of Object.values(d)) expect(v).toBeGreaterThanOrEqual(0);
    }
  });

  it("describes each input's transform, so the page never types one", () => {
    for (const input of forecast.inputs) {
      expect(input.transform, input.key).toMatch(/\S/);
      expect(input.label, input.key).toMatch(/\S/);
    }
    const byKey = Object.fromEntries(forecast.inputs.map((i) => [i.key, i]));
    expect(byKey.precip_mm.transform).toContain("ln(1 +");
    expect(byKey.snow_cm.transform).toContain("ln(1 +");
  });

  // Spec 013's cardinal rule, enforced at the artifact rather than trusted.
  it("uses neither the mean temperature nor snow on the ground", () => {
    for (const m of forecast.models) {
      expect(m.features.join(" "), m.system_id).not.toContain("temp_mean");
      expect(m.features.join(" "), m.system_id).not.toContain("snow_ground");
    }
    expect(forecast.inputs.map((i) => i.key)).not.toContain("snow_ground_cm");
  });
});
