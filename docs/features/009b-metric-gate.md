# Spec 009b — The enforcement 009 was missing

## Status

Complete — written alongside the work, 2026-07-29.

## Context

Spec 009 shipped `pipeline/mappings/metric_support.json`, which says of itself:

> Publishing a cross-city series for a metric not marked supported in every
> system it contains is an ERROR, checked by `make check-metrics` — not a
> matter of anyone remembering.

That was false. `pipeline/check_metrics.py` did not exist. The Makefile target
printed `check-metrics: stub — spec 009 makes this real.` and exited 0, so
`make check` reported overall success without running it. The only enforcement
was `guard()` inside `publish.py`, which runs at publish time and only for the
metrics whose author remembered to call it.

Spec 021 is the proof that the distinction matters. It published
`stations.json` and `stations_meta.json` — a per-system series across all three
cities — and called `guard()` for neither. Every gate passed. The violation was
found by a human reading the diff, which is exactly what the registry's own
comment says should not be necessary.

This is the same shape as the raw-data gate that used `git diff --cached`
before anything was staged: a gate that could not fail, sitting in a list of
gates that had all passed. It is numbered `009b` rather than a new number
because it completes 009 rather than extending it — 009 was half-built and the
record should say so.

## Depends On

- Spec 009 — the registry itself. Complete as of `cb10b98`.
- Spec 014 — the published artifacts this reads. Complete.

## Scope

- **Sources touched:** none. Reads committed artifacts and the registry.
- **Cities touched:** all three, indirectly. **Tier:** 1.
- **Published artifacts change:** **No.** This only reads them.

## Changes

1. **`pipeline/check_metrics.py`.** Reads `src/data/generated/` as committed —
   it does not re-run the pipeline and does not need the warehouse, so it
   checks what the site would actually serve rather than what a fresh publish
   would produce.
2. **Every artifact must be declared or explicitly exempt.** This is the
   central rule, and it is the inverse of the obvious one. A checker that
   validated only the artifacts it already knew about would have been just as
   silent for 021. Adding a new per-system artifact is now a decision.
3. **Exemptions carry reasons.** `meta`, `incomplete_months` and `exclusions`
   carry system ids without being comparative metrics. Each says why, because
   "it is not really a metric" is precisely the argument that would let an
   ungoverned series through.
4. **Shape-agnostic walk.** System ids are found anywhere in the structure,
   under `system_id` or under `stations.json`'s compact `s` key, so a nested
   series (`{"series": [...]}`) is covered without this file knowing which
   artifacts nest.
5. **Unknown system ids fail.** A typo'd or new id cannot pass silently.
6. **The Makefile target is unconditional.** No `|| true`, no `if [ -f ... ]`.

## Acceptance Criteria

- [x] `make check-metrics` exits non-zero on a violation and 0 otherwise
- [x] An artifact publishing a system the registry marks unsupported fails,
      and the failure quotes the registry's stated reason
- [x] An artifact that is neither declared nor exempt fails — **the 021 case**
- [x] An unknown system id fails
- [x] An empty artifact directory fails rather than passing vacuously
- [x] `make check` runs it for real as part of the three-gate sweep
- [x] The gate is proven to fire: every test plants a specific violation and
      asserts the failure names it
- [x] Passes against the real committed artifacts (10/10 governed or exempt)

## Data Integrity Checklist

- ~~Provenance~~ — n/a, reads no source files
- [x] Nothing guessed — an undeclared artifact is an error, never assumed
      benign; an unknown system id is an error, never skipped
- [x] Metrics defined identically — this *is* that check, made executable
- ~~Artifacts reproduce~~ — n/a, publishes nothing
- [x] Copy derives from the data — the Makefile comment and the module
      docstring both state the stub history rather than quietly replacing it
- ~~Row accounting~~ — n/a, no ETL change
- [x] No raw data committed

## Testing

12 pytest cases in `pipeline/tests/test_check_metrics.py`, each planting a
violation: undeclared artifact (with and without system ids), unsupported
system in a governed series, unknown id, ids under the compact key, nested
series, empty directory. Plus structural tests that every exemption has a real
reason, that declared and exempt are disjoint, and that every declared metric
exists in the registry.

One test runs against the real committed artifacts, which is not a tautology —
those are the files the site serves.

## Out of Scope

- Whether a `comparable: false` metric is *presented* as a three-city column.
  That is a rendering question; the registry marks comparability and the site
  labels it, but this gate checks publication, not layout.
- Backfilling `guard()` calls into `publish.py` beyond the one 021 needed. The
  file-level check now covers what `guard()` misses.

## Rollback

Single revert. `make check-metrics` returns to a stub, and the registry's
claim about itself becomes false again — which is the state this spec exists
to end.
