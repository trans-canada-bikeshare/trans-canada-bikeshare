# Spec 026 — Accessibility and responsive pass

## Status

Complete. Shipped 2026-07-29 in `3edb79a`.

> **Written retrospectively on 2026-07-29**, from `3edb79a`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## What shipped

Keyboard reachability, visible focus, contrast, reduced-motion, and a width
sweep in both themes.

The substantive change: **chart legends carry their values without hover.** A
legend that only names a series forces a pointer to read the chart, which fails
both a keyboard user and anyone reading on a phone. Values are in the legend.

## Known gap, carried

Spec 021's maps are the one surface this pass does not cover, because they
landed after it. Its review found `role="img"` on a container holding six
focusable controls, and no text alternative — both fixed there, not here. A
future accessibility pass should treat the map as a genuinely interactive
region rather than an image.

## Where the record is

- `src/components/charts/`
- `docs/features/021-station-maps.md` — the map-specific findings
