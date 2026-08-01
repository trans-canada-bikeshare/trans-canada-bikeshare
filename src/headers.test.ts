import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * `public/_headers`, structurally.
 *
 * These headers cannot be observed locally — `vite preview` does not read the
 * file, so the live check belongs on a Pages preview deployment and is written
 * into the file itself. What a test CAN hold is everything that is decidable
 * from the repository: that each rule exists, that the caching exception for
 * MapLibre's un-hashed worker files is still keyed to the filenames
 * `vite.config.ts` actually emits, that the CSP names every origin the code
 * reaches for, and that the script hash still matches the inline script it was
 * computed from.
 */

// Vitest runs with the project root as its working directory.
const read = (p: string) => readFileSync(path.resolve(process.cwd(), p), "utf8");

const HEADERS = read("public/_headers");

/** Stands in for a `! Header` line, which removes a header rather than setting
 *  one. The NUL keeps it distinct from any value a rule could legitimately
 *  carry, so a detach is never mistaken for a Cache-Control value. */
const DETACH = "\u0000detach";

/** `_headers` as rules: a column-0 path line, then indented `Name: value`. */
function parse(text: string) {
  const rules: { path: string; headers: [string, string][]; line: number }[] = [];
  text.split("\n").forEach((raw, i) => {
    const trimmed = raw.trim();
    if (trimmed === "" || trimmed.startsWith("#")) return;
    if (!/^[ \t]/.test(raw)) {
      rules.push({ path: trimmed, headers: [], line: i + 1 });
      return;
    }
    const at = trimmed.indexOf(":");
    const rule = rules[rules.length - 1];
    expect(rule, `header at line ${i + 1} before any rule`).toBeDefined();
    if (trimmed.startsWith("! ")) {
      rule.headers.push([trimmed.slice(2).trim(), DETACH]);
      return;
    }
    expect(at, `no colon on line ${i + 1}: ${trimmed}`).toBeGreaterThan(0);
    rule.headers.push([trimmed.slice(0, at).trim(), trimmed.slice(at + 1).trim()]);
  });
  return rules;
}

const RULES = parse(HEADERS);
const find = (path: string) => RULES.find((r) => r.path === path);
/** The value a rule SETS for a header — a `! Header` line removes, so it is not
 *  a value. Last wins within a rule, which is also how Pages reads it. */
const header = (path: string, name: string) =>
  find(path)
    ?.headers.filter(([n, v]) => n.toLowerCase() === name.toLowerCase() && v !== DETACH)
    .at(-1)?.[1];

/** The MapLibre files the build emits un-hashed, read from the build config so
 *  a rename there fails here rather than shipping a year-long cache on them. */
