/**
 * The diverging colour scale for net flow, in its own module.
 *
 * It lives here rather than in StationMap so the Flows section's legend can
 * import it without pulling in the map component — and with it MapLibre, which
 * is lazily loaded precisely because it is 257 KB gzipped against a 78 KB
 * bundle. A single static import from StationMap would have undone that.
 *
 * Two palettes, not one. An earlier version used a single set and claimed it
 * held up on both basemaps; measured against the actual renders it did not —
 * indigo came out at 1.58:1 on the dark basemap against WCAG 1.4.11's 3:1, so
 * the most strongly accumulating stations were the hardest to see. Every stop
 * now clears 3:1 against the basemap it is drawn on, except the near-neutral
 * amber over water (2.8:1), where stations essentially never sit.
 *
 * Amber drains — gives out more bikes than it takes in. Indigo accumulates.
 * Blue against orange is also the standard choice for a diverging scale that
 * survives the common colour-vision deficiencies, which matters here because
 * the two ends are close in luminance by construction.
 */
export const FLOW_STOPS: Record<"light" | "dark", string[]> = {
  light: ["#8a3d06", "#96601a", "#3f4a57", "#35599b", "#241d75"],
  dark: ["#ffc14d", "#e0a83f", "#9ca3af", "#7d9ee6", "#6f7fe8"],
};

/** Where each stop sits on the rate axis. Clipped at ±15%: stations do reach
 *  ±0.44 and ±0.73, and scaling to them would flatten every ordinary dock to
 *  neutral. A saturated dot means "at least this imbalanced", which the
 *  section states — an encoding that clips has to say so. */
export const FLOW_DOMAIN = [-0.15, -0.04, 0, 0.04, 0.15] as const;
