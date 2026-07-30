import { describe, expect, it } from "vitest";
import {
  rebalancing, rebalancingFor, headlineRebalancing, movesPerDay, movesPer1k,
  hourlyShare, hourBasis, hourGridShare, hourExtremes,
  dwell, dwellFor, dwellEras, dwellWithheldFor, dwellGridShare, dwellGridShareFor,
  relocatedShare, latestFullDwellYear,
} from "@/lib/data";
import { SYSTEM_ORDER } from "@/lib/systems";

const HOURS = Array.from({ length: 24 }, (_, i) => i);

describe("net flow by hour of day", () => {
  it("covers every hour of every system exactly once", () => {
    for (const id of SYSTEM_ORDER) {
      const hours = rebalancing.hourly
        .filter((r) => r.system_id === id)
        .map((r) => r.hour)
        .sort((a, b) => a - b);
      expect(hours, id).toEqual(HOURS);
    }
  });

  // The identity the whole computation rests on. A trip is one departure and
  // one return, so counting only trips with both ends recorded must cancel
  // exactly across a system's day. It fails the moment an unlinked trip is
  // admitted — which is precisely how spec 022's first net-flow implementation
  // biased every Montreal station amber.
  it("nets to exactly zero over a system's twenty-four hours", () => {
    for (const id of SYSTEM_ORDER) {
      const rows = rebalancing.hourly.filter((r) => r.system_id === id);
      const net = rows.reduce((n, r) => n + r.returns - r.departures, 0);
      expect(net, id).toBe(0);
    }
  });

  // Two independently computed queries have to agree, or the shares the chart
  // draws are a numerator over the wrong denominator.
  it("agrees with the basis it is divided by", () => {
    for (const id of SYSTEM_ORDER) {
      const rows = rebalancing.hourly.filter((r) => r.system_id === id);
      const basis = hourBasis(id)!;
      expect(basis, id).toBeDefined();
      const departures = rows.reduce((n, r) => n + r.departures, 0);
      const returns = rows.reduce((n, r) => n + r.returns, 0);
      expect(departures, `${id} departures`).toBe(basis.linked_trips);
      expect(returns, `${id} returns`).toBe(basis.linked_trips);
      expect(basis.days, id).toBeGreaterThan(0);
      expect(basis.on_hour_grid, id).toBeLessThanOrEqual(basis.linked_trips);
    }
  });

  it("plots shares that also cancel to zero", () => {
    for (const id of SYSTEM_ORDER) {
      const pts = hourlyShare(id);
      expect(pts.length, id).toBe(24);
      const sum = pts.reduce((n, p) => n + p.y, 0);
      expect(Math.abs(sum), id).toBeLessThan(1e-9);
      // A signed series with no sign would mean the chart is drawing the wrong
      // quantity. Every system must have hours on both sides of zero.
      expect(pts.some((p) => p.y < 0), `${id} has an emptying hour`).toBe(true);
      expect(pts.some((p) => p.y > 0), `${id} has a refilling hour`).toBe(true);
    }
  });

  // The page says the deepest hour is the morning commute and derives the hour
  // rather than naming it. Pinned because a shape that lost its commute trough
  // would mean the local-hour bucketing had broken — the exact failure mode
  // that put 8.9M Montreal rows on the wrong local day before spec 012.
  //
  // The fullest hour is NOT always the evening: Toronto's is 09:00, when the
  // wave that left at 08:00 arrives. An earlier version of this test asserted
  // an evening peak for all three and failed on that fact, which is why the
  // section's copy names the hour from the data instead of describing it.
  it("empties every system fastest during the morning departure surge", () => {
    for (const id of SYSTEM_ORDER) {
      const ex = hourExtremes(id)!;
      expect(ex.ebb, `${id} ebb`).toBeGreaterThanOrEqual(6);
      expect(ex.ebb, `${id} ebb`).toBeLessThanOrEqual(9);
    }
  });

  it("lands the morning wave an hour after it leaves, and refills in the evening", () => {
    for (const id of SYSTEM_ORDER) {
      const pts = hourlyShare(id);
      const at = (h: number) => pts.find((p) => p.x === h)!.y;
      expect(at(9), `${id} 09:00 against 08:00`).toBeGreaterThan(at(8));
      const evening = Math.max(...[17, 18, 19, 20, 21].map(at));
      expect(evening, `${id} evening refill`).toBeGreaterThan(0);
    }
  });

  // The qualification the section's copy is built on. Mobi publishes hour-only
  // timestamps; the other two do not. If this ever stopped being true the
  // caveat on the page would be describing a problem that no longer exists.
  it("finds Vancouver alone on an hour-only grid", () => {
    expect(Object.keys(rebalancing.qualified)).toEqual(["van-mobi"]);
    expect(hourGridShare("van-mobi")!).toBeGreaterThan(0.95);
    for (const id of ["mtl-bixi", "tor-bikeshare"] as const) {
      expect(hourGridShare(id)!, id).toBeLessThan(0.001);
    }
  });
});

