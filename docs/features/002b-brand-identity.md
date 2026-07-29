# Spec 002b — Brand identity assets

## Status

Ready

## Context

Spec 002 shipped a placeholder favicon — two circles and a frame I drew to
silence a console 404. The identity is now decided and needs building properly.

Two marks, because one cannot do both jobs:

- **Logo:** the German StVO 1992 *Sinnbild Radfahrer* pictogram beside the
  canonical 11-point flag maple leaf. Wide, and it turns to mud below ~64px.
- **Favicon:** an eight-spoke bicycle wheel with the red leaf at its hub. Square,
  and legible at 16.

Numbered `002b` rather than taking a roadmap slot: this is a follow-on to the
design-system port, and inserting it would renumber twenty-five downstream
specs.

## Depends On

- Spec 002 — design tokens and the `public/` directory. Complete as of `7093bac`.

## Scope

- **Sources touched:** none — no data.
- **Cities touched:** none. **Tier:** neither.
- **Published artifacts change:** No. `src/data/generated/` stays empty.

## Provenance and rights

Recorded here because this project does not ship anything whose origin it
cannot state.

| Asset | Origin | Terms |
| --- | --- | --- |
| Bicycle pictogram | German StVO 1992 *Sinnbild Radfahrer*, via Wikimedia Commons | Public domain — `PD-VzKat` / `PD-GermanGov`, §5(1) UrhG. No attribution required, no restrictions on commercial or derivative use |
| 11-point maple leaf | The leaf of the National Flag of Canada; path taken from canadatest.ca | Order in Council P.C. 1965-1623 s.4 permits use in a design or trademark subject to "good taste", disclaiming exclusive rights, and not preventing others' use. CIPO no longer requires the disclaimer |

**Constraints this places on the marks, all satisfied by the chosen designs:**

- No use of the **flag device** itself (red-white-red with the leaf) — that is
  Trademarks Act s.9(1)(e) and needs Canadian Heritage consent.
- No imitation of the **Canada wordmark** or the Federal Identity Program flag
  symbol. The leaf is never set beside a serif "Canada".
- **No exclusivity is claimed** in the maple leaf.
- The favicon deliberately avoids **a bare leaf centred in an open ring** — that
  is Air Canada's *rondelle*, and the compounding facts (Air Canada was formerly
  Trans-Canada Air Lines; this is transport; the name starts "Trans-Canada")
  make that composition a real conflict rather than a theoretical one. The
  eight-spoke wheel with a rim and hub reads as a different object.

None of the above is legal advice; a Canadian trademark agent should clear the
marks before any commercial use.

## Changes

1. **`public/logo.svg`** — the lockup: pictogram and leaf, no divider, on a
   viewBox sized to the artwork.
2. **`public/favicon.svg`** — the eight-spoke wheel. Rim in ink, spokes in grey
   so they recede, red leaf at the hub. Carries a
   `prefers-color-scheme: dark` rule so the rim inverts to light ink on dark
   browser chrome instead of disappearing.
3. **Raster fallbacks**, rendered from the SVG at exact pixel sizes:
   `favicon.ico` (16, 32, 48), `apple-touch-icon.png` (180, on paper, padded),
   `icon-192.png`, `icon-512.png`.
4. **`site.webmanifest`** naming the app and pointing at the PWA icons.
5. **Wire into `index.html`** — replace the placeholder link with the SVG icon,
   the `.ico` fallback, the apple-touch icon, and the manifest.
6. **Use the logo in `App.tsx`**, replacing the plain text brand.
7. **Footer line: "Not affiliated with or endorsed by the Government of
   Canada."** Shipping a national symbol on a site about public data makes the
   disclaimer worth its one line.
8. **Delete the spec-002 placeholder favicon.**

## Acceptance Criteria

- [ ] `public/favicon.svg` renders the eight-spoke wheel with a red leaf hub and
      inverts its rim under `prefers-color-scheme: dark`
- [ ] The wheel is legible at 32px — rim, spokes and leaf all distinguishable —
      and its silhouette survives at 16px
- [ ] `favicon.ico` contains 16, 32 and 48 pixel images and is a valid ICO
- [ ] `apple-touch-icon.png` is 180×180 with an opaque background, since iOS
      does not composite transparency
- [ ] `icon-192.png` and `icon-512.png` exist and are referenced by
      `site.webmanifest`
- [ ] `index.html` references the SVG icon, the ICO fallback, the apple-touch
      icon and the manifest; no request 404s
- [ ] The header renders `logo.svg` and the footer carries the
      non-affiliation line
- [ ] No console errors or failed requests on load
- [ ] The placeholder favicon from spec 002 is gone
- [ ] `npm test`, `npm run typecheck`, `npm run build` all exit 0
- [ ] Provenance for both source assets is recorded in the repo

## Data Integrity Checklist

- ~~Manifest / row accounting / artifacts reproduce / metrics~~ — n/a, no data,
  no ETL, no published artifacts
- ~~Copy derives from the data window~~ — n/a; the footer line is a legal
  statement, not a data claim
- [ ] Encodings explained — n/a for a logo, but asset provenance is documented
      so no shipped mark has unstated origin
- [ ] Attribution: both source assets' terms recorded; neither requires
      attribution, and that fact is written down rather than assumed
- [ ] No raw data committed

## Testing

- Vitest: pin that `index.html` references each icon and the manifest, and that
  the footer disclaimer is present.
- Browser: load, confirm zero failed requests, screenshot the favicon at 16 and
  32 against light and dark tab chrome.
- Verify the ICO byte structure (magic, image count, per-entry dimensions)
  rather than trusting the encoder.

## Out of Scope

- The header/nav design — spec 015
- Open Graph and social share images
- Any per-city or per-system iconography

## Rollback

Single revert. Restores the spec-002 placeholder favicon; nothing else depends
on these assets.
