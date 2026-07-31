# Spec 029 — Reproducibility release: a clean clone rebuilds, or says why not

## Status

Ready. Written 2026-07-31 from externally-reviewed, author-verified findings.

## Context

The reproducibility contract is strong in concept and incomplete in
practice. Verified gaps:

- `pipeline/requirements.txt` carries lower bounds only — no lock, no
  Python version pin. Another machine resolves different versions.
- Extraction is DELETE-then-load per system (`etl.py:345-350`) and not
  transactional: a late failure leaves a partially destroyed warehouse.
- DuckDB memory (10 GB) and threads (8) are hardcoded; extensions install
  from the network at run time.
- The encoding-repair cache is keyed by filename, not source checksum — a
  republished source file accepted with `--accept-changes` can serve a
  stale repaired copy.
- Manifest entries without checksums are skipped rather than refused.
- van-mobi `2025-05` date-order ambiguity is a silent default
  (month-first); known exceptions should be explicit mappings and new
  ambiguity should abort.
- The freshness gate proves warehouse→JSON reproducibility only. Nothing
  reconciles `rows_landed` against source record counts — the blind spot
  the quality report (post-028) names honestly. The external reviewer's own
  reconciliation found source and landed counts agree exactly today; the
  gate makes that a property, not an observation.
- No CI exists; nothing runs on a clean clone.

## Depends On

028 (the report the gates assert against must be truthful first).

## Scope

- **Sources touched:** none downloaded anew; source files are re-read for
  the reconciliation counts (cached by checksum).
- **Cities touched:** all three, published unchanged.
- **Tier:** neither.
- **Published artifacts change:** No (pipeline mechanics only). The quality
  report gains the source-reconciliation section — it regenerates under
  028's gate.

## Changes

1. Pin the toolchain: `requirements.lock` (hash-pinned) plus a stated
   Python version; runbook installs from the lock. DuckDB version pinned;
   extensions vendored or version-pinned with an offline path.
2. Transactional extraction: stage-and-swap (or a transaction) so an abort
   leaves the previous warehouse state intact. Demonstrated by a planted
   mid-extract failure in a test.
3. Strict manifests: an entry without a checksum aborts the run with a
   named error. Test plants one.
4. Every derived cache (encoding repair, any future) keyed by source
   checksum; test plants a filename collision with different content.
5. Explicit date-order exception mapping for van-mobi `2025-05`; any new
   ambiguous file aborts. Test plants an ambiguous fixture.
6. Source-count reconciliation: per-file record counts (computed once,
   cached by checksum) compared to `rows_landed` per file; mismatch fails
   `make check`. The quality report's funnel opens with this reconciliation
   instead of disclaiming it.
7. Resource limits configurable (env or flags) with the current values as
   defaults; documented in the runbook.
8. A small committed fixture dataset (synthetic, licence-clean, a few
   hundred rows per system covering the era formats) and a
   `make check-fixture` end-to-end path: download-skip → extract → clean →
   conform → model → publish → report on fixtures. GitHub Actions workflow
   runs fixture pytest + vitest + typecheck + build on push/PR. Full-data
   validation stays local/manual and the runbook says so.

## Acceptance Criteria

- [ ] A clean clone with the pinned toolchain runs the fixture pipeline
      end-to-end green with no network access beyond package install.
- [ ] A planted mid-extract failure leaves the prior warehouse queryable
      and unchanged (test).
- [ ] A manifest entry missing its checksum aborts extraction (test).
- [ ] A cache keyed to a checksum serves nothing for changed content under
      the same filename (test).
- [ ] van-mobi 2025-05 parses via an explicit mapping entry; a planted
      ambiguous fixture aborts (test).
- [ ] Per-file source record counts reconcile to `rows_landed` across the
      full archive; a planted mismatch fails `make check` (test); the
      quality report states the reconciliation result.
- [ ] CI runs on a clean GitHub-hosted runner: fixture pipeline, both
      suites, typecheck, build — green on the PR that introduces it.
- [ ] Runbook updated: lock install, resource flags, fixture path, and the
      van-mobi 2022-10 archived-copy caveat retained honestly.

## Data Integrity Checklist

- ~~Manifest entry for every new source file~~ — no new sources (fixtures
  are synthetic and carry a note saying so).
- [ ] Schema drift mapped explicitly — the ambiguity abort strengthens it.
- [ ] Row accounting closes — now against source counts, not only landed.
- ~~Metrics defined identically~~ — no metric changes.
- [ ] Committed artifacts reproduce byte-for-byte (must be unchanged).
- [ ] Site copy derives from the data window — untouched.
- ~~New encodings explained~~ — none.
- ~~Attribution~~ — no source changes.
- [ ] No raw trip data committed — fixtures are synthetic and small.

## Testing

The planted-failure tests named above are the deliverable, in the 009b
style: each guard demonstrated by a violation that fails. Full-archive
reconciliation run once locally and recorded in the spec at complete.

## Out of Scope

Branch protection, Dependabot, releases, community files — 031. Analytical
changes — 030.

## Rollback

Pipeline-internal; revert the merge. The warehouse schema gains only
additive audit columns; artifacts must not change, so a bad merge shows up
as freshness-gate failure immediately.
