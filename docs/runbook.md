# Runbook

How to rebuild the archive, regenerate artifacts, and deploy. First deployed
2026-07-30 (spec 027) to https://bikeshare.adnanreza.com.

## Rebuild from nothing

```bash
python3 -m venv .venv
.venv/bin/pip install -r pipeline/requirements.txt
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
clean ~2 min, model ~4 min. Peak disk about 45 GB including the warehouse and
unpacked archives.

## Gates

```bash
make check-manifest    # archive matches the manifests; pending vs corrupt
make check-artifacts   # committed artifacts match a fresh publish run
make check-metrics     # no cross-city series for a metric the registry does not
                       #   support, and no system-keyed artifact left undeclared
make check-report      # committed quality report matches a fresh generation
                       #   from the warehouse (timestamp excluded)
make check             # all four
npm test && npm run typecheck && npm run build
.venv/bin/python -m pytest pipeline/tests
```

`check-artifacts` is the one that matters before any release: the site serves
`src/data/generated/`, not the warehouse, so a SQL change nobody regenerated
would ship silently.

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
- `van-mobi` `2025-05.csv` has no date-order evidence either way and is parsed
  month-first. Reported on every clean run.
