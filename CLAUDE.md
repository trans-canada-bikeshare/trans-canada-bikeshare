# Trans-Canada Bikeshare

Canada's bike share systems, measured the same way. One pipeline, one set of
definitions, one site, computed from each system's published open data and
compared like for like. Sister project to `mobi-transit-explorer`, the
single-city deep dive this generalizes.

## Context files

- @README.md — scope, tiers, and the principles this project is built on
- @docs/decisions.md — the log of choices that bind the work
- @docs/current-feature.md — what is in progress right now

## Workflow

Every feature runs through the `/feature` skill, in order:

```
/feature load <spec>   → /feature start → /feature test
                       → /feature review → /feature complete
```

Specs live in `docs/features/NNN-name.md`, written from
`docs/features/000-template.md`. One feature per branch, branched from an
up-to-date `main`.

## Invariants

These hold in every feature. `/feature review` blocks on them.

- **Nothing is guessed silently.** Unknown headers, codes, or values stop the
  pipeline. No bare `except`, no `fillna(0)` standing in for a missing field.
- **Every number traces to a pinned file** with a checksum and a licence in
  the manifest.
- **Like-for-like means identical definitions** — same units, filter, window,
  and null handling for every tier-1 city, or the metric is labelled as not
  comparable. Dockless (Calgary, Edmonton) never sits beside docked systems
  as a comparable column.
- **Committed artifacts reproduce** byte-for-byte from a fresh run.
- **Copy derives from the data window.** Prose may lag the data; it may never
  contradict it.
- **Raw trip data never enters git.**

## Status

Built end to end: pipeline (`pipeline/`, DuckDB star schema over the full
archive), site (`src/`, Vite/React reading committed aggregates), and real
gates. The commands are:

```
make check                      # manifest + metric registry + artifact freshness + quality report
.venv/bin/python -m pytest pipeline/tests
npm test && npm run typecheck && npm run build
```

`docs/runbook.md` is the operational truth: rebuild from nothing, monthly
refresh, known gaps. Rendered surfaces are verified in a **headed** browser
(`docs/decisions.md`, 2026-07-29) — headless and backgrounded tabs throttle
rAF and cannot tell a drawn map from a blank one. Never report a skipped
check as passed.
