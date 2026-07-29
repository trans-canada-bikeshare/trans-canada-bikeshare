import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// The design language is inherited, not invented here. These pins fail if a
// token drifts from the value mobi-transit-explorer measured from
// adnanreza.com — the two projects are meant to read as one body of work, and a
// silently retuned accent or rule tone is exactly the kind of drift nobody
// notices until they sit side by side.

const css = readFileSync(resolve(__dirname, "./index.css"), "utf-8");

function block(selector: string): string {
  const start = css.indexOf(`${selector} {`);
  expect(start, `${selector} block missing`).toBeGreaterThan(-1);
  return css.slice(start, css.indexOf("\n  }", start));
}

const LIGHT: Record<string, string> = {
  "--background": "210 33% 97%",
  "--foreground": "203 31% 5%",
  "--card": "204 22% 95%",
  "--primary": "205 74% 38%",
  "--secondary-foreground": "202 11% 20%",
  "--muted-foreground": "205 6% 41%",
  "--muted-2": "207 4% 60%",
  "--accent-foreground": "204 100% 23%",
  "--border": "206 9% 85%",
  "--rule-2": "210 12% 90%",
  "--radius": "0.5rem",
};

const DARK: Record<string, string> = {
  "--background": "0 0% 4%",
  "--foreground": "0 0% 93%",
  "--card": "0 0% 9%",
  "--primary": "207 66% 62%",
  "--secondary-foreground": "0 0% 75%",
  "--muted-foreground": "0 0% 58%",
  "--muted-2": "0 0% 36%",
  "--accent-foreground": "207 76% 70%",
  "--border": "0 0% 18%",
  "--rule-2": "0 0% 13%",
};

describe("design tokens", () => {
  it.each(Object.entries(LIGHT))("light %s = %s", (name, value) => {
    expect(block(":root")).toContain(`${name}: ${value};`);
  });

  it.each(Object.entries(DARK))("dark %s = %s", (name, value) => {
    expect(block(".dark")).toContain(`${name}: ${value};`);
  });

  it("declares color-scheme in both themes so form chrome follows", () => {
    expect(block(":root")).toContain("color-scheme: light;");
    expect(block(".dark")).toContain("color-scheme: dark;");
  });

  it("keeps the eyebrow at 11px uppercase with 0.14em tracking", () => {
    expect(css).toMatch(/\.eyebrow\s*\{[^}]*text-\[11px\][^}]*uppercase[^}]*tracking-\[0\.14em\]/);
  });

  it("uses an ink focus outline, not a coloured ring", () => {
    expect(css).toContain("outline: 2px solid hsl(var(--foreground));");
  });

  it("holds reveals still under prefers-reduced-motion", () => {
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });

  it("ships no shadows — hairline rules are the only structural chrome", () => {
    expect(css).not.toMatch(/box-shadow:\s*(?!none)/);
  });
});
