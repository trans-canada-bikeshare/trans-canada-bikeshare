import { useEffect, useRef, useState } from "react";
import type { SystemId } from "@/lib/systems";
import { SYSTEMS, seriesColor, resolvedSeriesColor } from "@/lib/systems";
import { compact, full } from "@/lib/format";
import { loadStations, flowRate, type StationPin } from "@/lib/data";
import "maplibre-gl/dist/maplibre-gl.css";

export type MapMode = "volume" | "flow";

interface Props {
  system: SystemId;
  theme: "light" | "dark";
  /**
   * `volume` colours every dot with the system's series colour, so the map
   * reads as "where this network is". `flow` colours by net flow rate — a
   * quantity with a meaningful zero, so it gets a diverging scale rather than
   * the series colour, and the section says which end is which.
   */
  mode?: MapMode;
}

interface Selected {
  name: string;
  trips: number;
  active: boolean;
  /** net flow: returns minus departures */
  net: number;
}

const STYLE = {
  light: "https://tiles.openfreemap.org/styles/positron",
  dark: "https://tiles.openfreemap.org/styles/dark",
} as const;

/**
 * Diverging scale for net flow rate, clipped at ±15%.
 *
 * Not the series colour: net flow has a meaningful zero, and colouring it with
 * a single-hue ramp would hide the sign — the one thing the encoding exists to
 * show. Amber drains (gives out more bikes than it takes), indigo accumulates.
 *
 * The domain is ±0.15 rather than the observed range. A few stations reach
 * ±0.9, and scaling to them would collapse every ordinary dock onto neutral
 * grey. So a fully saturated dot means "at least this imbalanced", which the
 * section states — an encoding that clips has to say it clips.
 *
 * Literal colours, because MapLibre parses in JS and cannot read a CSS custom
 * property. These are chosen to hold up on both the light and dark basemap
 * rather than swapped per theme, so the two views stay directly comparable.
 */
const FLOW_SCALE: unknown[] = [
  "interpolate",
  ["linear"],
  ["get", "rate"],
  -0.15, "#b45309",
  -0.04, "#d9a441",
  0, "#9aa0a6",
  0.04, "#5b8dd6",
  0.15, "#3730a3",
];

/**
 * One system's stations on a map.
 *
 * MapLibre is imported dynamically. The library is 257 KB gzipped against an
 * initial bundle of 75 KB, so loading it eagerly would more than quadruple the
 * cost of a page most readers never scroll to the bottom of. It arrives when
 * this component first becomes visible and not before.
 *
 * Dormant stations are drawn hollow rather than hidden. Where a network used
 * to reach is part of its history, and the map is the only surface here that
 * can show it. "Dormant" is deliberate: the flag means no trip in the last six
 * months of this system's own data, which is not the same as decommissioned —
 * 28 of the hollow dots are stations the live GBFS feed still lists.
 */
