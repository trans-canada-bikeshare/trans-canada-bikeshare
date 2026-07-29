# Runbook

How to rebuild the archive, regenerate artifacts, and deploy. **Nothing here
has been deployed** — spec 027 is written, not executed.

## Rebuild from nothing

```bash
python3 -m venv .venv
.venv/bin/pip install -r pipeline/requirements.txt
npm install

.venv/bin/python pipeline/discover.py          # refresh manifests from source
.venv/bin/python pipeline/download.py          # ~20 GB, resumable, checksummed
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
make check-metrics     # stub — spec 009 enforcement lives in publish.py today
make check             # all three
npm test && npm run typecheck && npm run build
.venv/bin/python -m pytest pipeline/tests
```

`check-artifacts` is the one that matters before any release: the site serves
`src/data/generated/`, not the warehouse, so a SQL change nobody regenerated
would ship silently.

## Monthly refresh

When a system publishes a new period:

1. `discover.py` — new periods are added automatically. **A changed URL for an
   existing period is reported and not applied**; look at it before passing
   `--accept-changes`, because a source that repoints under you makes the
   archive unreproducible.
2. `download.py` — idempotent; only the new files are fetched.
3. `census.py` — **run this before ETL.** If it shows a header layout the era
   map does not cover, extraction will abort. That abort is the feature.
4. `etl.py --stage all`, then `publish.py`, then `quality_report.py`.
5. `make check` and the JS suite.
6. Commit the regenerated artifacts, the manifests, and the quality report
   together.

## Deploy — NOT YET RUN

The site is a static Vite build. `npm run build` emits `dist/`.

Cloudflare Pages, matching the sister project:

```bash
npx wrangler pages project create trans-canada-bikeshare   # once
npm run build
npx wrangler pages deploy dist --project-name trans-canada-bikeshare
```

Before the first deploy:

- **Resolve the BIXI licence question.** The source page states no terms. The
  site currently says so plainly, which is honest, but shipping Montreal data
  publicly is a decision to make deliberately. See `docs/decisions.md`.
- **Consider a trademark search** on the logo and favicon. The reasoning in
  `docs/features/002b-brand-identity.md` is not legal advice.
- Decide on a custom domain and set `og:url` and a canonical link, which are
  currently absent because no URL is committed to.

## Known gaps

- `van-mobi` 2022-10 fails to download: Google Drive returns a persistent 500.
  One period of 103. Retry with
  `python pipeline/download.py --system van-mobi --period 2022-10`.
- One row carries `implausible_date` after all parsing fixes. It is flagged,
  excluded from published series, and counted in the quality report.
- Montreal and Toronto retain a measured ~0.02–0.03% exact-duplicate residual.
  Vancouver is deduplicated exactly. Rationale in `pipeline/sql/20_clean.sql`.
- `van-mobi` `2025-05.csv` has no date-order evidence either way and is parsed
  month-first. Reported on every clean run.
