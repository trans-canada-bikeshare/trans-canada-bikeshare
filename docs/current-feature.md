# Current Feature: 031 Open-source operations

## Status

In Progress

## Lifecycle

- [x] load — 2026-07-31
- [x] start — 2026-07-31
- [ ] test
- [ ] review

## Goals

- CI workflow: all actions SHA-pinned (version comments beside),
  `persist-credentials: false`, `timeout-minutes` on every job; green on
  the PR that introduces the changes.
- The Makefile contains no stub fallback: deleting any gate script makes
  `make check` fail (demonstrated by test or dry run).
- Dependabot config covers npm, pip, github-actions.
- GitHub's community-profile checklist is fully green (README, licence,
  CoC, CONTRIBUTING, SECURITY, templates).
- A contributor can run the fixture pipeline from CONTRIBUTING alone
  (commands verified as written, in order, on this machine).
- `CHANGELOG.md` exists with one accurate entry per shipped release;
  v1.0.0 is tagged and its GitHub release carries the full provenance
  block (SHA, artifact hashes, toolchain versions, data windows).
- `docs/data-dictionary.md` regenerates from the schemas; a planted
  schema change without regeneration fails a test.
- The refresh-reminder workflow parses, is least-privilege, and its cron
  and template are documented in the runbook.
- Branch protection on `main` verified via API: PRs + required checks
  required, admins exempt; both merge paths documented in CONTRIBUTING.

## Notes

- **Depends on:** 029 (`a2ffdd1`), 028 (`bbf65e3`) — both in History.
- **Sources / cities / artifacts:** none touched; config and docs only.
- **Branch-protection stance (firmed at load):** PRs + green CI for
  contributors; admin bypass for the /feature workflow's local-merge
  path, documented with reasons in CONTRIBUTING.
- **Sequencing:** protection and the v1.0.0 tag/release happen at
  complete (after the merge), then verified via API.
- **Implementation:** one Opus agent for files/workflows/docs; gh API
  operations (protection, release) in the orchestrating context.

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

<!-- Backfilled 2026-07-29 from `git log`, not from memory. Specs 005-019 and
     025-026 shipped in batched commits during the overnight autonomous run
     rather than one merge each, so these lines point at the commit that
     actually carried the work. Where several specs shared a commit, they share
     a line — splitting them would invent a sequence that did not happen. -->

- 2026-07-28 `a343ccc`+`cb10b98` — specs 005-008: the warehouse. Era maps,
  staged extract → clean → conform → model, Kimball star schema over the full
  archive. `docs/features/005-008-warehouse.md`
- 2026-07-28 `cb10b98` — specs 009-010 and 014: metric support registry, the
  generated quality report, and the publish step that writes the committed
  aggregates. **009 shipped only half-built** — the registry landed, its
  `make check-metrics` enforcement was a stub until 2026-07-29.
- 2026-07-28 `b077d75` — spec 011: `make check-artifacts` byte-compares
  committed artifacts against a fresh publish run.
- 2026-07-28 `0ddd43c` — specs 015-019: app shell, overview, trips,
  seasonality, active stations, e-bike share.
- 2026-07-29 `3edb79a` — spec 026: chart legends carry values without hover.
  Same commit and neighbours carried spec 025, the `#method` section deriving
  its figures from `exclusions.json`.
- 2026-07-29 `71b2d64` — spec 012: GBFS station geography, and the Montreal
  station bridge that reconciled three era key spaces into one identity.
- 2026-07-29 `c6dd7db`, `cf7ec27`, `74371ec`, `13993fb` — the independent Fable
  review and its fixes: 320,229 Toronto trips in a nested zip, 217,569 in an
  unread worksheet, 31,315 lost to encoding, 8.9M Montreal rows on the wrong
  local day, and four false claims on the site.
- 2026-07-29 `fc4a07b` — van-mobi 2022-10 recovered (110,198 trips) from the
  sister archive after Drive began returning 500s.

