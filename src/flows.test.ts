import { describe, expect, it } from "vitest";
import stationsJson from "@/data/generated/stations.json";
import { flows, flowsFor, concentration, flowRate, type StationPin } from "@/lib/data";
import { SYSTEM_ORDER } from "@/lib/systems";

const pins = (stationsJson as { stations: StationPin[] }).stations;

describe("flow artifact", () => {
  it("covers every system", () => {
    for (const id of SYSTEM_ORDER) expect(flowsFor(id), id).toBeDefined();
  });

  // Concentration is the cross-city comparison the section makes, so its
  // internal consistency is the thing worth pinning: a wider net can never
  // carry less traffic than a narrower one.
  it("has monotonic concentration bands within each system", () => {
    for (const id of SYSTEM_ORDER) {
      const f = flowsFor(id)!;
      expect(f.top_10, id).toBeLessThanOrEqual(f.top_100);
      expect(f.top_100, id).toBeLessThanOrEqual(f.top_1000);
      expect(f.top_1000, id).toBeLessThanOrEqual(f.linked_trips);
    }
  });

  it("never claims more pairs shown than exist", () => {
    for (const id of SYSTEM_ORDER) {
      const f = flowsFor(id)!;
      expect(f.pairs_total, id).toBeGreaterThan(flows.top_pairs_shown);
      expect(f.shown_trips, id).toBeLessThanOrEqual(f.linked_trips);
    }
  });

  it("keeps round trips and unlinked trips inside the total", () => {
    for (const id of SYSTEM_ORDER) {
      const f = flowsFor(id)!;
      expect(f.round_trips, id).toBeLessThanOrEqual(f.trips);
      expect(f.no_return_station, id).toBeLessThanOrEqual(f.trips);
      // Every linked trip plus every trip with no return cannot exceed the
      // total; the remainder is trips with no departure station.
      expect(f.linked_trips + f.no_return_station, id).toBeLessThanOrEqual(f.trips);
    }
  });

  it("ships exactly the promised number of named pairs per system", () => {
    for (const id of SYSTEM_ORDER) {
      const p = flows.pairs.filter((x) => x.s === id);
      expect(p.length, id).toBe(flows.top_pairs_shown);
      for (const pair of p) {
        // Bare keys would render as blank rows — the page shows names.
        expect(pair.a.length, `${id} origin name`).toBeGreaterThan(0);
        expect(pair.b.length, `${id} destination name`).toBeGreaterThan(0);
        expect(pair.n).toBeGreaterThan(0);
        // The round-trip flag must agree with the names it is drawn from,
        // since the page renders "X and back" off it.
        if (pair.r) expect(pair.a).toBe(pair.b);
      }
    }
  });

  it("orders pairs by descending trips", () => {
    for (const id of SYSTEM_ORDER) {
      const n = flows.pairs.filter((x) => x.s === id).map((x) => x.n);
      expect(n, id).toEqual([...n].sort((a, b) => b - a));
    }
  });
});

describe("net flow per station", () => {
  it("gives every shipped station an integer net flow", () => {
    for (const p of pins) {
      expect(Number.isInteger(p.f), `${p.s} ${p.n}`).toBe(true);
    }
  });

  // |net| can never exceed total events: a station cannot give out more bikes
  // than the events that touched it. This catches a departures/returns mix-up
  // or a join that fanned rows out.
  it("never reports a net flow larger than the station's own activity", () => {
    for (const p of pins) {
      expect(Math.abs(p.f), `${p.s} ${p.n}`).toBeLessThanOrEqual(p.t);
      expect(Math.abs(flowRate(p))).toBeLessThanOrEqual(1);
    }
  });

  // Net flow counts only trips with both ends recorded, so every trip is one
  // departure and one return and the whole system must cancel to exactly zero.
  //
  // The first version of this metric counted every departure but only the
  // returns it could resolve, leaving a phantom -1 at the origin of each
  // unreturned trip — 272,088 of them in Montreal, enough to bias that entire
  // map amber for a reason that was a gap in the data rather than a movement
  // of bikes. The test then codified the bug by asserting the sum was
  // negative. Only stations shipped to the site are visible here, so the
  // subtotal is bounded rather than zero; the exact identity is checked in the
  // pipeline, where every station is in scope.
  it("keeps the shown subtotal far smaller than the system's own traffic", () => {
    for (const id of SYSTEM_ORDER) {
      const f = flowsFor(id)!;
      const shown = pins.filter((p) => p.s === id).reduce((n, p) => n + p.f, 0);
      // Unmapped and below-threshold stations hold the complement. If that
      // complement ever approached the system's whole volume, the join behind
      // `f` would have fanned out.
      expect(Math.abs(shown) / f.linked_trips, id).toBeLessThan(0.02);
    }
  });

  it("finds real imbalance rather than a uniformly flat field", () => {
    for (const id of SYSTEM_ORDER) {
      const rates = pins.filter((p) => p.s === id).map((p) => Math.abs(flowRate(p)));
      const imbalanced = rates.filter((r) => r > 0.05).length;
      // If a bug zeroed the flows this would be 0 and the map would be all
      // grey while still passing every bound check above.
      expect(imbalanced, `${id} stations over 5% imbalance`).toBeGreaterThan(20);
    }
  });
});

describe("concentration", () => {
  it("is a share between 0 and 1", () => {
    for (const id of SYSTEM_ORDER) {
      for (const n of [10, 100, 1000] as const) {
        const c = concentration(id, n)!;
        expect(c, `${id} top${n}`).toBeGreaterThan(0);
        expect(c, `${id} top${n}`).toBeLessThanOrEqual(1);
      }
    }
  });

  // The section's central claim: the same "top N" means very different things
  // in different cities. If this ever stops holding, the prose has to change.
  it("differs enough between systems to justify the claim the page makes", () => {
    const top1000 = SYSTEM_ORDER.map((id) => concentration(id, 1000)!);
    expect(Math.max(...top1000) / Math.min(...top1000)).toBeGreaterThan(2);
  });
});
