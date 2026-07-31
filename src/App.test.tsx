import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import {
  forecast, busiestMonth, defaultConditions, modelFor, monthBlock, predict,
} from "@/lib/forecast";
import { full, MONTH_SHORT } from "@/lib/format";
import {
  ebikeShare, meta, tripsMonthly,
  dwell, dwellFor, dwellWithheldFor, headlineRebalancing, movesPerDay,
  rebalancing, hourExtremes,
} from "@/lib/data";
import { SYSTEM_ORDER, cityOf } from "@/lib/systems";

describe("App", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
    localStorage.clear();
  });

  it("renders the brand and all three systems", () => {
    render(<App />);
    expect(screen.getByText("Trans-Canada Bikeshare")).toBeInTheDocument();
    for (const city of ["Vancouver", "Montreal", "Toronto"]) {
      expect(screen.getAllByText(new RegExp(city)).length).toBeGreaterThan(0);
    }
  });

  it("toggles the theme and reflects it in aria-pressed", async () => {
    const user = userEvent.setup();
    render(<App />);
    const toggle = screen.getByRole("button", { name: /switch to dark theme/i });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  // This test previously pinned the sentence "comparisons below are restricted
  // to 2017 onward" — which was FALSE: the trips and stations charts render
  // each system's full range. A test that locks in a false claim is worse than
  // no test, so this now checks the claim against the data it describes.
  it("does not claim a restriction the charts do not apply", () => {
    render(<App />);
    const overview = document.getElementById("overview")!;
    expect(overview.textContent).toMatch(new RegExp(meta.common_window_first_year));
    expect(overview.textContent).not.toMatch(/restricted to/i);

    const earliest = tripsMonthly
      .map((r) => r.month)
      .sort()[0]
      .slice(0, 4);
    // If a future change really does crop the charts to the common window,
    // this fails and the copy should be revisited deliberately.
    expect(Number(earliest)).toBeLessThan(Number(meta.common_window_first_year));
  });

  it("states BIXI's winter operation as the data has it", () => {
    render(<App />);
    const trips = document.getElementById("trips")!;
    const winter = tripsMonthly.filter(
      (r) => r.system_id === "mtl-bixi" && ["12", "01", "02"].includes(r.month.slice(5)),
    );
    // BIXI runs year-round now; copy claiming an unqualified closure is stale.
    expect(winter.length).toBeGreaterThan(0);
    expect(trips.textContent).toMatch(/year-round since/i);
  });

  // The load-bearing honesty test. E-bike share is a two-city metric because
  // BIXI publishes no bike-type field in any era. If a future change starts
  // rendering it as a three-city comparison, or drops the explanation, this
  // fails — which is the whole point of shipping the gap as data.
  it("labels every system that cannot support e-bike share, with a reason", () => {
    render(<App />);
    const section = document.getElementById("ebikes")!;
    const unsupported = Object.keys(ebikeShare.unsupported);
    expect(unsupported.length).toBeGreaterThan(0);
    for (const id of unsupported) {
      const city = meta.systems.find((s) => s.system_id === id)!.city;
      expect(within(section).getByText(new RegExp(city))).toBeInTheDocument();
      expect(section.textContent).toMatch(/not published/i);
      expect(ebikeShare.unsupported[id].reason ?? "").not.toHaveLength(0);
    }
    // ...and it must not be drawn as a series.
    const plotted = new Set(ebikeShare.series.map((r) => r.system_id));
    for (const id of unsupported) expect(plotted.has(id as never)).toBe(false);
  });

  // Spec 030: the section moves a day's weather inside a calendar month each
  // system has already ridden through, and its holdout keeps those month levels
  // in training — so "Forecast" claimed more than was computed. The label
  // changed; the anchor deliberately did not, because #forecast deep links are
  // already published, and neither did the artifact, the registry key or the
  // component. This test pins both halves of that split.
  it("labels the section weather scenario and keeps the published anchor", () => {
    render(<App />);
    const nav = document.querySelector<HTMLElement>('nav[aria-label="Sections"]')!;
    expect(
      within(nav).getByRole("link", { name: "Weather scenario" }),
    ).toHaveAttribute("href", "#forecast");
    expect(nav.textContent).not.toMatch(/forecast/i);

    const section = document.getElementById("forecast")!;
    expect(section.textContent).toMatch(/weather scenario/i);
    // The one surviving "forecast" in the copy is the artifact's own statement
    // that this is not one. Any second occurrence is a missed rename.
    expect(section.textContent!.match(/forecast/gi) ?? []).toHaveLength(1);
    expect(section.textContent).toContain("not a forecast of an unseen month");
  });

  // The weather-scenario section renders three predictions from published
  // coefficients. These check what a headed browser cannot assert cheaply: that
  // the number on screen is the one the model produces, and that the section
  // carries the caveat the ECCC licence and spec 013 both require.
  it("renders the prediction each model actually produces", () => {
    render(<App />);
    const section = document.getElementById("forecast")!;
    const conditions = defaultConditions(busiestMonth());
    for (const model of forecast.models) {
      const result = predict(model, conditions);
      expect(result.ok, model.system_id).toBe(true);
      if (!result.ok) return;
      expect(section.textContent, model.system_id).toContain(
        full(Math.round(result.trips)),
      );
    }
  });

  it("moves the prediction when the reader moves the weather", () => {
    render(<App />);
    const section = document.getElementById("forecast")!;
    const before = section.textContent!;
    const slider = within(section).getByLabelText(/daily high in/i);
    const month = busiestMonth();
    // The coldest high every model has seen in this month: inside all three
    // envelopes, and above the starting low, so the dials do not couple and the
    // expected conditions here are exactly the ones on screen.
    const target = Math.max(
      ...forecast.models.map((m) => monthBlock(m, month)!.ranges.temp_max_c.min),
    );
    const conditions = { ...defaultConditions(month), temp_max_c: target };
    expect(conditions.temp_min_c).toBeLessThan(target);

    fireEvent.change(slider, { target: { value: String(target) } });
    expect(section.textContent).not.toBe(before);

    for (const model of forecast.models) {
      const result = predict(model, conditions);
      // Not `continue` on a refusal: a loop that skips every system asserts
      // nothing and passes, which is how this test quietly stopped checking
      // anything when the dials were first coupled.
      expect(result.ok, model.system_id).toBe(true);
      if (!result.ok) return;
      expect(section.textContent, model.system_id).toContain(
        full(Math.round(result.trips)),
      );
    }
  });

  // A model asked for a day outside its training range must say so rather than
  // extrapolate. Vancouver's January has never been as cold as Montreal's, so
  // one set of dials produces an answer in one city and a refusal in another.
  it("refuses outside the envelope and names the range it was fitted on", () => {
    render(<App />);
    const section = document.getElementById("forecast")!;
    fireEvent.click(within(section).getByRole("button", { name: MONTH_SHORT[0] }));

    const coldest = modelFor("van-mobi")!;
    const span = monthBlock(coldest, 1)!.ranges.temp_max_c;
    fireEvent.change(within(section).getByLabelText(/daily high in/i), {
      target: { value: String(span.min - 5) },
    });
    expect(section.textContent).toMatch(/outside what this model has seen/i);
    expect(section.textContent).toMatch(/refuses rather than extrapolating/i);
    // The stated range must be the model's own, not a rounded retelling.
    expect(section.textContent).toContain(span.max.toFixed(1));
  });

  // Found by driving the built page, not by a failing assertion: dragging the
  // daily high below the daily low makes a day that cannot exist, and all three
  // models then refuse for that reason instead of showing the difference
  // between the cities, which is the only thing the control is there to show.
  it("keeps the day physical when one temperature dial passes the other", () => {
    render(<App />);
    const section = document.getElementById("forecast")!;
    fireEvent.click(within(section).getByRole("button", { name: MONTH_SHORT[0] }));
    const floor = Math.min(
      ...forecast.models.map((m) => monthBlock(m, 1)!.ranges.temp_max_c.min),
    );
    fireEvent.change(within(section).getByLabelText(/daily high in/i), {
      target: { value: String(floor) },
    });
    expect(section.textContent).not.toMatch(/not a day/i);
    const low = within(section).getByLabelText(/daily low in/i) as HTMLInputElement;
    expect(Number(low.value)).toBeLessThanOrEqual(floor);
    // The coldest city still answers where the mildest one cannot.
    const cold = forecast.models.reduce((a, b) =>
      monthBlock(a, 1)!.ranges.temp_max_c.min <= monthBlock(b, 1)!.ranges.temp_max_c.min
        ? a : b,
    );
    expect(monthBlock(cold, 1)!.ranges.temp_max_c.min).toBe(floor);
  });

  it("carries the airport-station caveat wherever a weather number appears", () => {
    render(<App />);
    const section = document.getElementById("forecast")!;
    for (const model of forecast.models) {
      expect(section.textContent, model.system_id).toContain(
        model.weather_station.name,
      );
      expect(section.textContent, model.system_id).toContain(
        `${model.weather_station.km_from_centroid.toFixed(1)} km`,
      );
    }
    expect(section.textContent).toMatch(/airport, not where the bikes are/i);
    expect(section.textContent).toMatch(/in-sample/i);
  });

  // The operational signals are the ones most easily read as measurements.
  // The bound has to travel with the number, in the section, not in a footnote
  // somewhere below it.
  it("labels implied rebalancing as a lower bound beside the figure", () => {
    render(<App />);
    const ops = document.getElementById("ops")!;
    expect(ops.textContent).toMatch(/lower bound/i);
    expect(ops.textContent).toMatch(/fewest moves a day/i);
    // The words the caveat turns on, carried from the registry rather than
    // written here: an overnight reset assumed, intra-day moves ignored.
    expect(ops.textContent).toContain(rebalancing.caveat);
  });

  it("prints the rebalancing figure the artifact computes, for all three", () => {
    render(<App />);
    const ops = document.getElementById("ops")!;
    for (const id of SYSTEM_ORDER) {
      const r = headlineRebalancing(id)!;
      const printed = Math.round(movesPerDay(r)).toLocaleString("en-CA");
      expect(ops.textContent, `${id} ${printed}`).toContain(printed);
    }
  });

  it("names each system's emptiest hour from the data, not from prose", () => {
    render(<App />);
    const ops = document.getElementById("ops")!;
    for (const id of SYSTEM_ORDER) {
      const ex = hourExtremes(id)!;
      const label = `${String(ex.ebb).padStart(2, "0")}:00`;
      expect(ops.textContent, `${cityOf(id)} ${label}`).toContain(label);
    }
  });

  // The membership discipline, applied to dwell: a system that cannot support
  // it is named and explained, never quietly missing. The same section carries
  // that system as a full column of the comparable metric above.
  it("marks the system with no bike ids as not published, with a reason", () => {
    render(<App />);
    const ops = document.getElementById("ops")!;
    const unsupported = Object.keys(dwell.unsupported);
    expect(unsupported.length).toBeGreaterThan(0);
    for (const id of unsupported) {
      expect(dwellFor(id as never)).toHaveLength(0);
      expect(ops.textContent).toContain(dwell.unsupported[id].reason);
      expect(within(ops).getAllByText(new RegExp(cityOf(id))).length).toBeGreaterThan(0);
    }
    expect(ops.textContent).toMatch(/not published/i);
  });

  it("states every withheld dwell year rather than skipping it", () => {
    render(<App />);
    const ops = document.getElementById("ops")!;
    for (const id of SYSTEM_ORDER) {
      for (const w of dwellWithheldFor(id)) {
        expect(ops.textContent, `${id} ${w.year}`).toContain(String(w.year));
      }
    }
  });

  it("reports the out-of-sample error beside the in-sample one", () => {
    render(<App />);
    const section = document.getElementById("forecast")!;
    // The number must be the artifact's, not prose.
    for (const m of forecast.models) {
      expect(section.textContent).toContain(
        `${m.fit.cv_median_abs_pct_error.toFixed(1)}%`,
      );
    }
    expect(section.textContent).toMatch(/one day in 5 held out/i);
  });

  // The disclaimer has to name the operators, not only the Crown: a reader
  // seeing three systems compared could reasonably assume one of them ran it.
  it("declares no affiliation with any operator or with the government", () => {
    render(<App />);
    const disclaimer = screen.getByText(/not affiliated with or endorsed by/i);
    expect(disclaimer).toBeInTheDocument();
    for (const name of [
      "Mobi by Rogers",
      "BIXI Montréal",
      "Bike Share Toronto",
      "Government of Canada",
    ]) {
      expect(disclaimer.textContent).toContain(name);
    }
  });
});
