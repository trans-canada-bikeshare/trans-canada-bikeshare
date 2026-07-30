import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LineChart, type Series } from "@/components/charts/LineChart";

/** The chart's own padding, from LineChart.tsx. A point drawn outside this box
 *  is off the plot, which is what an unsigned domain does to a negative value. */
const PAD = { top: 12, bottom: 26 };
const H = 260;

function series(points: { x: number; y: number }[]): Series[] {
  return [{ id: "a", label: "A", color: "hsl(1 2% 3%)", points }];
}

/** Every y coordinate in every drawn path. */
function plottedY(container: HTMLElement): number[] {
  return [...container.querySelectorAll("path")].flatMap((p) =>
    [...(p.getAttribute("d") ?? "").matchAll(/[ML]([\d.-]+) ([\d.-]+)/g)].map((m) =>
      Number(m[2]),
    ),
  );
}

describe("LineChart", () => {
  // The default has to be untouched: every other chart on this site relies on
  // a 0..max domain and would silently rescale if `signed` leaked into it.
  it("keeps a zero-based domain by default", () => {
    const { container } = render(
      <LineChart series={series([{ x: 0, y: 0 }, { x: 1, y: 100 }])}
                 xLabel={String} yLabel={(y) => y.toFixed(0)} />,
    );
    const labels = [...container.querySelectorAll("text")].map((t) => t.textContent);
    expect(labels).toContain("0");
    expect(labels).toContain("50");
    expect(labels).toContain("100");
    expect(labels).not.toContain("-100");
  });

  it("opens the domain below zero when signed, symmetrically about it", () => {
    const { container } = render(
      <LineChart signed
                 series={series([{ x: 0, y: -40 }, { x: 1, y: 100 }])}
                 xLabel={String} yLabel={(y) => y.toFixed(0)} />,
    );
    const labels = [...container.querySelectorAll("text")].map((t) => t.textContent);
    // Symmetric: an imbalance of 40 in either direction must sit the same
    // distance from the axis, so the floor mirrors the ceiling.
    expect(labels).toContain("-100");
    expect(labels).toContain("0");
    expect(labels).toContain("100");
  });

  // The failure this prop exists to prevent. On the unsigned domain a negative
  // value maps below the baseline and is drawn outside the plot box entirely.
  it("draws negative values inside the plot rather than below it", () => {
    const points = [{ x: 0, y: -40 }, { x: 1, y: 100 }];
    const unsigned = render(
      <LineChart series={series(points)} xLabel={String} />,
    );
    const signed = render(
      <LineChart signed series={series(points)} xLabel={String} />,
    );
    expect(Math.max(...plottedY(unsigned.container))).toBeGreaterThan(H - PAD.bottom);
    for (const y of plottedY(signed.container)) {
      expect(y).toBeGreaterThanOrEqual(PAD.top);
      expect(y).toBeLessThanOrEqual(H - PAD.bottom);
    }
  });

  it("draws the zero line at full rule weight when signed", () => {
    const { container } = render(
      <LineChart signed
                 series={series([{ x: 0, y: -1 }, { x: 1, y: 1 }])}
                 xLabel={String} />,
    );
    const strokes = [...container.querySelectorAll("line")].map((l) =>
      l.getAttribute("stroke"),
    );
    expect(strokes).toContain("hsl(var(--border))");
  });
});