describe("implied minimum daily rebalancing", () => {
  it("is published for all three systems — the comparable core", () => {
    for (const id of SYSTEM_ORDER) {
      expect(rebalancingFor(id).length, id).toBeGreaterThan(0);
    }
  });

  it("counts only days the system operated, inside a sane calendar", () => {
    for (const r of rebalancing.yearly) {
      expect(r.days, `${r.system_id} ${r.year} days`).toBeGreaterThan(0);
      expect(r.days, `${r.system_id} ${r.year} days`).toBeLessThanOrEqual(366);
      expect(r.months, `${r.system_id} ${r.year} months`).toBeGreaterThan(0);
      expect(r.months, `${r.system_id} ${r.year} months`).toBeLessThanOrEqual(12);
      expect(r.linked_trips, `${r.system_id} ${r.year}`).toBeGreaterThan(0);
      // The imbalance a day leaves cannot exceed the trips that made it: every
      // linked trip contributes at most one departure and one return, so the
      // summed absolute net is bounded by twice the trips.
      expect(r.abs_net, `${r.system_id} ${r.year}`).toBeLessThanOrEqual(2 * r.linked_trips);
    }
  });

  // The headline comparison must be over one window, not three. If a future
  // archive update leaves a system short of a full 2025 this fails rather than
  // quietly comparing eleven months against twelve.
  it("compares all three over one calendar year the archive fully covers", () => {
    expect(rebalancing.headline_year).not.toBeNull();
    const days = new Set<number>();
    for (const id of SYSTEM_ORDER) {
      const r = headlineRebalancing(id)!;
      expect(r, id).toBeDefined();
      expect(r.full_year, id).toBe(true);
      expect(r.months, id).toBe(12);
      days.add(r.days);
    }
    expect(days.size, "all three read over the same number of days").toBe(1);
  });

  // Pinned, because these are the figures the section prints and a reviewer
  // re-derives. They reconcile with the independently measured 2025-onward
  // reference values (Montreal 2,812 / Toronto 1,418 / Vancouver 398 a day)
  // once the window is a calendar year rather than an eighteen-month tail.
  it("reports the measured bound for the headline year", () => {
    const expected: Record<string, number> = {
      "mtl-bixi": 3163,
      "tor-bikeshare": 1587,
      "van-mobi": 405,
    };
    for (const id of SYSTEM_ORDER) {
      const r = headlineRebalancing(id)!;
      expect(Math.round(movesPerDay(r)), id).toBe(expected[id]);
    }
  });

  // The finding the per-1,000 chart exists to show, and the one a raw
  // moves-per-day reading inverts: Vancouver is the smallest system and the
  // most lopsided per trip.
  it("ranks Vancouver highest per 1,000 trips and lowest in absolute moves", () => {
    const per1k = SYSTEM_ORDER.map((id) => movesPer1k(headlineRebalancing(id)!));
    const perDay = SYSTEM_ORDER.map((id) => movesPerDay(headlineRebalancing(id)!));
    const van = SYSTEM_ORDER.indexOf("van-mobi");
    expect(Math.max(...per1k)).toBe(per1k[van]);
    expect(Math.min(...perDay)).toBe(perDay[van]);
  });

  it("marks every year the archive clips, and no year it covers", () => {
    for (const id of SYSTEM_ORDER) {
      const years = rebalancingFor(id);
      const clipped = years.filter((r) => !r.full_year).map((r) => r.year);
      // Only the edges of an archive can be clipped. A hole in the middle
      // would mean a year vanished from the ingest.
      const bounds = [years[0].year, years[years.length - 1].year];
      for (const y of clipped) expect(bounds, `${id} ${y}`).toContain(y);
    }
  });
});

