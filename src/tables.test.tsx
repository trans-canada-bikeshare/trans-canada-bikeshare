import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "@/App";
// The artifacts, imported here exactly as the site imports them. A table that
// agreed with a number this test computed for itself would prove nothing.
import stationsYearly from "@/data/generated/stations_yearly.json";
import tripsMonthly from "@/data/generated/trips_monthly.json";
import { SYSTEM_ORDER, SYSTEMS } from "@/lib/systems";
import { full, monthLabel } from "@/lib/format";

/** The one table pattern: a `<details>` disclosure holding a captioned table. */
function tablesIn(sectionId: string): HTMLTableElement[] {
  const section = document.getElementById(sectionId)!;
  return Array.from(section.querySelectorAll<HTMLTableElement>("details table"));
}

/** A table as `{ rowHeader: { columnHeader: cellText } }`. */
function readTable(table: HTMLTableElement): Record<string, Record<string, string>> {
  const columns = Array.from(table.querySelectorAll("thead th")).map(
    (th) => th.textContent ?? "",
  );
  const out: Record<string, Record<string, string>> = {};
  for (const tr of Array.from(table.querySelectorAll("tbody tr"))) {
    const cells = Array.from(tr.children).map((c) => c.textContent ?? "");
    const row: Record<string, string> = {};
    cells.slice(1).forEach((v, i) => (row[columns[i + 1]] = v));
    out[cells[0]] = row;
  }
  return out;
}

describe("chart data tables", () => {
  // Charts on this site are SVG and pointer-only: the value at a given month is
  // available by hovering and no other way. Every section that draws one has to
  // offer the numbers some other way.
  it("gives every chart section a table", () => {
    render(<App />);
    for (const id of ["trips", "seasons", "stations", "ebikes", "members", "ops"]) {
      expect(tablesIn(id).length, id).toBeGreaterThan(0);
    }
    // Two charts in each of these sections, so two tables.
    expect(tablesIn("members")).toHaveLength(2);
    expect(tablesIn("ops")).toHaveLength(2);
  });

  it("uses one pattern everywhere: a details disclosure and a captioned table", () => {
    render(<App />);
    const tables = Array.from(document.querySelectorAll("table"));
    expect(tables.length).toBeGreaterThan(0);
    for (const t of tables) {
      expect(t.closest("details"), t.querySelector("caption")?.textContent ?? "").not.toBeNull();
      expect(t.querySelector("caption")?.textContent ?? "").not.toHaveLength(0);
      // Row and column headers, or a screen reader reads a grid of loose
      // numbers with nothing saying which city or which month.
      expect(t.querySelectorAll("thead th").length).toBeGreaterThan(1);
      expect(t.querySelectorAll('tbody th[scope="row"]').length).toBeGreaterThan(0);
    }
  });

  // The pin. Every cell of the stations table, against the artifact the chart
  // above it is drawn from — same file, same rows, no recomputation on either
  // side. `stations_yearly.json` is the whole basis of that chart.
  it("prints the station counts stations_yearly.json holds, cell for cell", () => {
    render(<App />);
    const [table] = tablesIn("stations");
    const read = readTable(table);

    const years = [...new Set(stationsYearly.map((r) => r.year))].sort((a, b) => a - b);
    expect(Object.keys(read)).toEqual(years.map(String));

    for (const row of stationsYearly) {
      const city = SYSTEMS[row.system_id as keyof typeof SYSTEMS].city;
      expect(read[String(row.year)][city], `${row.system_id} ${row.year}`).toBe(
        full(row.stations),
      );
    }
    // And nothing invented: a cell with no artifact row is an em dash, never a
    // zero for a year a system did not run.
    const published = new Set(stationsYearly.map((r) => `${r.system_id}|${r.year}`));
    for (const id of SYSTEM_ORDER) {
      for (const year of years) {
        if (published.has(`${id}|${year}`)) continue;
        expect(read[String(year)][SYSTEMS[id].city], `${id} ${year}`).toBe("—");
      }
    }
  });

  // The same discipline on the largest table, where a formatting slip would be
  // easiest to miss: spot-check the extremes and the row count.
  it("prints monthly trips at the precision the artifact holds", () => {
    render(<App />);
    const [table] = tablesIn("trips");
    const read = readTable(table);

    const months = [...new Set(tripsMonthly.map((r) => r.month))].sort();
    expect(Object.keys(read)).toHaveLength(months.length);

    for (const id of SYSTEM_ORDER) {
      const rows = tripsMonthly
        .filter((r) => r.system_id === id)
        .sort((a, b) => a.month.localeCompare(b.month));
      const busiest = rows.reduce((a, b) => (a.trips >= b.trips ? a : b));
      for (const row of [rows[0], rows[rows.length - 1], busiest]) {
        expect(read[monthLabel(row.month)][SYSTEMS[id].city], `${id} ${row.month}`).toBe(
          full(row.trips),
        );
      }
    }
  });
});
