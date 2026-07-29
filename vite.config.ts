import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vitest/config";

const require = createRequire(import.meta.url);

/**
 * Ship MapLibre's tile-parsing worker with the production build.
 *
 * MapLibre v6 spawns its worker from a blob that does
 * `import(new URL("maplibre-gl-worker.mjs", import.meta.url).href)`. That URL
 * is assembled at runtime inside a template string, so Rollup cannot see it and
 * emits no chunk for it. In the built site `import.meta.url` is the hashed
 * bundle in /assets/, so the worker resolves to /assets/maplibre-gl-worker.mjs
 * — which does not exist. The SPA fallback then answers with index.html at
 * HTTP 200, the worker tries to parse HTML as a module, and closes.
 *
 * Nothing reports this. The failure is inside a worker, so no main-thread
 * error fires and no request 404s. MapLibre parses both vector tiles AND
 * GeoJSON there, so the basemap and our station dots die together: every map
 * renders as an empty box while `isStyleLoaded()` stays false forever. That is
 * exactly what spec 021 shipped.
 *
 * Copying both files verbatim, unhashed, is what makes the runtime-computed
 * URL resolve. `maplibre-gl-shared.mjs` is duplicated between the main bundle
 * and the worker, which is MapLibre's own packaging and costs ~467 KB
 * uncompressed on a chunk only the worker fetches.
 */
function maplibreWorker(): Plugin {
  const FILES = ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"];
  return {
    name: "maplibre-worker-assets",
    apply: "build",
    generateBundle() {
      const dist = path.dirname(require.resolve("maplibre-gl/dist/maplibre-gl.mjs"));
      for (const file of FILES) {
        const from = path.join(dist, file);
        if (!fs.existsSync(from)) {
          // Loud, not silent: a renamed dist file must break the build rather
          // than ship blank maps again.
          this.error(
            `maplibre-worker-assets: ${file} not found in ${dist}. ` +
              "MapLibre's dist layout changed — the station maps will render " +
              "blank until this plugin is updated.",
          );
        }
        this.emitFile({
          type: "asset",
          fileName: `assets/${file}`, // unhashed: the runtime URL is literal
          source: fs.readFileSync(from),
        });
      }
    },
    // Emitting is not shipping. Assert the files reached disk, so a change to
    // Vite's output layout fails the build instead of producing a site whose
    // maps are blank and which reports nothing wrong.
    closeBundle() {
      const outDir = path.resolve(__dirname, "dist/assets");
      const missing = FILES.filter((f) => !fs.existsSync(path.join(outDir, f)));
      if (missing.length) {
        this.error(
          `maplibre-worker-assets: ${missing.join(", ")} missing from dist/assets ` +
            "after build. The station maps would render blank silently.",
        );
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), maplibreWorker()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // In dev the same worker breaks differently: Vite's dep pre-bundling rewrites
  // MapLibre's import graph and the worker request fails outright
  // (net::ERR_FAILED, then an immediate close). Excluding it leaves the real
  // module graph in place, so `import.meta.url` resolves to the file that
  // actually exists in node_modules.
  optimizeDeps: { exclude: ["maplibre-gl"] },
  worker: { format: "es" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
});
