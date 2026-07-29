# Spec 015 — App shell

## Status

Complete. Shipped 2026-07-28 in `0ddd43c`.

> **Written retrospectively on 2026-07-29**, from `0ddd43c`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## What shipped

Nav with scrollspy, light and dark parity, the eyebrow and hairline system,
reveal motion honouring `prefers-reduced-motion`.

Design tokens are the Vancouver project's verbatim, pinned by 26 tests in
`src/design-tokens.test.ts` so a drift is a failing test rather than a
discovered inconsistency. New components extend the language rather than
departing from it — spec 021's review treated a component inventing its own
type ramp as a finding.

## Where the record is

- `src/App.tsx`, `src/index.css`, `src/lib/theme.ts`
- `src/design-tokens.test.ts`
