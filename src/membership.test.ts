import { describe, expect, it } from "vitest";
import { membership, membershipFor, memberShare } from "@/lib/data";
import { SYSTEM_ORDER } from "@/lib/systems";

const all = [...membership.series, ...membership.partial];

describe("membership artifact", () => {
  it("keeps the comparable pair and the partial city apart", () => {
    const comparable = new Set(membership.series.map((r) => r.system_id));
    const partial = new Set(membership.partial.map((r) => r.system_id));
    // The whole design rests on these being disjoint: a system in both would
    // be drawn as a comparable column AND as the exception to one.
    for (const id of partial) expect(comparable.has(id), id).toBe(false);
    expect(comparable.size).toBeGreaterThan(1);
    expect(partial.size).toBeGreaterThan(0);
  });

  it("declares why each partial system is partial", () => {
    for (const id of new Set(membership.partial.map((r) => r.system_id))) {
      const note = membership.partial_note[id];
      expect(note, `no partial_note for ${id}`).toBeDefined();
      // The page renders both; an empty one would print a bare city name.
      expect(note.display?.length ?? 0).toBeGreaterThan(0);
      expect(note.reason?.length ?? 0).toBeGreaterThan(0);
      expect(note.partial_until).toBeTruthy();
    }
  });

  it("stops the partial series where the source stops", () => {
    for (const [id, note] of Object.entries(membership.partial_note)) {
      const months = membership.partial
        .filter((r) => r.system_id === id)
        .map((r) => r.month)
        .sort();
      expect(months.length).toBeGreaterThan(0);
      // A month past the declared end would mean the label is a fiction.
      expect(months[months.length - 1] <= `${note.partial_until}-12`).toBe(true);
    }
  });

  it("never lets a group total exceed the month's trips", () => {
    for (const r of all) {
      expect(r.member + r.casual + r.other + r.unlabelled, r.month).toBeLessThanOrEqual(
        r.trips,
      );
      for (const n of [r.member, r.casual, r.other, r.unlabelled, r.trips]) {
        expect(Number.isInteger(n)).toBe(true);
        expect(n).toBeGreaterThanOrEqual(0);
      }
    }
  });

  it("computes the share against labelled trips, not all trips", () => {
    // The distinction matters most where labelling is weakest. If the
    // denominator were `trips`, Vancouver's share would be dragged down by its
    // ~1% unlabelled rate rather than by anything about its riders.
    const r = all.find((x) => x.unlabelled > 0 && x.member + x.casual > 0)!;
    expect(r, "no month with unlabelled trips to test against").toBeDefined();
    expect(memberShare(r)).toBeCloseTo(r.member / (r.member + r.casual), 10);
    expect(memberShare(r)).not.toBeCloseTo(r.member / r.trips, 6);
  });

  it("returns null rather than 0 for a month with no labels at all", () => {
    expect(
      memberShare({
        system_id: "van-mobi", month: "2020-01", member: 0, casual: 0,
        other: 0, unlabelled: 100, trips: 100,
      }),
    ).toBeNull();
  });

  it("gives every share a plausible value", () => {
    for (const r of all) {
      const share = memberShare(r);
      if (share === null) continue;
      expect(share, `${r.system_id} ${r.month}`).toBeGreaterThan(0);
      expect(share, `${r.system_id} ${r.month}`).toBeLessThanOrEqual(1);
    }
  });

  // A bug that zeroed one group would still satisfy every bound above.
  it("finds both members and casual riders in every system", () => {
    for (const id of new Set(all.map((r) => r.system_id))) {
      const rs = all.filter((r) => r.system_id === id);
      expect(rs.reduce((n, r) => n + r.member, 0), `${id} members`).toBeGreaterThan(0);
      expect(rs.reduce((n, r) => n + r.casual, 0), `${id} casual`).toBeGreaterThan(0);
    }
  });

  it("orders each system's months", () => {
    for (const id of new Set(all.map((r) => r.system_id))) {
      const months = all.filter((r) => r.system_id === id).map((r) => r.month);
      expect(months, id).toEqual([...months].sort());
    }
  });

  it("covers every comparable system in SYSTEM_ORDER order-compatible ids", () => {
    for (const r of membership.series) {
      expect(SYSTEM_ORDER, `unknown system ${r.system_id}`).toContain(r.system_id);
    }
  });
});