- 2026-07-29 `8b84d6e` — spec 021: station maps. MapLibre maps per system,
  lazily loaded; `stations.json` + `stations_meta.json`. Review (Opus, not
  Fable — Fable unavailable) found the maps rendered **zero dots** from two
  independent causes: MapLibre cannot parse `hsl(var(...))` and silently
  rejected the layer, and its tile-parsing worker was never emitted by the
  build, so the SPA fallback served it `index.html` and it died parsing HTML.
  Also fixed: per-map dot scales replaced by one shared ceiling, "retired"
  relabelled "dormant" (28 hollow dots are in the live GBFS feed), station
  labels now taken from whatever supplied the coordinate, Tukey-fence framing
  so Sherbrooke stops stretching Montreal 161 km wide. Verified in a headed
  browser: 260 / 1,102 / 972 dots. 56 vitest.
  `docs/features/021-station-maps.md`
- 2026-07-29 `3deb81e` — spec 009b: the enforcement 009 was missing.
  `make check-metrics` printed "stub" and exited 0 while
  `metric_support.json` claimed it was checked. Now fails on an artifact
  publishing an unsupported system **or on one never declared at all** — the
  case 021 needed. 12 tests, each planting a violation. 38 pytest. Same merge
  gave every spec number 001-027 a file and an index, for a repository about
  to be public. `docs/features/009b-metric-gate.md`
- 2026-07-29 `66da202` — spec 022: station flows. Its review exposed that
  `fact_trips` and `dim_station` resolved station ids differently since spec
  012, inflating Vancouver's distinct-pair count 44% — fixed by materialising
  `station_identity` and joining every consumer to it.
  `docs/features/022-station-flows.md`
- 2026-07-29 `a83eb87` — spec 013: ECCC daily weather, one airport station per
  city, pinned per year. Review found the licence had been named from memory
  and wrong (`d0a330c`); the owner decision to publish under the actual ECCC
  terms is `51fcb40`. `docs/features/013-weather.md`
- 2026-07-30 `fb91a78` — spec 020 + the adversarial audit: membership mix,
  with Toronto's file-scoped label corruption withheld (2021-10..2023-12,
  11,089,535 trips). The audit also found Toronto's 2016.xlsx Q4 day/month
  transposition and added the containment and coercion-signature gates.
  `docs/features/020-membership-mix.md`
- 2026-07-30 `3c7be44` — spec 023: forecast. One weather-and-calendar model per
  system, published as coefficients with an in-browser prediction and an
  out-of-envelope refusal; the additive model was replaced after validation
  against actual days (43% overstatement). Out-of-sample fit added in
  `ce93a23`. `docs/features/023-forecast.md`
- 2026-07-30 `69d230e` — spec 024: operational signals, Montreal in the
  comparable core. Registry key split into `rebalancing_pressure` and
  `bike_dwell`; found Mobi publishes hour-only timestamps and that archive-edge
  days diluted per-day denominators. `docs/features/024-operational-signals.md`
- 2026-07-30 `7d7607a` — spec 027: deployed to Cloudflare Pages at
  bikeshare.adnanreza.com; artifacts unchanged, verified byte-identical
  local-to-served and headed in production. `docs/features/027-deploy.md`
- 2026-07-31 `bbf65e3` — spec 028: the trust release. Quality report's false
  0.0% Montreal figure corrected to a derived 88.9%; funnel made independent
  with a refusal; report under make check; five null-station rows
  re-accounted; fit_basis truthful; LICENSE pure MIT with DATA-LICENSES.md
  carrying every obligation; Mobi's stated hour-rounding recorded.
  `docs/features/028-trust-release.md`
- 2026-07-31 `a2ffdd1` — spec 029: the reproducibility release. Hash-pinned
  lock, transactional extract, sha-keyed caches, standing reconciliation
  gate, synthetic offline fixture pipeline (~2s from nothing), CI green on
  GitHub runners; the 2025-05 "ambiguity" and the fresh-warehouse build bug
  both never-existed/always-existed and are corrected.
  `docs/features/029-reproducibility-release.md`
- 2026-07-31 `21c007a` — spec 030: analytical integrity. Weather scenario
  rename (anchor and keys kept); one completeness declaration, zero months
  moved (verified twice); 15 JSON Schema contracts validated at publish and
  in vitest; artifacts byte-identical.
  `docs/features/030-analytical-integrity.md`
