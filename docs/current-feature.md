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

<!-- GAP: specs 004-020 shipped during the overnight autonomous run of
     2026-07-28/29 without their History lines being appended. The commits are
     the record until they are backfilled — `git log --oneline main` reads in
     order. Recorded as a gap rather than reconstructed from memory, because a
     History entry invented after the fact is worth less than a pointer to the
     commit that is actually true. -->

- 2026-07-29 `pending` — spec 021: station maps. MapLibre maps per system,
  lazily loaded; `stations.json` + `stations_meta.json`. Review (Opus, not
  Fable — Fable unavailable) found the maps rendered **zero dots**: MapLibre
  cannot parse `hsl(var(...))` and silently rejected the layer. Also fixed:
  per-map dot scales replaced by one shared ceiling, "retired" relabelled
  "dormant" (28 hollow dots are in the live GBFS feed), station labels now
  taken from whatever supplied the coordinate, Tukey-fence framing so
  Sherbrooke stops stretching Montreal 161 km wide. 56 vitest.
  `docs/features/021-station-maps.md`