export function StationMap({ system, theme, mode = "volume" }: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const mapRef = useRef<{ remove: () => void } | null>(null);
  const [visible, setVisible] = useState(false);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<Selected | null>(null);

  const [stations, setStations] = useState<StationPin[]>([]);
  const [loaded, setLoaded] = useState(false);
  // One dot-size ceiling shared by all three maps. Scaling each map to its own
  // busiest station would make a 9px dot mean 1,182,789 lifetime events in
  // Montreal and 429,534 in Vancouver — three panels side by side encoding at
  // rates 2.75x apart, under one sentence explaining the encoding. That is the
  // like-for-like promise broken in the one place a reader cannot check it.
  const [scaleMax, setScaleMax] = useState(0);
  const meta = SYSTEMS[system];

  // Pins arrive with the same trigger as the library, not with the page.
  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    loadStations()
      .then((all) => {
        if (cancelled) return;
        setScaleMax(Math.max(...all.map((s) => s.t)));
        setStations(all.filter((s) => s.s === system));
        setLoaded(true);
      })
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

        // Frame the network, not its farthest outlier. BIXI runs stations in
        // Sherbrooke about 150 km east; on a raw min/max fit that stretches
        // Montreal's box to 161 km against Vancouver's 15 km and collapses the
        // dense core into a blob.
        //
        // A fixed percentile does not work here — Sherbrooke and the South
        // Shore are 3% of Montreal's stations, so trimming 1% left the frame
        // at zoom 6.6, still showing the whole Eastern Townships. This uses
        // Tukey's far-outlier fence instead, which adapts to each
        // distribution: a separated cluster falls outside it however large it
        // is, and a network with no outliers keeps its full extent because
        // the fence is clamped to the data. The outliers are still drawn —
        // they are one pan away, which the section says.
        const span = (vals: number[]): [number, number] => {
          const s = [...vals].sort((a, b) => a - b);
          const at = (q: number) => s[Math.round(q * (s.length - 1))];
          const q1 = at(0.25);
          const q3 = at(0.75);
          const fence = 3 * (q3 - q1);
          return [
            Math.max(s[0], q1 - fence),
            Math.min(s[s.length - 1], q3 + fence),
          ];
        };
        const [lonLo, lonHi] = span(stations.map((s) => s.x));
        const [latLo, latHi] = span(stations.map((s) => s.y));
        const map = new maplibre.Map({
          container: holder.current,
          style: STYLE[theme],
          bounds: [
            [lonLo, latLo],
            [lonHi, latHi],
          ],
          fitBoundsOptions: { padding: 28 },
          attributionControl: { compact: true },
        });
        mapRef.current = map;
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
        // Registering an "error" listener silences MapLibre's own console
        // logging, so this handler is the only place a fault can surface. It
        // must therefore report everything it does not recognise rather than
        // filtering for the one case its author had in mind — an earlier
        // version matched /style/i only, which swallowed the layer-validation
        // error that left every map empty and reported nothing.
        map.on("error", (e: { error?: { message?: string } }) => {
          const message = e?.error?.message ?? "unknown MapLibre error";
          if (cancelled) return;
          // Tiles and sprites fail piecemeal and are non-fatal; the map still
          // carries our dots. Anything else means the render is compromised.
          if (/\b(tile|sprite|glyph)\b/i.test(message)) return;
          console.error("[StationMap]", meta.city, message);
          setFailed(true);
        });
        // "load" waits for the basemap's first tiles. The station dots are
        // OUR data and must not depend on a third-party tile server being
        // reachable — draw them as soon as the style is parsed, so a failed
        // basemap degrades to dots on blank paper rather than an empty box
        // that claims it is still loading.
        const draw = () => {
          if (cancelled || map.getSource("stations")) return;
          // MapLibre parses colours in JavaScript and cannot resolve a CSS
          // custom property. Handing it `hsl(var(--series-van))` makes it
          // reject the entire layer, which is how this shipped three maps that
          // added a source and drew nothing.
          const dot = resolvedSeriesColor(system);
          // MapLibre requires strictly ascending interpolation stops. A
          // scaleMax of 0 would put both radius stops at input 0 and get the
          // layer rejected exactly the way the unresolved `var()` colour was —
          // silently, with the source added and nothing drawn. It should not
          // happen, since scaleMax and stations are set together, but "should
          // not happen" is the reasoning that shipped the first bug.
          const ceiling = Math.sqrt(scaleMax);
          if (!dot || !(ceiling > 0)) {
            setFailed(true);
            return;
          }
          map.addSource("stations", {
            type: "geojson",
            data: {
              type: "FeatureCollection",
              features: stations.map((s) => ({
                type: "Feature",
                geometry: { type: "Point", coordinates: [s.x, s.y] },
                properties: {
                  name: s.n,
                  trips: s.t,
                  active: s.a ? 1 : 0,
                  net: s.f,
                  rate: flowRate(s),
                },
              })),
            },
          });
          map.addLayer({
            id: "station-dots",
            type: "circle",
            source: "stations",
            paint: {
              "circle-radius": [
                "interpolate", ["linear"], ["sqrt", ["get", "trips"]],
                0, 2.5, ceiling, 9,
              ],
              // Net flow has a meaningful zero, so it gets a diverging scale
              // rather than the series colour. The domain is +/-15%, not the
              // observed extremes: a handful of stations reach +/-90% and
              // scaling to them would flatten every ordinary dock to neutral.
              // The clipping is stated where the map is, because a saturated
              // dot means "at least this imbalanced", not "exactly".
              "circle-color": (mode === "flow" ? FLOW_SCALE : dot) as never,
              // Dormant stations read as outlines, not absences. The ring is
              // drawn at full strength for both states so it clears the 3:1
              // of WCAG 1.4.11 — the fill alone carries the distinction.
              "circle-opacity":
                mode === "flow"
                  ? 0.75
                  : ["case", ["==", ["get", "active"], 1], 0.55, 0.1],
              "circle-stroke-width": 1,
              "circle-stroke-color": (mode === "flow" ? FLOW_SCALE : dot) as never,
              "circle-stroke-opacity": 0.9,
            },
          });
          map.on("click", "station-dots", (e) => {
            const f = e.features?.[0];
            if (!f) return;
            setSelected({
              name: String(f.properties?.name ?? ""),
              trips: Number(f.properties?.trips ?? 0),
              active: Number(f.properties?.active) === 1,
              net: Number(f.properties?.net ?? 0),
            });
          });
          map.on("mouseenter", "station-dots", () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", "station-dots", () => {
            map.getCanvas().style.cursor = "";
          });
          // Only now is the caption's promise true. addLayer rejects an
          // invalid paint property without throwing, so readiness is claimed
          // on the layer existing, never on having asked for it.
          if (map.getLayer("station-dots")) setReady(true);
          else setFailed(true);
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
      // The rebuilt map has nothing selected; leaving the old readout up would
      // caption a station the reader can no longer see highlighted.
      setSelected(null);
    };
    // Theme is a dependency: the basemap is baked into the style, so a theme
    // change rebuilds the map rather than mutating it — and re-resolves the
    // series colour against the newly applied tokens.
  }, [visible, theme, system, stations, scaleMax, meta.city, mode]);

  const active = stations.filter((s) => s.a).length;

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        {/* The series colour is a swatch, not the text: as 11px type it reads
            4.0:1 against paper for Toronto's ochre, under AA. This is the
            idiom StatGrid already uses. */}
        <p className="eyebrow flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-2 w-2 shrink-0"
            style={{ backgroundColor: seriesColor(system) }}
          />
          {meta.city}
        </p>
        {loaded && (
          <p className="font-mono text-[11px] tabular-nums text-muted-foreground">
            {full(active)} mapped · {full(stations.length - active)} dormant
          </p>
        )}
      </div>

      <figure className="m-0">
        {/* The dots are only reachable with a pointer. Rather than leave a
            screen-reader user with a bare "image", state the figures the map
            encodes. `role="img"` was worse than nothing here: it declares its
            children presentational, and this container holds six focusable
            controls. */}
        {loaded && stations.length > 0 && (
          <p className="sr-only">
            {full(stations.length)} {meta.city} stations are plotted:{" "}
            {full(active)} used in the last six months of this system&rsquo;s data
            and {full(stations.length - active)} dormant. Dot size is lifetime
            events on one scale shared by all three maps.
          </p>
        )}
        <div
          ref={holder}
          className="mt-3 h-[300px] w-full border border-border md:h-[380px]"
          role="group"
          aria-label={`Interactive map of ${meta.city} bike share stations`}
        />

        <figcaption
          aria-live="polite"
          className="mt-2 min-h-[1.25rem] text-[13px] text-muted-foreground"
        >
          {failed ? (
            loaded ? (
              `The map could not load. The ${full(stations.length)} stations counted above come from the data, not the map.`
            ) : (
              "The map could not load."
            )
          ) : loaded && stations.length === 0 ? (
            `No ${meta.city} stations have a known position.`
          ) : selected ? (
            <>
              <strong className="font-medium text-foreground">{selected.name}</strong> ·{" "}
              {compact(selected.trips)} lifetime events ·{" "}
              {mode === "flow" ? (
                <>
                  {selected.net === 0
                    ? "balanced"
                    : `${selected.net > 0 ? "+" : "\u2212"}${compact(Math.abs(selected.net))} net ` +
                      `${selected.net > 0 ? "in" : "out"} (${(
                        (100 * selected.net) / (selected.trips || 1)
                      ).toFixed(1)}%)`}
                </>
              ) : selected.active ? (
                "used in the last six months"
              ) : (
                "dormant"
              )}
            </>
          ) : ready ? (
            mode === "flow"
              ? // The section lede carries the encoding; repeating it under each
                // of three maps is noise, not clarity.
                "Select a station for its net flow."
              : "Select a station for its lifetime events. Hollow dots are dormant — no trips in the last six months of this system's data."
          ) : (
            "Map loads when you reach it."
          )}
        </figcaption>
      </figure>
    </div>
  );
}
