# Current Feature: 003 Per-city manifests and downloaders

## Status

In Progress — branch `feature/003-manifests-and-downloaders`

## Lifecycle

<!-- Each action stamps its own line with the date it ran. `/feature complete`
     refuses to proceed while `review` is unstamped. -->

- [x] load — 2026-07-28
- [x] start — 2026-07-28
- [ ] test
- [ ] review

## Goals

- `discover.py` populates all three manifests with every period each system
  publishes, from the live source, with no payload downloads
- A changed URL for an existing period is **reported and not applied** without
  `--accept-changes`
- `download.py` fetches a requested period, stores SHA-256, byte size, and
  magic-byte-detected format into the manifest
- Re-running `download.py` on an already-correct file makes **no network
  request** and leaves the manifest byte-identical
- A pinned file whose content changes causes a **non-zero exit** naming the
  drifted period, and does not overwrite the pin
- Format is determined by magic bytes; a file whose extension disagrees with its
  content is stored by content
- At least one real file per system is downloaded, checksummed, and pinned — and
  the Vancouver pin matches the sister project's manifest for the same period
- GBFS `station_information` is pinned for all three systems
- Every manifest carries a licence block reflecting spec 001's findings,
  including Montreal's absence of stated terms
- `LICENSE` no longer makes the unsupported BIXI claim and carries Toronto's
  required attribution wording
- `make check-manifest` exits 0 on a consistent archive and non-zero on a
  corrupted one, distinguishing *pending* from *failed*
- `pytest` covers the pure logic — period parsing, change detection,
  verification — without touching the network

## Notes

**Depends on:** spec 001 (`5425262`) for the URL inventory and licence findings;
spec 002 (`7093bac`) for `common.py`.

**Sources:** all three trip archives plus their discovery surfaces (Mobi system-
data page, BIXI open-data page, Toronto CKAN `package_show`), and GBFS
`station_information` for each.

**Cities:** Vancouver, Montreal, Toronto. Tier 1.

**Published artifacts change:** No. Manifests are committed;
`src/data/generated/` stays empty until spec 014.

**Licence constraints — this spec discharges two debts:**
- Spec 001 deferred SHA-256 here. Discharged for the files actually downloaded.
- `LICENSE` makes a BIXI claim the source page does not support, and omits
  Toronto's required attribution string. Corrected here.

**Scale.** The full archive is several GB (BIXI 2024 is 476 MB; its 2025 file is
2.8 GB uncompressed). Discovery is cheap and covers everything; downloading is
explicit and scoped. Acceptance is about the downloader behaving correctly on
real files, not about pulling the whole archive.

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
