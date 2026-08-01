# Runbook

How to rebuild the archive, regenerate artifacts, and deploy. First deployed
2026-07-30 (spec 027) to https://bikeshare.adnanreza.com.

## Rebuild from nothing

```bash
python3.11 -m venv .venv
.venv/bin/pip install --require-hashes -r pipeline/requirements.lock
npm ci

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
make check-dictionary  # docs/data-dictionary.md matches the schemas and the
                       #   completeness declaration it is generated from
make check             # all six
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

## What publish.py refuses

Two checks run inside `publish.py` on every run, before anything is written.
Neither has a `make` target because neither is a separate pass: they are the
conditions the publisher will not write without.

### The completeness declaration — `pipeline/completeness.py`

One file declaring, for each of the fifteen artifacts, **which rule governs
what reaches it and why**, plus every numeric threshold the publisher admits
or excludes rows by. Nothing else in `publish.py` or `forecast.py` states a
threshold; they read this.

The month rule is one text, `incomplete_month_having()`: a system-month
observed on **three days or fewer**, or a trailing month the source has not
finished publishing, is excluded and listed in `incomplete_months.json`. Both
consumers call it. Before spec 030 it was written five times — the
incomplete-months query, the Python filter, the SQL predicate, the seasonality
CTE with a different boundary, and a fourth copy in `forecast.daily_rows` — and
three artifacts applied no rule at all with nothing recording that.

Each policy is one of two answers, and **`whole_archive` is an answer**:

| Answer | Artifacts | What it means |
| --- | --- | --- |
| `exclude_incomplete_months` | `incomplete_months`, `trips_monthly`, `seasonality`, `stations_yearly`, `ebike_share`, `membership`, `forecast`, `rebalancing`, `dwell` | The artifact has a per-month point or a per-month denominator, so a fraction of a month could be read as a low one. |
| `whole_archive` | `meta`, `duration`, `stations`, `stations_meta`, `flows`, `exclusions` | Nothing in the output is per month. Applying the rule would drop real trips from totals that are meant to be totals, or split a numerator from its denominator. |

Every `whole_archive` entry was **measured** before it was written, and the
measurement is in the file: what applying the rule would have moved. Read the
reasons there, not here — that is the point of putting them there.

Three further rules with no numeric threshold are declared alongside:
`operating_days_only` (a per-day denominator counts days the system ran,
evidenced by a departure), `whole_calendar_years_only`, and
`withhold_unreliable_label_eras` (Toronto's file-scoped member-label
corruption, `2021-10..2023-12`).

`publish.build()` calls `completeness.validate()` with the artifacts it built,
so **a new artifact with no declared policy stops the run**. A test scans the
publisher's own source and fails on any number in a `HAVING`, a `WHERE`, a
`BETWEEN`, a modulus, a named constant or a Python comparison that did not come
from the declaration — planted violations included, in the style of
`test_check_metrics.py`.

### The artifact schemas — `pipeline/schemas/*.schema.json`

One JSON Schema (draft 2020-12) per artifact, enforced from both ends:

- `publish.write()` validates every artifact against its schema **before
  writing any of them**, so a shape drift is a refusal on the machine that
  produced it rather than a half-updated directory. Needs `jsonschema`, which
  is in the lock.
- `src/schemas.test.ts` validates the **committed** files with ajv, so the same
  contract is checked on a runner with no warehouse — which is where a drift
  between what `publish.py` writes and what `src/lib/data.ts` imports would
  otherwise reach production.

The schemas are strict on purpose: `additionalProperties: false` everywhere and
every key required unless the publisher genuinely omits it. Both ends also
check the **set**: an artifact with no schema fails, and so does a schema whose
artifact no longer ships.

To change an artifact's shape, change the schema in the same commit. That is
the whole ceremony, and it is deliberate — the schema is the place the site's
expectations and the publisher's output are written down together.

## The fixture pipeline

```bash
make check-fixture      # ~2.5s, no network, no archive
```

Every gate above needs the ~20 GB archive, so until spec 029 nothing in this
repository could be verified by anyone who had not downloaded it — including a
GitHub runner. `make check-fixture` closes that: it runs the **whole** pipeline
end to end over a small synthetic archive and then runs the real gates against
the result.

- **The fixtures live in `pipeline/tests/fixtures/`** — `archive/` (the source
  files) and `manifests/` (their checksums), with a README stating what they
  cover and what they deliberately do not. Every value in them is invented;
  every station is named `FIXTURE …`, every manifest URL is `synthetic://`,
  and no source licence reaches them. `pipeline/tests/fixtures/generate_fixtures.py`
  is how the bytes were made and rewrites both directories together.
- **The run tree is `.fixture-run/`**, gitignored, removed on success and kept
  by `--keep`. `BIKESHARE_DATA_ROOT` points at it, so the archive, the
  warehouse and the manifests move together; `BIKESHARE_GENERATED_DIR` points
  at `.fixture-run/generated`. `pipeline/fixture_run.py` records the
  modification times of `src/data/generated/`, `docs/data-quality-report.md`,
  `data-raw/` and `data-warehouse/` before the run and compares them after, so
  "it cannot touch the real project" is checked rather than asserted.
- **It is offline.** `BIKESHARE_ALLOW_EXTENSION_INSTALL=0` and an empty
  extension directory inside the run tree. The fixtures are CSV-only precisely
  so DuckDB's `excel` extension — the one thing here that is fetched from the
  network — is never needed; `icu` ships inside the wheel.
- **It runs on 1 GB and two threads**, which is what makes the configurable
  limits a tested property rather than a documented intention.

It runs `check-manifest`, `check-metrics`, `check-artifacts` and `check-report`
against the fixture tree. The last two are the interesting ones: there are no
committed fixture artifacts to compare against, so the run publishes and then
re-publishes and byte-compares, and generates the quality report and then
regenerates and diffs it. That is the same question `make check-artifacts` asks
of the real archive — and it is what would have caught spec 029's
`stations.json` defect, where a sort that was not a total order returned tied
rows in whatever order the scan produced.

What it does **not** cover is in the fixtures' README: no XLSX, no zips, no
encoding repair, and nothing about whether any published number is right. Those
stay with the full archive, and the full archive stays local.

## CI

`.github/workflows/ci.yml`, on every push to `main` and every pull request. Two
jobs, both on a clean GitHub-hosted runner:

| Job | Runs |
| --- | --- |
| **Pipeline (Python 3.11)** | `pip install --require-hashes -r pipeline/requirements.lock`, `pytest pipeline/tests`, `make check-fixture` |
| **Site (Node)** | `npm ci`, `npm test`, `npm run typecheck`, `npm run build` |

pip and npm caches are keyed on the lock files. No `continue-on-error` and no
`|| true` anywhere: a gate that cannot fail is worse than an absent one.

**Hardening (spec 031).** Every action is pinned to a full commit SHA with its
version in a comment beside it, both checkouts set `persist-credentials: false`,
and both jobs carry `timeout-minutes: 15`. `pipeline/tests/test_workflows.py`
asserts all three over every workflow in `.github/`, plus the permissions
blocks — so an action re-pinned to a tag, or a checkout that leaves the job's
token in `.git/config`, fails the suite rather than being noticed in review.

To move an action to a new version: resolve the tag to its commit, put the SHA
in the `uses:` and the version in the comment, and check the two agree.

```bash
gh api repos/actions/checkout/git/ref/tags/v4 --jq '.object.sha'
gh api repos/actions/checkout/git/matching-refs/tags/v --paginate \
  --jq '.[] | select(.object.sha=="<sha>") | .ref'    # which versions that is
```

**Dependabot** (`.github/dependabot.yml`) proposes those updates monthly,
grouped into one PR per ecosystem (npm, pip, github-actions). Note the pip one:
Dependabot edits `pipeline/requirements.txt`, the lower bounds. The hash-pinned
`pipeline/requirements.lock` is regenerated by hand for all three platforms per
the instructions in its own header — a lock edited any other way fails
`pip install --require-hashes` on the next clean install.

### The monthly refresh reminder

`.github/workflows/monthly-refresh-reminder.yml` runs on
**`cron: '0 14 1 * *'`** — 14:00 UTC on the first of each month — and can be
triggered by hand with `workflow_dispatch`. It opens one issue titled
`Monthly data refresh — <Month Year>`, whose body is the template at
**`.github/refresh-reminder.md`**: the steps below, in order, linked back to
this section. Editing the reminder means editing that file, not the workflow.

It has `issues: write` and `contents: read` and nothing else, uses `gh` with
`GITHUB_TOKEN` rather than a third-party action, and skips silently when an
open issue with that month's title already exists. It touches no data and runs
no gate — the refresh itself needs the archive and stays on this machine.

### The data dictionary gate

`make check-dictionary` regenerates `docs/data-dictionary.md` from the fifteen
schemas and `pipeline/completeness.py` and fails on any difference. The
document carries **no timestamp**, so unlike the quality report the diff is
total. Regenerate with:

```bash
.venv/bin/python pipeline/generate_data_dictionary.py
```

### The release provenance block

`pipeline/release_provenance.py` prints what a tagged release carries: the
commit, the sha256 and byte size of every file in `src/data/generated/`, the
Python and DuckDB versions read from the lock, the Node version read from the
CI workflow, and each system's window read from `meta.json`. Nothing in it is
typed by hand.

```bash
.venv/bin/python pipeline/release_provenance.py --check          # it renders
.venv/bin/python pipeline/release_provenance.py v1.1.0 $(git rev-parse HEAD)
```

**What stays local, and why.** `make check` — manifest, metrics, artifacts,
report, reconciliation, dictionary — needs the ~20 GB archive for all but the
last, and it is neither committed nor downloadable inside a job (a full
acquisition is ~25 minutes and one period currently 500s at origin). So the
full-data gates run on the machine that holds the archive, before the artifacts
are committed, and CI proves the two things a clean clone can prove: that the
pinned toolchain installs and that the pipeline runs end to end. In a clean
clone with no `data-raw/` and no `data-warehouse/`, the warehouse-backed tests
**skip** — 239 pass, 31 skip, measured in a fresh clone on 2026-07-31 — and
`make check-fixture` passes on its own tree. (This line read "149 pass" until
spec 031 ran the count instead of carrying it forward.)

**Deployment is not in CI.** No Cloudflare credential exists in this
repository's secrets, and the deploy is the two commands under "Deploy" below,
run by hand.

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
   silently. Two more aborts belong to publish and are also features: an
   artifact with no completeness policy, and an artifact that no longer
   matches its schema. Both are described under "What publish.py refuses" —
   a new artifact needs an entry in `pipeline/completeness.py` and a schema in
   `pipeline/schemas/` before it can ship.
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

### Response headers

They live in **`public/_headers`**, which Vite copies verbatim to
`dist/_headers` for Pages to parse. The file explains itself; three things to
know before touching it:

- **`vite preview` does not read it.** These headers can only be observed on a
  deployment, so a change to them is verified with `curl -sI` against a Pages
  **preview** URL before production, never from local serving.
- **Pages merges every matching rule** and comma-joins repeated header names —
  there is no last-match-wins. That is why the two un-hashed MapLibre worker
  files detach `Cache-Control` with `! Cache-Control` before setting their own;
  without it they would inherit the immutable year meant for hashed assets, and
  a stale worker means blank maps.
- **The CSP names the tile provider explicitly.** `img-src` and `connect-src`
  both carry `https://tiles.openfreemap.org`, taken from `STYLE` in
  `src/components/StationMap.tsx` and confirmed against both style JSONs
  (tiles, sprites and glyphs are all on that one origin). **Change the basemap
  provider and the CSP has to move with it**, or the maps go blank with only a
  console violation to say why. `script-src` pins `index.html`'s inline theme
  script by sha256; `src/headers.test.ts` fails if that script is edited and
  the hash is not recomputed (the command is in the file's own comments).

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
