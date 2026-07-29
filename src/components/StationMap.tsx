import { useEffect, useRef, useState } from "react";
import type { SystemId } from "@/lib/systems";
import { SYSTEMS, seriesColor } from "@/lib/systems";
import { compact, full } from "@/lib/format";
import { loadStations, type StationPin } from "@/lib/data";
import "maplibre-gl/dist/maplibre-gl.css";

interface Props {
  system: SystemId;
  theme: "light" | "dark";
}

interface Selected {
  name: string;
  trips: number;
  active: boolean;
}

const STYLE = {
  light: "https://tiles.openfreemap.org/styles/positron",
  dark: "https://tiles.openfreemap.org/styles/dark",
} as const;

/**
 * One system's stations on a map.
 *
 * MapLibre is imported dynamically. The library is roughly 230 KB gzipped
 * against a whole-site bundle of about 62 KB, so loading it eagerly would
 * quadruple the cost of a page most readers never scroll to the bottom of. It
 * arrives when this component first becomes visible and not before.
 *
 * Retired stations are drawn hollow rather than hidden. Where a network used
 * to reach is part of its history, and the map is the only surface here that
 * can show it.
 */
export function StationMap({ system, theme }: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const mapRef = useRef<{ remove: () => void } | null>(null);
  const [visible, setVisible] = useState(false);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<Selected | null>(null);

  const [stations, setStations] = useState<StationPin[]>([]);
  const meta = SYSTEMS[system];

  // Pins arrive with the same trigger as the library, not with the page.
  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    loadStations()
      .then((all) => !cancelled && setStations(all.filter((s) => s.s === system)))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [visible, system]);

  // Only start loading once the section is actually approached.
  useEffect(() => {
    const node = holder.current;
    if (!node || visible) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const obs = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting) && setVisible(true),
      { rootMargin: "200px" },
    );
    obs.observe(node);
    return () => obs.disconnect();
  }, [visible]);

  useEffect(() => {
    if (!visible || !holder.current || stations.length === 0) return;
    let cancelled = false;

    (async () => {
      try {
        // The stylesheet ships with the same lazy chunk (see maplibre.css,
        // imported by this module's own side-effect import below).
        const maplibre = await import("maplibre-gl");
        if (cancelled || !holder.current) return;

        const lats = stations.map((s) => s.y);
        const lons = stations.map((s) => s.x);
        const map = new maplibre.Map({
          container: holder.current,
          style: STYLE[theme],
          bounds: [
            [Math.min(...lons), Math.min(...lats)],
            [Math.max(...lons), Math.max(...lats)],
          ],
          fitBoundsOptions: { padding: 28 },
          attributionControl: { compact: true },
        });
        mapRef.current = map;
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
        // "load" waits for the basemap's first tiles. The station dots are
        // OUR data and must not depend on a third-party tile server being
        // reachable — draw them as soon as the style is parsed, so a failed
        // basemap degrades to dots on blank paper rather than an empty box
        // that claims it is still loading.
        map.on("error", (e: { error?: { message?: string } }) => {
          // Tile failures are noisy and non-fatal; only a style failure means
          // there is nothing to show.
          if (!cancelled && /style/i.test(e?.error?.message ?? "")) setFailed(true);
        });
        const draw = () => {
          if (cancelled || map.getSource("stations")) return;
          map.addSource("stations", {
            type: "geojson",
            data: {
              type: "FeatureCollection",
              features: stations.map((s) => ({
                type: "Feature",
                geometry: { type: "Point", coordinates: [s.x, s.y] },
                properties: { name: s.n, trips: s.t, active: s.a ? 1 : 0 },
              })),
            },
          });
          const maxTrips = Math.max(...stations.map((s) => s.t));
          map.addLayer({
            id: "station-dots",
            type: "circle",
            source: "stations",
            paint: {
              "circle-radius": [
                "interpolate", ["linear"], ["sqrt", ["get", "trips"]],
                0, 2.5, Math.sqrt(maxTrips), 9,
              ],
              "circle-color": seriesColor(system),
              // Retired stations read as outlines, not absences.
              "circle-opacity": ["case", ["==", ["get", "active"], 1], 0.55, 0.06],
              "circle-stroke-width": 1,
              "circle-stroke-color": seriesColor(system),
              "circle-stroke-opacity": ["case", ["==", ["get", "active"], 1], 0.9, 0.55],
            },
          });
          map.on("click", "station-dots", (e) => {
            const f = e.features?.[0];
            if (!f) return;
            setSelected({
              name: String(f.properties?.name ?? ""),
              trips: Number(f.properties?.trips ?? 0),
              active: Number(f.properties?.active) === 1,
            });
          });
          map.on("mouseenter", "station-dots", () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", "station-dots", () => {
            map.getCanvas().style.cursor = "";
          });
          setReady(true);
        };
        if (map.isStyleLoaded()) draw();
        else map.on("style.load", draw);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      setReady(false);
    };
    // Theme is a dependency: the basemap is baked into the style, so a theme
    // change rebuilds the map rather than mutating it.
  }, [visible, theme, system, stations]);

  const active = stations.filter((s) => s.a).length;

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="eyebrow" style={{ color: seriesColor(system) }}>
          {meta.city}
        </p>
        <p className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {full(active)} active · {full(stations.length - active)} retired
        </p>
      </div>

      <div
        ref={holder}
        className="mt-3 h-[300px] w-full border border-border md:h-[380px]"
        aria-label={`Map of ${meta.city} bike share stations`}
        role="img"
      />

      <p className="mt-2 min-h-[1.25rem] text-[13px] text-muted-foreground">
        {failed ? (
          "The map could not load. The station figures above come from the data, not the map."
        ) : selected ? (
          <>
            <strong className="font-medium text-foreground">{selected.name}</strong> ·{" "}
            {compact(selected.trips)} lifetime trips ·{" "}
            {selected.active ? "active" : "retired"}
          </>
        ) : ready ? (
          "Select a station for its lifetime trips. Hollow dots are retired stations."
        ) : (
          "Map loads when you reach it."
        )}
      </p>
    </div>
  );
}
