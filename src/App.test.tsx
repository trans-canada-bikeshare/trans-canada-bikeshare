import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import App from "@/App";

describe("App scaffold", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
    localStorage.clear();
  });

  it("renders the project name and the three tier-1 systems", () => {
    render(<App />);
    expect(screen.getByText("Trans-Canada Bikeshare")).toBeInTheDocument();
    for (const city of ["Vancouver", "Montreal", "Toronto"]) {
      expect(screen.getByText(city)).toBeInTheDocument();
    }
  });

  it("uses the eyebrow micro-label rather than a heading for section labels", () => {
    const { container } = render(<App />);
    expect(container.querySelector(".eyebrow")).not.toBeNull();
  });

  it("toggles the theme and reflects it in aria-pressed", async () => {
    const user = userEvent.setup();
    render(<App />);
    const toggle = screen.getByRole("button", { name: /switch to dark theme/i });
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    await user.click(toggle);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(
      screen.getByRole("button", { name: /switch to light theme/i }),
    ).toHaveAttribute("aria-pressed", "true");
  });
});
