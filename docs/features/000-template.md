# Spec NNN — Title

Copy this file to `NNN-short-slug.md` and fill it in. The sections
`/feature load`, `review`, and `complete` depend on are marked **required**.

## Status

Draft | Ready | In progress | Complete

## Context

Why this feature, why now. What is true today that makes it necessary. Link
the decision in `docs/decisions.md` it follows from, if there is one.

## Depends On

**(required)** — list specs that must be complete first, or write `None.`

## Scope

**(required)**

- **Sources touched:** e.g. BIXI Montreal 2024 trip files, ECCC Montreal daily
- **Cities touched:** e.g. Montreal, Toronto
- **Tier:** 1 (docked, like-for-like) | 2 (dockless panel) | both | neither
- **Published artifacts change:** Yes / No — if yes, name them. This decides
  whether the reproducibility gate runs at test and complete.

## Changes

What gets built, in the order it gets built. One numbered item per unit of
work, each small enough to verify on its own.

## Acceptance Criteria

**(required)** — these become the goals verbatim. Write them so each one can
be checked as true or false by someone who did not build it. Avoid "works
well"; prefer "every trip in the 2024 Montreal file lands in exactly one of
kept, dropped-short, or dropped-null-station, and the three counts sum to the
file's row count".

- [ ]
- [ ]

## Data Integrity Checklist

**(required)** — tick what applies, strike through what genuinely does not,
with a reason. `/feature review` enforces these.

- [ ] Manifest entry with checksum and licence for every new source file
- [ ] Schema drift mapped explicitly; unknown headers stop the pipeline
- [ ] Row accounting closes; the quality report reflects it
- [ ] Metrics defined identically across tier-1 cities, or labelled as not
      comparable
- [ ] Committed artifacts reproduce byte-for-byte from a fresh run
- [ ] Site copy derives from the data window — no hardcoded counts or dates
- [ ] New encodings explained where a first-time viewer will look
- [ ] Source licence attribution present in manifest and on the site
- [ ] No raw trip data committed

## Testing

What proves this works — contract tests, unit tests, component tests, or for
a document deliverable, what gets re-derived from source to verify it.

## Out of Scope

What this deliberately does not do, so review does not flag it as missing and
a later spec knows it is still open.

## Rollback

How to undo this if it ships wrong. For artifact changes, name the previous
good artifacts. For schema or manifest changes, say what else depends on them.
