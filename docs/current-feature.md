# Current Feature

## Status

_No feature in progress._

## Lifecycle

- [ ] load
- [ ] start
- [ ] test
- [ ] review

## Goals

<!-- Filled by `/feature load` from the spec's Acceptance Criteria, verbatim. -->

## Notes

<!-- Dependencies, sources and cities touched, licence constraints, and
     whether this feature changes any published artifact. -->

## History

<!-- Appended by `/feature complete`, oldest first. ONE LINE per feature:
     `YYYY-MM-DD` `<sha>` — what shipped. Spec path.
     The detail lives in the merge commit; `git show <sha>` is the record.
     Keep this file cheap to load — it enters context every session. -->

- 2026-07-28 `5425262` — spec 001: source column audit across all three systems.
  E-bike share and membership mix confirmed **not** three-city comparable;
  BIXI and Toronto era maps and the BIXI station bridge established.
  `docs/features/001-source-column-audit.md` → `docs/source-audit.md`
- 2026-07-28 `7093bac` — spec 002: repo scaffold. Python pipeline skeleton,
  Vite/React/Tailwind site, design tokens ported verbatim from the Vancouver
  project (26 pinned tests), `make check` gate stubs. 32 vitest + 7 pytest.
  `docs/features/002-repo-scaffold.md`
- 2026-07-28 `80775e3` — spec 002b: brand identity. StVO bike + flag leaf logo,
  eight-spoke wheel favicon with theme-adaptive rim, ico/apple-touch/PWA
  rasters, asset provenance and rights recorded. 45 vitest.
  `docs/features/002b-brand-identity.md`
- 2026-07-28 `1d5bd16` — spec 003: per-city manifests and downloaders. Discovery
  separated from download, checksum pinning with drift refusal, inventory gate,
  LICENSE corrected (BIXI unsupported claim removed, Toronto attribution added).
  26 pytest. `docs/features/003-manifests-and-downloaders.md`
