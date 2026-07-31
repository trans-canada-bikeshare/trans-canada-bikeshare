# Spec 030 — Analytical integrity: claims sized to what was computed

## Status

Ready, with one owner decision required at load. Written 2026-07-31.

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

- [ ] The forecast section's name, copy, artifact self-description, and
      validation method are mutually consistent under the chosen path.
- [ ] Every completeness threshold lives in the central declaration; a
      planted rogue threshold in a publisher query fails a test.
- [ ] Any month excluded or newly included by unification is enumerated in
      the spec record with before/after counts.
- [ ] Hourly surfaces say "rounded to the nearest hour" for Vancouver.
- [ ] All artifacts validate against their schemas at publish and in CI;
      a planted shape drift fails.

## Data Integrity Checklist

- ~~Manifest~~ — no new sources.
- [ ] Metrics defined identically or labelled — the policy unification is
      exactly this; verdicts per metric at review.
- [ ] Committed artifacts reproduce byte-for-byte after regeneration.
- [ ] Site copy derives from the data window.
- [ ] Encodings explained — any changed forecast presentation re-checked.
- ~~Attribution~~ / [ ] No raw data — standard.

## Testing

Contract tests over schemas; planted-violation tests for the policy module;
existing suites; headed check of the forecast section (interaction is
output).

## Out of Scope

CI/community files (031), site accessibility (032), any new metric.

## Rollback

Artifact regenerations revert with the merge; schema files are additive.
