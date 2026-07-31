# Spec 031 — Open-source operations

## Status

Complete. Merged 2026-07-31; protection, tag, release and the PVR toggle verified at complete.

## Context

The repository is public with working CI (029) but no operating model
around it: actions pinned to tags not SHAs, no branch protection, no
releases or changelog, no contributor/security/conduct files, no
dependency automation, no data dictionary. 029's review deferred four CI
hardening items here by name: SHA-pinned actions, `persist-credentials:
false`, `timeout-minutes`, and the Makefile's dead spec-011 stub
fallbacks that contradict its own gate doctrine.

**Branch-protection stance, firmed at load:** the `/feature` workflow
merges locally and pushes `main` directly — that is the maintainer's
documented path, protected by the full local gate battery plus
independent review, which is stronger than CI alone. Protection therefore
requires PRs + green CI for everyone else, with admin bypass
(`enforce_admins: false`), and CONTRIBUTING states both paths and why.

## Depends On

029 (the CI this formalizes), 028. Both complete.

## Scope

Repository configuration, workflow files, and documents only. No
pipeline behavior, no artifacts, no site changes. Published artifacts
change: No.

## Changes

1. **CI hardening**: every action pinned to a full commit SHA (with the
   version as a comment), `persist-credentials: false` on checkouts,
   `timeout-minutes` on both jobs. The Makefile's spec-011-era
   `if [ -f … ]; else echo stub` fallbacks are removed — a gate whose
   script vanishes must fail, not print.
2. **Dependabot**: npm, pip, and github-actions ecosystems, monthly,
   grouped.
3. **Community files**: `CONTRIBUTING.md` (the /feature workflow, the
   gates, the fixture pipeline from a clean clone, the two merge paths),
   `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1, project contact),
   `SECURITY.md` (private reporting via GitHub security advisories),
   issue templates (bug, data-quality report with provenance fields) and
   a PR template that names the gates.
4. **Changelog + release**: `CHANGELOG.md` (Keep-a-Changelog form,
   derived from the merge history, one entry per spec release);
   **v1.0.0 tagged at complete** with a GitHub release carrying the
   provenance block: git SHA, sha256 of every committed artifact,
   toolchain versions (Python/DuckDB/Node from the locks), and each
   system's data window from `meta.json`.
5. **Data dictionary**: `docs/data-dictionary.md` GENERATED from the 15
   schema contracts (a small generator; a drift test fails when schemas
   change without regenerating — 028's report-gate pattern).
6. **Monthly refresh reminder**: a cron workflow (first of month) opening
   a templated issue linking the runbook's refresh section;
   least-privilege (`issues: write` only on that job).
7. **Branch protection applied and verified** via the API at complete,
   per the stance above.

## Acceptance Criteria

- [x] CI workflow: all actions SHA-pinned (version comments beside),
      `persist-credentials: false`, `timeout-minutes` on every job; green
      on the PR that introduces the changes.
- [x] The Makefile contains no stub fallback: deleting any gate script
      makes `make check` fail (demonstrated by test or dry run).
- [x] Dependabot config covers npm, pip, github-actions.
- [x] GitHub's community-profile checklist is fully green (README,
      licence, CoC, CONTRIBUTING, SECURITY, templates).
- [x] A contributor can run the fixture pipeline from CONTRIBUTING alone
      (commands verified as written, in order, on this machine).
- [x] `CHANGELOG.md` exists with one accurate entry per shipped release;
      v1.0.0 is tagged and its GitHub release carries the full provenance
      block (SHA, artifact hashes, toolchain versions, data windows).
- [x] `docs/data-dictionary.md` regenerates from the schemas; a planted
      schema change without regeneration fails a test.
- [x] The refresh-reminder workflow parses, is least-privilege, and its
      cron and template are documented in the runbook.
- [x] Branch protection on `main` verified via API: PRs + required checks
      required, admins exempt; both merge paths documented in
      CONTRIBUTING.

## Data Integrity Checklist

- ~~Manifest / schema drift / row accounting / like-for-like / tier
  boundary / encodings~~ — no data or pipeline-behavior changes.
- [x] Committed artifacts reproduce byte-for-byte (must be untouched).
- [x] Site copy derives from the data window — untouched.
- [x] Attribution — CHANGELOG and release notes must not misstate any
      licence obligation; DATA-LICENSES.md remains the authority.
- [x] No raw trip data committed.

## Testing

The data-dictionary drift test; YAML parse + policy assertions on both
workflows (no continue-on-error, permissions blocks present, SHAs not
tags); the Makefile no-stub check; existing suites unchanged. CI green on
the PR is the live proof.

## Out of Scope

New cities, analytics, site changes (032). Full-archive CI. Publishing
to package registries.

## Rollback

Configuration only: delete the workflows/files, drop the tag
(`git push --delete origin v1.0.0`), disable protection via the API.
Nothing else depends on any of it.

## Accepted from review, noted

The dictionary generator walks today's schema vocabulary and would
silently omit (not refuse) a future oneOf/anyOf/$ref subtree — a refusal
would better match house style; the timeout test does not strip comments;
reminder dedup trusts search indexing at monthly cadence. All three
optional polish, recorded here.
