# Runbook

How to rebuild the archive, regenerate artifacts, and deploy. First deployed
2026-07-30 (spec 027) to https://bikeshare.adnanreza.com.

## Rebuild from nothing

```bash
python3.11 -m venv .venv
.venv/bin/pip install --require-hashes -r pipeline/requirements.lock
npm install

.venv/bin/python pipeline/discover.py          # refresh manifests from source
.venv/bin/python pipeline/weather.py           # derive ECCC weather years from the trip window
.venv/bin/python pipeline/download.py          # ~20 GB, resumable, checksummed
#   ^ van-mobi 2022-10 will FAIL here while Google Drive 500s — see Known
#     gaps below for the archived-copy recovery. etl.py refuses to run with
#     a pinned file absent, deliberately.
.venv/bin/python pipeline/inventory.py         # verify the archive
.venv/bin/python pipeline/census.py            # header layouts, to maintain era maps
.venv/bin/python pipeline/etl.py --stage all   # extract -> clean -> conform -> model
.venv/bin/python pipeline/publish.py           # artifacts to src/data/generated/
.venv/bin/python pipeline/quality_report.py    # docs/data-quality-report.md
```

Timings on a 16 GB machine: download ~25 min on a fast link, extract ~11 min,
clean ~4 min, model ~4 min. Peak disk about 45 GB including the warehouse and
unpacked archives. (Clean was recorded as ~2 min before spec 029 measured it
again at 4:04 over 135.9M rows; the stage did not get slower, the figure was
stale.)

**Install from the lock, not from `requirements.txt`.** `pipeline/requirements.txt`
carries lower bounds and is what a dependency refresh resolves *from*;
`pipeline/requirements.lock` carries exact versions and sha256 hashes for every
package, direct and transitive, and is what a rebuild installs. A hash mismatch
aborts the install rather than producing a subtly different environment.

**Python 3.11, exactly.** The lock holds CPython 3.11 (`cp311`) wheel hashes and
nothing else, so another minor version has nothing to install; and every
pipeline module asserts the version at import (`common.PYTHON_REQUIRES`), so a
pre-existing environment on 3.12 fails at startup instead of at the first
behavioural difference. Regenerating the lock for another Python or another
platform is documented in the lock's own header.

**One network call that is not a download.** DuckDB's `icu` extension ships
inside the Python wheel and loads offline. `excel` does not, and `read_xlsx`
reads Toronto's 2016 workbook and Mobi's eight XLSX months, so a first run
fetches it from DuckDB's extension repository. Extensions are not vendored into
git — they are per-platform, per-version binaries under a licence this project
does not control. To run with no network at all, point
`BIKESHARE_DUCKDB_EXTENSION_DIR` at a directory that already has it and set
`BIKESHARE_ALLOW_EXTENSION_INSTALL=0`, which turns a missing extension into a
named refusal instead of a silent fetch.

## Configuration

Every data path and every resource limit is overridable, with the values above
as defaults. This exists so a fixture or CI run can point the **whole** pipeline
— `etl.py`, `publish.py`, `quality_report.py`, `check_report.py`,
`check_freshness.py`, `check_reconciliation.py`, `inventory.py` — at a different
tree in one move.

| Variable | Default | What it moves |
| --- | --- | --- |
| `BIKESHARE_DATA_ROOT` | repo root | `data-raw/`, `data-warehouse/` **and** `manifests/`, together |
| `BIKESHARE_DATA_RAW` | `<root>/data-raw` | the acquired archive |
| `BIKESHARE_DATA_WAREHOUSE` | `<root>/data-warehouse` | the DuckDB file and its spill directory |
| `BIKESHARE_MANIFEST_DIR` | `pipeline/manifests` | the checksum manifests |
| `BIKESHARE_GENERATED_DIR` | `src/data/generated` | the artifacts the site serves |
| `BIKESHARE_DUCKDB_MEMORY_LIMIT` | `10GB` | DuckDB memory limit (also `etl.py --memory-limit`) |
| `BIKESHARE_DUCKDB_THREADS` | `8` | DuckDB thread count (also `etl.py --threads`) |
| `BIKESHARE_DUCKDB_EXTENSION_DIR` | DuckDB's own (`~/.duckdb`) | where extension binaries are cached |
| `BIKESHARE_ALLOW_EXTENSION_INSTALL` | on; `0` forbids | whether a missing extension may be fetched |