function unhashedAssets(): string[] {
  const config = read("vite.config.ts");
  const list = /const FILES = \[([^\]]+)\]/.exec(config);
  expect(list, "vite.config.ts no longer declares a FILES list").not.toBeNull();
  return [...list![1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
}

describe("public/_headers", () => {
  it("parses as Cloudflare Pages rules, every line accounted for", () => {
    expect(RULES.length).toBeGreaterThan(1);
    for (const rule of RULES) {
      expect(rule.path.startsWith("/"), rule.path).toBe(true);
      expect(rule.headers.length, rule.path).toBeGreaterThan(0);
    }
    // 100 rules, 2,000 characters a line — Cloudflare's documented limits.
    expect(RULES.length).toBeLessThanOrEqual(100);
    for (const line of HEADERS.split("\n")) expect(line.length).toBeLessThanOrEqual(2000);
  });

  it("sends HSTS, nosniff, a referrer policy and a permissions policy site-wide", () => {
    const hsts = header("/*", "Strict-Transport-Security") ?? "";
    expect(hsts).toMatch(/max-age=31536000/);
    expect(hsts).toMatch(/includeSubDomains/);
    expect(header("/*", "X-Content-Type-Options")).toBe("nosniff");
    expect(header("/*", "Referrer-Policy")).toBe("strict-origin-when-cross-origin");
    const permissions = header("/*", "Permissions-Policy") ?? "";
    for (const feature of ["geolocation", "camera", "microphone", "payment"]) {
      expect(permissions, feature).toContain(`${feature}=()`);
    }
  });

  it("carries a CSP with the sources the app actually uses, and no eval", () => {
    const csp = header("/*", "Content-Security-Policy") ?? "";
    const directive = (name: string) =>
      csp
        .split(";")
        .map((d) => d.trim())
        .find((d) => d === name || d.startsWith(`${name} `)) ?? "";

    expect(directive("default-src")).toBe("default-src 'self'");
    expect(directive("object-src")).toBe("object-src 'none'");
    expect(directive("base-uri")).toBe("base-uri 'self'");
    expect(directive("frame-ancestors")).toBe("frame-ancestors 'none'");

    // The map dies silently without these two: MapLibre spawns its tile-parsing
    // worker from a Blob, and that is exactly the failure spec 021 shipped.
    expect(directive("worker-src")).toContain("blob:");
    expect(directive("child-src")).toContain("blob:");

    // The basemap origin, in both directives that reach it.
    for (const name of ["img-src", "connect-src"]) {
      expect(directive(name), name).toContain("https://tiles.openfreemap.org");
    }
    // maplibre-gl.css's control icons, and its blob-decoded tile images.
    expect(directive("img-src")).toContain("data:");
    expect(directive("img-src")).toContain("blob:");

    expect(csp).not.toContain("unsafe-eval");
    // A wildcard source would make every other line of this test decorative.
    expect(csp).not.toMatch(/(^|[ ;])\*([ ;]|$)/);
    expect(directive("script-src")).not.toContain("unsafe-inline");
  });

  it("pins the inline theme script by hash, and the hash still matches it", () => {
    const html = read("index.html");
    const inline = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)];
    // One, and only one: a second inline script would be silently blocked.
    expect(inline).toHaveLength(1);
    const digest = createHash("sha256").update(inline[0][1], "utf8").digest("base64");
    expect(header("/*", "Content-Security-Policy")).toContain(`'sha256-${digest}'`);
  });

  it("caches hashed assets immutably", () => {
    const cache = header("/assets/*", "Cache-Control") ?? "";
    expect(cache).toMatch(/max-age=31536000/);
    expect(cache).toContain("immutable");
  });

  // The whole reason this file needs the detach syntax. Pages merges matching
  // rules and comma-joins repeats, so re-stating Cache-Control without first
  // detaching would serve both values at once.
  it("keeps the un-hashed MapLibre files revalidating, detaching the inherited value", () => {
    const assetsAt = RULES.findIndex((r) => r.path === "/assets/*");
    expect(assetsAt).toBeGreaterThanOrEqual(0);

    for (const file of unhashedAssets()) {
      const path = `/assets/${file}`;
      const rule = find(path);
      expect(rule, `${path} has no rule; it would inherit an immutable year`).toBeDefined();
      // Order matters: the detach removes what an earlier rule added.
      expect(RULES.indexOf(rule!), path).toBeGreaterThan(assetsAt);

      // The detach must be present, and must come before the value it clears.
      const cacheLines = rule!.headers.filter(
        ([n]) => n.toLowerCase() === "cache-control",
      );
      expect(cacheLines, path).toHaveLength(2);
      expect(cacheLines[0], path).toEqual(["Cache-Control", DETACH]);
      const value = header(path, "Cache-Control") ?? "";
      expect(value, path).toContain("must-revalidate");
      expect(value, path).toMatch(/max-age=0/);
      expect(value, path).not.toContain("immutable");
    }
  });

  it("caches the social card briefly rather than immutably", () => {
    const cache = header("/og-image.png", "Cache-Control") ?? "";
    expect(cache).toMatch(/max-age=3600/);
    expect(cache).not.toContain("immutable");
  });
});
