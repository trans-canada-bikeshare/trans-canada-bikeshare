import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Icon links rot silently: a renamed file leaves a 404 that nobody notices
// because the browser just shows a blank tab. These pin the wiring.

const root = resolve(__dirname, "..");
const html = readFileSync(resolve(root, "index.html"), "utf-8");
const manifest = JSON.parse(readFileSync(resolve(root, "public/site.webmanifest"), "utf-8"));

const ASSETS = [
  "favicon.svg",
  "favicon.ico",
  "apple-touch-icon.png",
  "icon-192.png",
  "icon-512.png",
  "logo.svg",
  "site.webmanifest",
];

describe("brand assets", () => {
  it.each(ASSETS)("public/%s exists", (name) => {
    expect(existsSync(resolve(root, "public", name))).toBe(true);
  });

  it("index.html references every icon and the manifest", () => {
    for (const href of [
      "/favicon.svg",
      "/favicon.ico",
      "/apple-touch-icon.png",
      "/site.webmanifest",
    ]) {
      expect(html).toContain(`href="${href}"`);
    }
  });

  it("prefers the SVG icon over the ico fallback", () => {
    expect(html.indexOf("/favicon.svg")).toBeLessThan(html.indexOf("/favicon.ico"));
  });

  it("manifest points only at icons that exist", () => {
    for (const icon of manifest.icons) {
      expect(existsSync(resolve(root, "public", icon.src.replace(/^\//, "")))).toBe(true);
    }
  });

  it("favicon.svg adapts to dark chrome instead of vanishing", () => {
    const svg = readFileSync(resolve(root, "public/favicon.svg"), "utf-8");
    expect(svg).toContain("prefers-color-scheme: dark");
  });

  it("favicon.ico is a valid multi-size ICO", () => {
    const ico = readFileSync(resolve(root, "public/favicon.ico"));
    expect(ico.readUInt16LE(0)).toBe(0); // reserved
    expect(ico.readUInt16LE(2)).toBe(1); // type 1 = icon
    const count = ico.readUInt16LE(4);
    expect(count).toBe(3);
    const sizes = Array.from({ length: count }, (_, i) => ico.readUInt8(6 + 16 * i));
    expect(sizes.sort((a, b) => a - b)).toEqual([16, 32, 48]);
  });

  it("keeps the leaf out of a bare ring — the rondelle collision", () => {
    // A leaf centred in an open ring is Air Canada's mark, and this project is
    // transport with a "Trans-Canada" name. The spokes and hub are what make
    // this a bicycle wheel instead. If they ever get removed, fail loudly.
    const svg = readFileSync(resolve(root, "public/favicon.svg"), "utf-8");
    expect(svg).toContain('class="spoke"');
    expect(svg).toContain('class="hub"');
  });
});
