/** The three tier-1 systems, and the one colour decision that matters.
 *
 * Series colour is assigned here and nowhere else, so a city is the same hue on
 * every chart on the site. Getting this wrong — Vancouver blue on one chart and
 * orange on the next — is the fastest way to make a comparison unreadable.
 *
 * The palette is the design system's accent plus two hues chosen to hold up
 * against it in both themes and to stay distinguishable for the most common
 * forms of colour vision deficiency. It deliberately avoids red, which belongs
 * to the logo and to nothing else.
 */

export type SystemId = "van-mobi" | "mtl-bixi" | "tor-bikeshare";

export interface SystemMeta {
  id: SystemId;
  city: string;
  system: string;
  /** CSS custom property holding this system's series colour. */
  varName: string;
}

export const SYSTEMS: Record<SystemId, SystemMeta> = {
  "van-mobi": {
    id: "van-mobi",
    city: "Vancouver",
    system: "Mobi by Rogers",
    varName: "--series-van",
  },
  "mtl-bixi": {
    id: "mtl-bixi",
    city: "Montreal",
    system: "BIXI",
    varName: "--series-mtl",
  },
  "tor-bikeshare": {
    id: "tor-bikeshare",
    city: "Toronto",
    system: "Bike Share Toronto",
    varName: "--series-tor",
  },
};

/** Stable display order: west to east, which is also how the name reads. */
export const SYSTEM_ORDER: SystemId[] = ["van-mobi", "mtl-bixi", "tor-bikeshare"];

export function seriesColor(id: SystemId): string {
  return `hsl(var(${SYSTEMS[id].varName}))`;
}

/**
 * The same colour, resolved to a literal `hsl(...)`.
 *
 * `seriesColor` returns a CSS custom property reference, which is correct for
 * anything the browser's style engine renders — every SVG chart on this site
 * hands it straight to the DOM. MapLibre is different: it parses colours in
 * JavaScript, where `var()` means nothing, and rejects the whole layer rather
 * than falling back. That is how spec 021 originally shipped three maps that
 * added their GeoJSON source and then drew nothing at all.
 *
 * Returns null if the token is missing, so a caller can fail visibly instead
 * of substituting a colour nobody chose.
 */
export function resolvedSeriesColor(id: SystemId): string | null {
  if (typeof getComputedStyle === "undefined") return null;
  const triplet = getComputedStyle(document.documentElement)
    .getPropertyValue(SYSTEMS[id].varName)
    .trim();
  return triplet ? `hsl(${triplet})` : null;
}

export function cityOf(id: string): string {
  return SYSTEMS[id as SystemId]?.city ?? id;
}

export function isSystemId(id: string): id is SystemId {
  return id in SYSTEMS;
}