`BIKESHARE_DATA_ROOT` moves the archive, the warehouse and the manifests
**together**, and that grouping is the point: a manifest pins the bytes in the
archive and the warehouse records which pinned bytes it was built from. Point
two of them at a fixture tree and the third at the real one and every checksum
comparison in the project becomes meaningless while continuing to pass. The
layout it expects is `<root>/data-raw`, `<root>/data-warehouse`,
`<root>/manifests`. The individual variables exist for the cases where the three
genuinely must not move together.

**`pipeline/mappings/` has no override, deliberately.** The era maps, the
membership groups, the metric registry and the date-order exceptions are code:
they encode decisions about what the published bytes *mean*, they are reviewed
as code, and they are what the gates check against. A run that could substitute
them could make any archive parse "correctly" — a fixture run proves the
mappings work, it does not get its own.

## Gates

```bash
make check-manifest    # archive matches the manifests; pending vs corrupt
make check-artifacts   # committed artifacts match a fresh publish run
make check-metrics     # no cross-city series for a metric the registry does not
                       #   support, and no system-keyed artifact left undeclared
make check-report      # committed quality report matches a fresh generation
                       #   from the warehouse (timestamp excluded)
make check-reconciliation
                       # the per-file audit is still true of the archive the
                       #   manifests pin now — see below
make check             # all five
npm test && npm run typecheck && npm run build
.venv/bin/python -m pytest pipeline/tests
```

`check-artifacts` is the one that matters before any release: the site serves
`src/data/generated/`, not the warehouse, so a SQL change nobody regenerated
would ship silently.

`check-reconciliation` is the one that matters after a **re-pin**. Extraction
counts the records in every source file and refuses to continue if that differs
from what landed — but that fires once, against the bytes on disk that morning.
`download.py --accept-changes` can then re-pin a republished source, and every
other gate stays green: `check-manifest` passes because the archive matches the
manifest, `check-artifacts` passes because the artifacts match a publish run
over the unchanged warehouse. So the audit records the checksum each count was
taken from, and this compares it. It reads no files unless a pin has moved,
which is why it can live in `make check`; where one has moved it re-counts that
period and says by how much.

A warehouse extracted before spec 029 has no checksums recorded and the gate
says so rather than assuming. Run it **once**:

```bash
.venv/bin/python pipeline/check_reconciliation.py --recount
```

It re-reads the archive, confirms every count against what landed, and stamps
the checksum — 241 files in about 16 seconds. Where a count no longer matches it
refuses to stamp and tells you to re-extract, because overwriting the recorded
count with a fresh one would erase the only evidence that the warehouse is
stale.

## Monthly refresh

When a system publishes a new period:

1. `discover.py` — new periods are added automatically. Then `weather.py`,
   which derives the ECCC year range from the manifest's own trip periods —
   a new trip year pulls its weather without anyone editing a list. The
   current calendar year's weather file is marked `volatile` and repins
   without complaint; every closed year refuses drift. **A changed URL for an
   existing period is reported and not applied**; look at it before passing
   `--accept-changes`, because a source that repoints under you makes the
   archive unreproducible.
2. `download.py` — idempotent; only the new files are fetched.
3. `census.py` — **run this before ETL.** If it shows a header layout the era
   map does not cover, extraction will abort. That abort is the feature.
4. `etl.py --stage all`, then `publish.py`, then `quality_report.py`.
5. `make check` and both test suites. Two aborts are FEATURES, not failures:
   an unmapped column header stops extraction, and an unmapped membership
   label stops publish — map the new value explicitly in
   `pipeline/mappings/` and rerun. A new Vancouver pass name will also trip
   the pinned label-count test, which exists so the mapping cannot grow
   silently.
6. Commit the regenerated artifacts, the manifests, and the quality report
   together. **The site updates by exactly this** — every count, window, gap
   sentence and chart derives from the committed artifacts, so a republish is
   the whole update; there is no other copy to edit.

Three aborts are also FEATURES and all three arrive during ETL:

- **A manifest entry with no checksum** stops extraction
  (`etl.UnpinnedSource`). It used to be skipped, silently, which turned a
  period nobody had downloaded into a quietly smaller warehouse. Download it
  or remove the entry.
