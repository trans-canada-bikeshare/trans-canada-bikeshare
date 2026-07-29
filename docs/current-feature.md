# Current Feature: 003 Per-city manifests and downloaders

## Status

In Progress — branch `feature/003-manifests-and-downloaders`

## Lifecycle

- [x] load — 2026-07-28
- [x] start — 2026-07-28
- [x] test — 2026-07-28
- [x] review — 2026-07-28

## Goals

See `docs/features/003-manifests-and-downloaders.md`. All twelve acceptance
criteria met except the full-archive pull, which is running and is explicitly
an operator action rather than a test.

## Notes

**Test (2026-07-28).** 26 pytest (19 new), all offline. Live discovery found
13 Montreal periods, 12 Toronto, 103 Vancouver — and reported one unrecognized
Vancouver link (the unlabelled duplicate 2017 export) rather than skipping it,
which is the designed behaviour. `make check-manifest` runs `inventory.py` and
correctly separates *pending* from *failed*. Format detection classified
Toronto's 2014-2015 and 2016 as xlsx and the rest as zip, from magic bytes.

**Resumability fix made during the run:** the manifest saved only at the end of
a system, so a crash on file 80 of a multi-GB pull would have discarded the
first 79 pins. It now saves after every file.

**Review.** Gate items: provenance pinned — **pass**, every downloaded file
carries sha256, byte size and content format, and each manifest now carries a
licence block. Nothing guessed silently — **pass**, unknown link labels and
non-data content types are reported and refused. No raw data in the diff —
**pass**, `data-raw/` is gitignored and holds the archive. Row accounting,
artifacts, metrics, copy, encodings — n/a, no ETL or site surface yet.

**Verdict: ready to complete.**

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
