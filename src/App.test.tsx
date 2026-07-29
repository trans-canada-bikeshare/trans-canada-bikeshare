import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import { ebikeShare, meta } from "@/lib/data";

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

  it("states the common window rather than implying one", () => {
    render(<App />);
    const overview = document.getElementById("overview")!;
    expect(overview.textContent).toMatch(
      new RegExp(meta.common_window_first_year),
    );
    expect(overview.textContent).toMatch(/all\s+three publish/i);
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

  it("declares no government affiliation", () => {
    render(<App />);
    expect(
      screen.getByText(/not affiliated with or endorsed by the government of canada/i),
    ).toBeInTheDocument();
  });
});
