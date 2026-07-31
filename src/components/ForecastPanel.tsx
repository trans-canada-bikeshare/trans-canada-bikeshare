import { useMemo, useState } from "react";
import { Note } from "@/components/Section";
import { SYSTEM_ORDER, SYSTEMS, seriesColor, cityOf } from "@/lib/systems";
import { compact, full, longDate, MONTH_SHORT } from "@/lib/format";
import {
  forecast, modelFor, monthBlock, predict, sharedSpan, defaultConditions,
  busiestMonth, busiestDay, weakestFit, furthestStation,
  type Conditions, type Span, type ForecastModel,
} from "@/lib/forecast";

/** One decimal, the precision ECCC publishes and the envelope is stored at. */
function dec(n: number): string {
  return n.toFixed(1);
}

function Dial({
  label, unit, value, span, onChange,
}: {
  label: string;
  unit: string;
  value: number;
  span: Span;
  onChange: (n: number) => void;
}) {
  return (
    <label className="block">
      <span className="eyebrow flex items-baseline justify-between gap-2">
        <span>
          {label}
          {unit ? ` (${unit})` : ""}
        </span>
        <span className="font-mono tabular-nums text-foreground">{dec(value)}</span>
      </span>
      <input
        type="range"
        aria-label={`${label}${unit ? ` in ${unit}` : ""}`}
        className="mt-2 w-full accent-[hsl(var(--primary))]"
        min={span.min}
        max={span.max}
        // `any`, not a fixed step. The bounds are real observed extremes to one
        // decimal, so a fixed step puts the grid off the bounds and the thumb
        // lands somewhere other than the number printed beside it.
        step="any"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="mt-1 flex justify-between font-mono text-[11px] tabular-nums text-muted-foreground">
        <span>{dec(span.min)}</span>
        <span>{dec(span.max)}</span>
      </span>
    </label>
  );
}

function SystemCard({
  model, conditions, scaleMax,
}: {
  model: ForecastModel;
  conditions: Conditions;
  scaleMax: number;
}) {
  const result = predict(model, conditions);
  const block = monthBlock(model, conditions.month);
  const colour = seriesColor(model.system_id);

  return (
    <div className="border-t border-border pt-4">
      <p className="eyebrow flex items-center gap-2">
        <span
          aria-hidden="true"
          className="inline-block h-[2px] w-3.5 shrink-0"
          style={{ background: colour }}
        />
        {cityOf(model.system_id)} · {SYSTEMS[model.system_id].system}
      </p>

      {result.ok ? (
        <>
          <p className="mt-2 text-[clamp(24px,2vw,32px)] font-medium tabular-nums tracking-[-0.02em]">
            {full(Math.round(result.trips))}
            <span className="ml-1.5 text-[13px] font-normal text-muted-foreground">
              trips
            </span>
          </p>
          {/* Shared ceiling across the three panels, so the bars compare. The
              same rule spec 021 settled for the station maps. */}
          <div
            aria-hidden="true"
            className="mt-3 h-1.5 w-full bg-[hsl(var(--rule-2))]"
          >
            <div
              className="h-full"
              style={{
                width: `${Math.min(100, (100 * result.trips) / scaleMax).toFixed(2)}%`,
                background: colour,
              }}
            />
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
            Central 95% of days like this ran{" "}
            <span className="tabular-nums">{compact(Math.round(result.low))}</span>{" "}
            to{" "}
            <span className="tabular-nums">{compact(Math.round(result.high))}</span>.
            The average such day runs{" "}
            <span className="tabular-nums">{full(Math.round(result.mean))}</span>;
            this figure is the typical one. {MONTH_SHORT[conditions.month - 1]}{" "}
            {forecast.reference_year} averaged{" "}
            <span className="tabular-nums">{full(result.monthMean)}</span> a day
            across every kind of weather.
          </p>
        </>
      ) : (
        <>
          <p className="mt-2 text-[clamp(17px,1.4vw,20px)] font-medium leading-snug tracking-[-0.01em]">
            Outside what this model has seen.
          </p>
          <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
            {result.impossible ? (
              <>No prediction: {result.impossible}.</>
            ) : (
              <>
                In {MONTH_SHORT[conditions.month - 1]} this model was fitted on{" "}
                {result.refusals.map((r, i) => (
                  <span key={r.key}>
                    {i > 0 ? ", and on " : ""}
                    <span className="text-foreground">
                      {r.label.toLowerCase()}
                    </span>{" "}
                    between{" "}
                    <span className="tabular-nums">{dec(r.span.min)}</span> and{" "}
                    <span className="tabular-nums">{dec(r.span.max)}</span>
                    {r.unit ? ` ${r.unit}` : ""} — you asked for{" "}
                    <span className="tabular-nums">{dec(r.value)}</span>
                  </span>
                ))}
                . It refuses rather than extrapolating.
              </>
            )}
          </p>
        </>
      )}

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-[12px] text-muted-foreground">
        <dt>R² on trips</dt>
        <dd className="text-right font-mono tabular-nums">
          {model.fit.r2_trips.toFixed(3)}
        </dd>
        <dt>R² on ln(trips)</dt>
        <dd className="text-right font-mono tabular-nums">
          {model.fit.r2_log.toFixed(3)}
        </dd>
        <dt>typical error</dt>
        <dd className="text-right font-mono tabular-nums">
          {model.fit.median_abs_pct_error.toFixed(1)}%
        </dd>
        <dt>days fitted</dt>
        <dd className="text-right font-mono tabular-nums">
          {full(model.fit.days)}
        </dd>
        <dt>
          {MONTH_SHORT[conditions.month - 1]} {forecast.reference_year} days
        </dt>
        <dd className="text-right font-mono tabular-nums">
          {block ? full(block.reference_days) : "none"}
        </dd>
        <dt>every {MONTH_SHORT[conditions.month - 1]} fitted</dt>
        <dd className="text-right font-mono tabular-nums">
          {block ? `${full(block.days)} · ${block.years} yr` : "none"}
        </dd>
        <dt>station distance</dt>
        <dd className="text-right font-mono tabular-nums">
          {dec(model.weather_station.km_from_centroid)} km
        </dd>
      </dl>
    </div>
  );
}

