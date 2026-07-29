import { describe, expect, it } from "vitest";
import stationsJson from "@/data/generated/stations.json";
import { stationsMeta, omittedFor } from "@/lib/data";
import { SYSTEM_ORDER, SYSTEMS, resolvedSeriesColor, seriesColor } from "@/lib/systems";

const pins = (stationsJson as { stations: { s: string; y: number; x: number; t: number; n: string }[] })
  .stations;

// Rough bounding boxes. Wide enough not to be brittle, tight enough that a
// coordinate landing in the wrong city — or at (0,0), the classic failure when
// a missing position is treated as a number — fails loudly.
const BOX: Record<string, { lat: [number, number]; lon: [number, number] }> = {
  "van-mobi": { lat: [49.15, 49.35], lon: [-123.3, -122.9] },
  // BIXI is not only Montreal. It runs 25 stations in SHERBROOKE, ~150 km
  // east, plus South Shore towns — verified against real street names in the
  // GBFS feed (U. de Sherbrooke, Cégep de Sherbrooke, Galt Ouest). An earlier
  // version of this box rejected them as bad coordinates; they are real.
  "mtl-bixi": { lat: [45.3, 45.8], lon: [-74.05, -71.8] },
  "tor-bikeshare": { lat: [43.5, 43.9], lon: [-79.7, -79.1] },
};

describe("station artifact", () => {
  it("has stations for every system", () => {
    for (const id of SYSTEM_ORDER) {
      expect(pins.filter((p) => p.s === id).length).toBeGreaterThan(100);
    }
  });

  it("places every station inside its own city", () => {
    for (const p of pins) {
      const box = BOX[p.s];
      expect(box, `unknown system ${p.s}`).toBeDefined();
      expect(p.y).toBeGreaterThanOrEqual(box.lat[0]);
      expect(p.y).toBeLessThanOrEqual(box.lat[1]);
      expect(p.x).toBeGreaterThanOrEqual(box.lon[0]);
      expect(p.x).toBeLessThanOrEqual(box.lon[1]);
    }
  });

  it("never ships a station without a name", () => {
    for (const p of pins) expect(p.n?.length ?? 0).toBeGreaterThan(0);
  });

  // Pin the literal, not `stationsMeta.min_lifetime_events`. Comparing the
  // artifact to a constant from the same publish run restates it rather than
  // checking it: move the threshold in publish.py and both sides move together
  // while the spec and the sentence on the page quietly stop being true.
  it("ships only stations at or above the declared 100-event threshold", () => {
    expect(stationsMeta.min_lifetime_events).toBe(100);
    for (const p of pins) expect(p.t).toBeGreaterThanOrEqual(100);
  });
});

describe("map dot colour", () => {
  // Spec 021 first shipped with `hsl(var(--series-van))` handed to MapLibre,
  // which parses colours in JavaScript and cannot resolve a custom property.
  // It rejected the whole layer without throwing, so all three maps added
  // their GeoJSON source, drew zero dots, and captioned themselves "Select a
  // station". Nothing in the suite noticed.
  it("never hands MapLibre a CSS custom property", () => {
    for (const id of SYSTEM_ORDER) {
      document.documentElement.style.setProperty(SYSTEMS[id].varName, "205 74% 38%");
      const colour = resolvedSeriesColor(id);
      expect(colour, `no resolved colour for ${id}`).not.toBeNull();
      expect(colour).not.toContain("var(");
      // MapLibre accepts CSS colour syntax it can parse without the cascade.
      expect(colour).toMatch(/^hsl\([\d.\s%]+\)$/);
    }
  });

  it("still returns the var() form for SVG, which the browser does resolve", () => {
    for (const id of SYSTEM_ORDER) expect(seriesColor(id)).toContain("var(");
  });

  it("returns null rather than inventing a colour when the token is absent", () => {
    for (const id of SYSTEM_ORDER) {
      document.documentElement.style.removeProperty(SYSTEMS[id].varName);
    }
    expect(resolvedSeriesColor("van-mobi")).toBeNull();
  });

  // The map cannot show a station with no coordinates. The page must therefore
  // state how many it is not showing — otherwise a reader takes the dots for
  // the whole network, which for Montreal would understate it by hundreds.
  it("accounts for every station the map omits", () => {
    for (const id of SYSTEM_ORDER) {
      const o = omittedFor(id);
      expect(o, `no omission record for ${SYSTEMS[id].city}`).toBeDefined();
      const shown = pins.filter((p) => p.s === id).length;
      expect(shown + o!.no_coordinates + o!.below_threshold).toBe(o!.total);
    }
  });
});