- **A file whose date order its own values cannot prove** stops the clean
  stage (`etl.AmbiguousDateOrder`). Declare it in
  `pipeline/mappings/date_order.json` with the evidence.
- **A file that lands a different number of records than it contains** stops
  extraction (`etl.ReconciliationFailed`), and the audit that proves it is
  re-checked afterwards by `make check-reconciliation`.

And extraction is now **transactional per system**: if any of those aborts
fires part-way through, the system being loaded keeps its previous rows rather
than being left half-deleted. Each system is either entirely its old contents
or entirely its new ones. Re-run the same command once the cause is fixed.

## Deploy — first run 2026-07-30

The site is a static Vite build. `npm run build` emits `dist/`.

Cloudflare Pages, matching the sister project. The commands actually run:

```bash
npx wrangler pages project create trans-canada-bikeshare --production-branch main   # once, done
npm run build
npx wrangler pages deploy dist --project-name trans-canada-bikeshare --branch main
```

The custom domain `bikeshare.adnanreza.com` is attached to the Pages project
(dashboard: Workers & Pages → trans-canada-bikeshare → Custom domains; the
adnanreza.com zone is on the same account, so Cloudflare created the CNAME
and certificate itself — wrangler has no command for this step). `og:url`
and `rel=canonical` in `index.html` carry the same URL.

A redeploy is the last two commands. The site serves static assets only — no
Pages Functions — so traffic consumes nothing from the Workers plan.

The owner decisions that gated the first deploy, all settled 2026-07-30:

- **The BIXI licence question** — proceed, publishing Montreal with its terms
  stated as unknown, per the 2026-07-28 decision. The escape hatch stands:
  if terms arrive that forbid this, one publish run drops Montreal.
- **Trademark search** on the logo and favicon — proceeding without a formal
  search; `docs/features/002b-brand-identity.md` records the reasoning and
  remains not legal advice.
- **The canonical URL** — `bikeshare.adnanreza.com`; the reasoning is in
  `docs/decisions.md` (2026-07-30).

## Known gaps

- `van-mobi` 2022-10 **cannot be downloaded from source**: Google Drive
  returns HTTP 500, confirmed across four endpoint forms on 2026-07-29, while
  the Mobi source page still points at the same drive id — a source-side
  outage, not a stale link. The archive currently holds a copy taken from the
  sister project `mobi-transit-explorer`, which acquired it from the same URL
  on 2026-07-09; its sha256 was recomputed independently here and matches that
  project's pin exactly. The manifest entry carries a `provenance_note` saying
  so. **A clean-room rebuild on another machine will fail on this period until
  Drive serves the file again** — that is the one place the reproducibility
  contract currently depends on a second copy rather than the source. Retry
  with `python pipeline/download.py --system van-mobi --period 2022-10
  --accept-changes` once it is back.
- One row carries `implausible_date` after all parsing fixes. It is flagged,
  excluded from published series, and counted in the quality report.
- Montreal and Toronto retain a measured ~0.02–0.03% exact-duplicate residual.
  Vancouver is deduplicated exactly. Rationale in `pipeline/sql/20_clean.sql`.
- ~~`van-mobi` `2025-05.csv` has no date-order evidence either way and is
  parsed month-first.~~ **Not true, and closed in spec 029.** That file is
  `YYYY/MM/DD HH:MM:SS` — 133,643 slashed rows, one distinct first field
  (`2025`), one distinct second field (`05`), third fields spanning 01..31. It
  is year-first and unambiguous. Both evidence rules in `15_dates.sql` captured
  one or two digits before a slash, so a four-digit year matched neither, both
  counts came out zero, and the file was labelled ambiguous and parsed by the
  month-first fallback — correctly, for the wrong reason, while this page, the
  clean-stage log and the warehouse all reported an ambiguity that does not
  exist. `year_evidence` now recognises it. Nothing about the parsed data
  changed; the claim about it did.
- Date order is no longer defaulted anywhere. A file whose order its own values
  cannot prove must be declared in `pipeline/mappings/date_order.json` with the
  evidence for the choice, or the clean stage aborts
  (`etl.AmbiguousDateOrder`); a declaration for a file that can now prove its
  own order aborts too. **The list is currently empty**, which is the state to
  want: every file in the archive proves itself.
