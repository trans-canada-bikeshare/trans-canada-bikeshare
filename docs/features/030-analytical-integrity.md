# Spec 030 — Analytical integrity: claims sized to what was computed

## Status

Complete. Merged 2026-07-31; the owner decision (Path A, rename) is recorded below.

## Owner decision required at load

The "Forecast" section estimates historical daily ridership under weather
scenarios with a level per observed calendar month; its holdout keeps month
levels in training. It is within-month scenario analysis, not temporal
forecasting. Two honest paths — the owner picks one at `/feature load`:

- **A (rename):** the section becomes "Weather scenario" (or similar); copy
  and nav updated; no model change. Cheap, fully honest.
- **B (upgrade):** keep the name, add rolling-origin temporal validation
  and a model form that can answer unseen months, publishing its (weaker)
  out-of-window error honestly alongside.

> **Decided at load, 2026-07-31: Path A — rename.** The owner chose the
> rename, with the temporal-validation upgrade available as a future spec
> if ever warranted. Also noted at load: the hourly-surface criterion was
> largely satisfied by spec 028 (the ±30-minute rounded-labels copy);
> start verifies the remaining hourly surfaces rather than assuming.

## Context

Verified findings this spec resolves (see the 2026-07-31 decisions entry
when 028 lands):

- Completeness policies diverge silently: the publisher's stated rule is
  "incomplete months are excluded from every series," but seasonality
  admits any system-month with more than 3 observed days
  (`publish.py:225`); other metrics apply different thresholds.
- Vancouver hour-of-day surfaces say "hour buckets"; the source now states
  the labels are *rounded to nearest hour* — phrasing on every hourly
  surface should say rounded, per the 028 decisions entry.
- Artifact consumers have no contract: the site trusts artifact shapes
  implicitly. JSON Schema contracts catch a publisher/site drift at build
  time rather than in production.

## Depends On

028 (truthful `fit_basis` baseline; Mobi facts recorded), 029 (CI to hold
the new contract tests).

## Scope

- **Sources touched:** none.
- **Cities touched:** all three.
- **Tier:** neither.
- **Published artifacts change: YES** — at minimum `forecast.json`
  (either path) and `seasonality.json` if the unified completeness policy
  moves any month; every change enumerated at review.

  > **Corrected at build, 2026-07-31: NO committed artifact changes.**
  > Both premises above resolved to nothing: under Path A the artifact's
  > `fit_basis` was already truthful (spec 028 fixed it), so the rename is
  > site-side strings only; and the completeness unification moved **zero
  > months** (enumeration below). The branch's artifact diff is empty and
  > `make check-artifacts` passes without regeneration. New files are the
  > 15 schema contracts and the policy declaration — code, not artifacts.

## The unification enumeration (acceptance criterion 3)

Zero months moved, in zero artifacts — verified, not assumed:

- The month rule (a system-month with ≤3 observed days, or a trailing
  month the source has not finished publishing) excludes exactly three
  system-months archive-wide: `mtl-bixi 2022-12` (1 day, 3 trips),
  `tor-bikeshare 2016-06` (1 day, 372 trips), `van-mobi 2026-07` (1 day,
  26 trips).
- **seasonality** previously used its own `HAVING count(DISTINCT
  date_key) > 3`; over every system-month ≥2017 the two rules select
  identical sets — 0 disagreements (warehouse-verified).
- **stations_yearly** previously had no rule; applying the month rule
  changes nothing because every station appearing in a stub month recurs
  elsewhere in the same year.
- **duration, flows, stations, stations_meta, meta, exclusions** are
  declared `whole_archive` with stated reasons (a median's published
  basis must equal the population it was taken over; flows' numerator
  and denominator must share a population; dot size comes from
  `dim_station.lifetime_events`) — deliberate, reasoned non-application
  rather than blind harmonization. Measured had they been filtered:
  duration's basis shrinks by 3/372/25 with no quartile moving; no
  top-8 flow pair changes; 105 stations would move their net by 1–10
  events (largest drawn: 9). The declaration's first draft said "1 to 6"
  and "sixth decimal"; the reviewer measured both false and they were
  re-derived — recorded here because the declaration exists precisely so
  its numbers cannot be recalled wrong.

Accepted as-is this spec, from review: the threshold scanner's
own-coverage check carries slack (docstrings and non-call-site SQL count
toward what it has "seen"), so it is a smoke check, weaker than its name;
and tuple-assignment / arithmetic-expression named constants still evade
the scan. Both noted rather than fixed — the plain and annotated
assignment forms that occur in this codebase are covered.

## Changes

1. Execute the owner's path A or B for the forecast section.
2. One completeness policy module: per-metric rules declared in one place
   (registry or adjacent), each with a stated reason; publisher queries
   consume the declarations; a test asserts no query embeds its own
   threshold.
3. Hourly surfaces describe Vancouver's labels as rounded.
4. JSON Schema for every published artifact, validated at publish time and
   in vitest against the committed files.

## Acceptance Criteria

- [x] The forecast section's name, copy, artifact self-description, and
      validation method are mutually consistent under the chosen path.
- [x] Every completeness threshold lives in the central declaration; a
      planted rogue threshold in a publisher query fails a test.
- [x] Any month excluded or newly included by unification is enumerated in
      the spec record with before/after counts.
- [x] Hourly surfaces say "rounded to the nearest hour" for Vancouver.
- [x] All artifacts validate against their schemas at publish and in CI;
      a planted shape drift fails.

## Data Integrity Checklist

- ~~Manifest~~ — no new sources.
- [x] Metrics defined identically or labelled — the policy unification is
      exactly this; verdicts per metric at review.
- [x] Committed artifacts reproduce byte-for-byte after regeneration.
- [x] Site copy derives from the data window.
- [x] Encodings explained — any changed forecast presentation re-checked.
- ~~Attribution~~ — no new sources. [x] No raw data — diff is code, schemas, tests, docs.

## Testing

Contract tests over schemas; planted-violation tests for the policy module;
existing suites; headed check of the forecast section (interaction is
output).

## Out of Scope

CI/community files (031), site accessibility (032), any new metric.

## Rollback

Artifact regenerations revert with the merge; schema files are additive.
