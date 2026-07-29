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

export function cityOf(id: string): string {
  return SYSTEMS[id as SystemId]?.city ?? id;
}

export function isSystemId(id: string): id is SystemId {
  return id in SYSTEMS;
}