/**
 * The weather-scenario surface: one set of dials, three models, three answers —
 * or a refusal where a model has never seen the day being asked for. The
 * component, the artifact and the registry key keep the older `forecast` name;
 * only the label the reader sees was renamed (spec 030).
 *
 * Everything rendered here comes out of `forecast.json`. The dial bounds, the
 * starting values, the month the section opens on, the fit statistics, the
 * envelope quoted in a refusal, the station distances, even the list of
 * features and their transforms: all of it is read from the artifact rather
 * than typed. That is not fastidiousness — spec 022 shipped three false
 * sentences written from memory of an earlier query, and the fix that held was
 * deriving the sentence from the data it describes.
 */
export function ForecastPanel() {
  const [conditions, setConditions] = useState<Conditions>(() =>
    defaultConditions(busiestMonth()),
  );

  const spans = useMemo(
    () =>
      Object.fromEntries(
        forecast.inputs.map((i) => [i.key, sharedSpan(conditions.month, i.key)]),
      ) as Record<string, Span>,
    [conditions.month],
  );

  const models = SYSTEM_ORDER.map((id) => modelFor(id)).filter(
    (m): m is ForecastModel => Boolean(m),
  );

  // One ceiling for all three bars, fixed: the busiest single day any of the
  // three systems has recorded. Fixed so the bars do not rescale as the dials
  // move — a bar that grows because its own axis shrank is worse than no bar —
  // and an observed maximum rather than an average, because a prediction can
  // exceed any average and would then draw a clipped bar that silently means
  // "at least this much".
  const busiest = busiestDay();
  const scaleMax = busiest.fit.max_daily_trips;
  const smallest = forecast.models.reduce((a, b) =>
    a.fit.max_daily_trips <= b.fit.max_daily_trips ? a : b,
  );

  const set = (patch: Partial<Conditions>) =>
    setConditions((c) => ({ ...c, ...patch }));

  /**
   * Move one dial, keeping the day physical.
   *
   * The two temperature dials are not independent: a day whose low is above its
   * high does not exist, and `predict` rightly refuses it. Left uncoupled, a
   * reader dragging the high down through the low gets three "not a day"
   * refusals — technically correct and completely uninformative, because the
   * thing worth seeing is that the same cold day is ordinary in one city and
   * off the end of another's record. Dragging one past the other therefore
   * carries the other with it, holding the diurnal range, clamped to what the
   * dial itself can reach. Found by driving the built page in a browser; no
   * test asked for it.
   */
  const applyInput = (key: string, value: number) =>
    setConditions((c) => {
      const gap = c.temp_max_c - c.temp_min_c;
      const clamp = (n: number, k: string) => {
        const s = sharedSpan(c.month, k);
        return Math.min(s.max, Math.max(s.min, n));
      };
      if (key === "temp_max_c" && value < c.temp_min_c) {
        return { ...c, temp_max_c: value, temp_min_c: clamp(value - gap, "temp_min_c") };
      }
      if (key === "temp_min_c" && value > c.temp_max_c) {
        return { ...c, temp_min_c: value, temp_max_c: clamp(value + gap, "temp_max_c") };
      }
      return { ...c, [key]: value } as Conditions;
    });

  const weakest = weakestFit();
  const furthest = furthestStation();
  // The month-and-system pair standing on the least history, and the system
  // whose coverage of that same month is deepest. Both derived: naming a city
  // in this sentence and then quoting another's day count is exactly the class
  // of error docs/decisions.md records for spec 022.
  const thinnest = forecast.models
    .flatMap((m) => m.months.map((b) => ({ m, b })))
    .reduce((a, b) => (a.b.years <= b.b.years ? a : b));
  const deepest = forecast.models
    .map((m) => ({ m, b: monthBlock(m, thinnest.b.month) }))
    .filter((x): x is { m: ForecastModel; b: NonNullable<typeof x.b> } => Boolean(x.b))
    .reduce((a, b) => (a.b.days >= b.b.days ? a : b));

  return (
    <div>
      <div className="grid gap-8 border-t border-border pt-6 md:grid-cols-2 lg:grid-cols-3">
        <div className="lg:col-span-3">
          <p className="eyebrow">Month of {forecast.reference_year}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {MONTH_SHORT.map((name, i) => {
              const month = i + 1;
              const on = conditions.month === month;
              return (
                <button
                  key={name}
                  type="button"
                  aria-pressed={on}
                  className={`border px-2.5 py-1 text-[13px] transition-colors ${
                    on
                      ? "border-foreground bg-foreground text-background"
                      : "border-border text-muted-foreground hover:border-foreground hover:text-foreground"
                  }`}
                  // Changing month re-centres every dial on that month's
                  // middling day. Keeping the old values would hand the reader
                  // a 26 °C January and three refusals before they had touched
                  // anything.
                  onClick={() =>
                    setConditions((c) => defaultConditions(month, c.is_weekend))
                  }
                >
                  {name}
                </button>
              );
            })}
          </div>
        </div>

        {forecast.inputs.map((input) => {
          const span = spans[input.key];
          // A dial whose observed range is a single value is not a control.
          // Every August in the record had zero snowfall in all three cities;
          // a slider that cannot move says less than the sentence does.
          if (span.min === span.max) {
            return (
              <p key={input.key} className="self-end pb-1">
                <span className="eyebrow">
                  {input.label}
                  {input.unit ? ` (${input.unit})` : ""}
                </span>
                <span className="mt-2 block text-[13px] leading-relaxed text-muted-foreground">
                  Fixed at <span className="tabular-nums">{dec(span.min)}</span>
                  {input.unit ? ` ${input.unit}` : ""} — no other value has been
                  recorded in {MONTH_SHORT[conditions.month - 1]} in any of the
                  three cities.
                </span>
              </p>
            );
          }
          return (
            <Dial
              key={input.key}
              label={input.label}
              unit={input.unit ?? ""}
              value={(conditions as unknown as Record<string, number>)[input.key]}
              span={span}
              onChange={(n) => applyInput(input.key, n)}
            />
          );
        })}

        <label className="flex items-center gap-2.5 self-end pb-1 text-[14px]">
          <input
            type="checkbox"
            className="h-4 w-4 accent-[hsl(var(--primary))]"
            checked={conditions.is_weekend}
            onChange={(e) => set({ is_weekend: e.target.checked })}
          />
          Weekend
        </label>
      </div>

      <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
        {models.map((m) => (
          <SystemCard
            key={m.system_id}
            model={m}
            conditions={conditions}
            scaleMax={scaleMax}
          />
        ))}
      </div>

      <p className="mt-4 text-[12px] text-muted-foreground">
        The three bars share one ceiling — {full(busiest.fit.max_daily_trips)}{" "}
        trips, the busiest single day in the record, in{" "}
        {cityOf(busiest.system_id)} on {longDate(busiest.fit.max_daily_date)} —
        so a bar means the same length in each panel.{" "}
        {cityOf(smallest.system_id)}&rsquo;s is short because{" "}
        {cityOf(smallest.system_id)}&rsquo;s system is smaller, which is the
        comparison rather than a problem with the chart.
      </p>

      <Note>
        <strong className="font-medium text-foreground">
          What the model is given.
        </strong>{" "}
        {forecast.inputs.map((i, n) => (
          <span key={i.key}>
            {n > 0 ? ", " : ""}
            {i.label.toLowerCase()}
            {i.unit ? ` in ${i.unit}` : ""}{" "}
            <span className="text-foreground">({i.transform})</span>
          </span>
        ))}
        ,{" "}
        {forecast.calendar_inputs.map((i, n) => (
          <span key={i.key}>
            {n > 0 ? ", " : ""}
            {i.label.toLowerCase()}{" "}
            <span className="text-foreground">({i.transform})</span>
          </span>
        ))}
        . The response is {forecast.response}, so every coefficient is a
        proportional effect and the prediction cannot go below zero — a model
        fitted on trips themselves returns negative ridership for a cold wet
        Montreal January, which is not a number worth rendering.{" "}
        {forecast.reference_levels.note}
      </Note>

      <Note>
        <strong className="font-medium text-foreground">
          Most of the parameters are calendar, not weather.
        </strong>{" "}
        {models.map((m, i) => (
          <span key={m.system_id}>
            {i > 0 ? ", " : ""}
            {cityOf(m.system_id)} fits {full(m.fit.parameters)} of them,{" "}
            {full(m.fit.month_levels)} being one level per calendar month
          </span>
        ))}
        . That is the point rather than a cost: with each month carrying its own
        level, the {full(models[0].fit.weather_parameters)} weather and weekend
        coefficients are estimated only from how days differed <em>within</em> a
        month, so they cannot quietly absorb a growing network or a shifting
        season. A version of this model that shared one seasonal shape across
        every year overstated one city&rsquo;s late summer by more than 40%,
        because a season can be strong in one year and weak in the next and an
        additive model has no way to say so. It is also why these coefficients
        say nothing about seasonality: the seasons section above is where that
        question is answered, from its own artifact.
      </Note>

      <Note>
        <strong className="font-medium text-foreground">
          How well these fit, and on what basis.
        </strong>{" "}
        The figures are {forecast.fit_basis}. On the trips scale the three
        models explain{" "}
        {models.map((m, i) => (
          <span key={m.system_id}>
            {i > 0 ? ", " : ""}
            {(100 * m.fit.r2_trips).toFixed(1)}% of {cityOf(m.system_id)}&rsquo;s
            day-to-day variance
          </span>
        ))}
        .{" "}
        <strong className="font-medium text-foreground">
          {cityOf(weakest.system_id)} fits worst
        </strong>{" "}
        and its typical day is still off by{" "}
        {weakest.fit.median_abs_pct_error.toFixed(1)}% — which is the honest
        headline for all three. These are in-sample figures, so each model was
        also refitted {models[0].fit.cv_folds} times with one day in{" "}
        {models[0].fit.cv_folds} held out; on the days it never saw, the
        typical prediction is off by{" "}
        {models.map((m, i) => (
          <span key={m.system_id}>
            {i > 0 ? ", " : ""}
            {m.fit.cv_median_abs_pct_error.toFixed(1)}% ({cityOf(m.system_id)})
          </span>
        ))}
        — within a fraction of a point of the fitted figures, so the weather
        coefficients are not an artifact of the monthly levels. Weather and the
        calendar are most of what moves a riding day, and they are nowhere near
        all of it: nothing here knows about a holiday, a transit strike, a road
        closure, a fare change or a station that was down.
      </Note>

      <Note>
        <strong className="font-medium text-foreground">
          The weather is measured at an airport, not where the bikes are.
        </strong>{" "}
        One Environment and Climate Change Canada station stands in for each
        city, chosen for the length of its record rather than its address:{" "}
        {models.map((m, i) => (
          <span key={m.system_id}>
            {i > 0 ? ", " : ""}
            {m.weather_station.name} for {cityOf(m.system_id)},{" "}
            {dec(m.weather_station.km_from_centroid)} km from its trip-weighted
            centre
          </span>
        ))}
        .{" "}
        {cityOf(furthest.system_id)} is the weakest proxy of the three at{" "}
        {dec(furthest.weather_station.km_from_centroid)} km. All three sit at
        airports on the edge of their region rather than in the dense core each
        system actually runs in, and an airport reading can be colder, windier
        and snowier than the same hour downtown. Every prediction above inherits
        that gap, and none of them corrects for it.
      </Note>

      <Note>
        <strong className="font-medium text-foreground">
          Only days each system was running.
        </strong>{" "}
        A day a system published no trips is absent from its training, never
        entered as a zero: a closed day says nothing about weather, and teaching
        the model otherwise would put a service decision inside a temperature
        coefficient. That is why{" "}
        {cityOf(thinnest.m.system_id)}&rsquo;s{" "}
        {MONTH_SHORT[thinnest.b.month - 1]} weather response rests on{" "}
        {full(thinnest.b.days)} days across {thinnest.b.years} years (
        {thinnest.b.first_year}&ndash;{thinnest.b.last_year}) where{" "}
        {cityOf(deepest.m.system_id)}&rsquo;s has {full(deepest.b.days)} across{" "}
        {deepest.b.years}. Days whose
        weather ECCC did not report are dropped and counted too —{" "}
        {models.map((m, i) => (
          <span key={m.system_id}>
            {i > 0 ? ", " : ""}
            {full(m.excluded_days.no_weather_observation)} in{" "}
            {cityOf(m.system_id)}
          </span>
        ))}{" "}
        — because a missing observation is missing, and 0 °C is a real
        temperature here.
      </Note>
    </div>
  );
}