describe("per-bike dwell", () => {
  it("excludes Montreal with a stated reason, and never as an absence", () => {
    expect(dwellFor("mtl-bixi")).toHaveLength(0);
    const un = dwell.unsupported["mtl-bixi"];
    expect(un).toBeDefined();
    expect(un.reason ?? "").not.toHaveLength(0);
    expect(un.display).toBe("not published");
    // ...and the same system is fully present in the comparable metric, which
    // is the entire point of splitting the registry entry in two.
    expect(rebalancingFor("mtl-bixi").length).toBeGreaterThan(0);
  });

  it("keeps every interval inside the era that produced it", () => {
    for (const r of dwell.series) {
      expect(r.year, `${r.system_id} ${r.year}`).toBeGreaterThanOrEqual(r.era_first_year);
      expect(r.year, `${r.system_id} ${r.year}`).toBeLessThanOrEqual(r.era_last_year);
    }
  });

  // The boundary that matters. Vancouver's 2021-2023 are withheld; a chain
  // allowed to step over them would pair a 2020 return with a 2024 departure
  // and report a three-year dwell as if it were one.
  it("never reports a year it withheld", () => {
    for (const id of SYSTEM_ORDER) {
      const published = new Set(dwellFor(id).map((r) => r.year));
      for (const w of dwellWithheldFor(id)) {
        expect(published.has(w.year), `${id} ${w.year}`).toBe(false);
        expect(w.with_bike_id / w.trips, `${id} ${w.year} coverage`)
          .toBeLessThan(dwell.min_bike_id_coverage);
      }
    }
  });

  it("splits eras at the withheld years rather than spanning them", () => {
    expect(dwellEras("mtl-bixi")).toHaveLength(0);
    expect(dwellEras("tor-bikeshare")).toHaveLength(1);
    // Two blocks, because 2021-2023 sit between them.
    const van = dwellEras("van-mobi");
    expect(van).toHaveLength(2);
    expect(van[1].first - van[0].last).toBeGreaterThan(1);
    const withheld = dwellWithheldFor("van-mobi").map((w) => w.year);
    for (let y = van[0].last + 1; y < van[1].first; y += 1) {
      expect(withheld, `van-mobi ${y}`).toContain(y);
    }
  });

  it("publishes a monotonic, non-negative distribution", () => {
    for (const r of dwell.series) {
      const tag = `${r.system_id} ${r.year}`;
      expect(r.intervals, tag).toBeGreaterThan(0);
      expect(r.p25_s, tag).toBeGreaterThanOrEqual(0);
      expect(r.p25_s, tag).toBeLessThanOrEqual(r.median_s);
      expect(r.median_s, tag).toBeLessThanOrEqual(r.p75_s);
      expect(r.on_hour_grid, tag).toBeLessThanOrEqual(r.intervals);
      // Relocations are excluded from the quantiles, so they are a separate
      // count and must not be folded into the interval total.
      expect(relocatedShare(r), tag).toBeGreaterThan(0);
      expect(relocatedShare(r), tag).toBeLessThan(0.5);
      // Rows recorded before the return they follow are a data defect, counted
      // rather than hidden — but they must stay negligible.
      expect(r.out_of_order / r.intervals, tag).toBeLessThan(0.001);
    }
  });

  // The relocation share the page quotes must come from a whole year. Caught
  // in the headed browser: it read off the newest row, which is the archive's
  // trailing stub — Toronto's January-to-March 2026 — and printed a winter
  // figure under the present tense.
  it("quotes the relocation share from a complete year", () => {
    for (const id of SYSTEM_ORDER) {
      const rows = dwellFor(id);
      if (!rows.length) continue;
      const quoted = latestFullDwellYear(id)!;
      expect(quoted.months, `${id} ${quoted.year}`).toBe(12);
      // ...and it must still be the most recent complete one.
      const newerFull = rows.filter((r) => r.months === 12 && r.year > quoted.year);
      expect(newerFull, id).toHaveLength(0);
    }
  });

  // Vancouver's quartiles are hour boundaries because its source has no finer
  // value, and the page says so from this number. Toronto's are not, so the
  // caveat must not appear under Toronto.
  it("separates the hour-only system from the minute-precision one", () => {
    for (const r of dwellFor("van-mobi")) {
      expect(dwellGridShare(r), `van-mobi ${r.year}`).toBeGreaterThan(0.85);
      expect(r.median_s % 3600, `van-mobi ${r.year} median`).toBe(0);
    }
    for (const r of dwellFor("tor-bikeshare")) {
      expect(dwellGridShare(r), `tor ${r.year}`).toBeLessThan(0.1);
    }
    // The figure the page prints qualifies the whole interval count beside it,
    // so it has to be measured over the whole set rather than over one year.
    expect(dwellGridShareFor("van-mobi")).toBeGreaterThan(0.9);
    expect(dwellGridShareFor("tor-bikeshare")).toBeLessThan(0.1);
  });
});
