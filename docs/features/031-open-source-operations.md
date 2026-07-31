# Spec 031 — Open-source operations

## Status

Draft — written light 2026-07-31; firmed at load, shaped by 029's CI.

## Context

The repository is public with no `.github` directory: no CI on PRs, no
branch protection, no releases or changelog, no contributor/security
policy, no dependency automation, and GitHub cannot classify the licence
(resolved in 028). A public data project claiming rigor needs its process
visible, not only its artifacts.

## Depends On

029 (the fixture CI this formalizes), 028.

## Scope

Repository configuration and documents only. No pipeline, no artifacts,
no site changes. Published artifacts change: No.

## Changes (firmed at load)

1. `.github/`: PR workflow (fixture pytest, vitest, typecheck, build,
   `make check-fixture`, docs link check), issue templates, PR template.
2. Branch protection on `main`: PRs + green CI required (owner grants via
   settings or authorizes `gh api`).
3. Dependabot (npm + pip), grouped monthly.
4. `CONTRIBUTING.md` (the /feature workflow, the gates, how to run
   fixtures), `CODE_OF_CONDUCT.md`, `SECURITY.md`.
5. First tagged release with changelog; release provenance: git SHA,
   artifact manifest hash, toolchain versions, data windows per system.
6. Data dictionary + warehouse schema doc, generated not hand-written
   where possible.
7. Scheduled monthly-refresh reminder (issue or action), runbook-linked.

## Acceptance Criteria (firmed at load)

- [ ] A PR from a clean fork runs CI green and cannot merge red.
- [ ] Release v1 exists with provenance and changelog.
- [ ] Community files render on GitHub's community-profile checklist.
- [ ] A contributor can run the fixture pipeline from CONTRIBUTING alone.

## Out of Scope

New cities, analytics, site changes. Full-archive CI (stays local).

## Rollback

Configuration only; every piece removes cleanly.
