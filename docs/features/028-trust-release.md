# Spec 028 — Trust release: the record tells the truth

## Status

Ready. Written 2026-07-31 from findings verified against the warehouse and
the live source pages the same day (external review, claim-by-claim
verification recorded in the decisions log when this spec completes).

## Context

An external review found, and author verification confirmed, that the
project's own trust instruments contain false statements — the exact
"stated and wrong" class the decisions log warns about, now in a public
repository:

- `docs/data-quality-report.md` publishes **0.0%** for Montreal
  canonical-station resolution. The warehouse answers **88.9%**
  (78,431,689 of 88,197,834 trips). `pipeline/quality_report.py:146` joins
  the fact's already-canonical id against the bridge's era-local id.
- The report's "~31,000 rows discarded on invalid encoding, open gap"
  paragraph is hardcoded prose (`quality_report.py:58-61`); `etl.py:170-228`
  has repaired those lines since the overnight review fixes.
- The funnel's duplicate count is landed-minus-everything-else, so the
  zero residual is true by construction, not a check.
- Five 2016 Toronto rows carry a null departure station id (violating the
  no-departure-station drop rule) and 783,014 Toronto rows carry the
  literal string 'NULL' as a raw label over real ids.
- The report's per-system table prints Toronto's first trip as 2000-01-01 —
  the known `implausible_date` row leaking into `min()`.
- The report sits outside every gate: `check_freshness.py` never touches it.
- `pipeline/forecast.py:611` publishes `fit_basis: "no holdout"` while the
  same artifact carries the 5-fold day-holdout figures the site quotes.
- README lines 43-45 claim "Every metric on the site works for all three" —
  false by the project's own decisions (e-bike share and membership are
  two-city; dwell is not comparable).
- Mobi's system-data page now states (fetched 2026-07-31): timestamps are
  "rounded to the nearest hour to maintain the privacy of our users" and
  "Trips made by our Operations team for purposes of rebalancing and
  maintenance have been removed." This corrects the 2026-07-30 decisions
  entry ("floors or rounds… cannot be recovered") and qualifies Vancouver's
  rebalancing signal.
- GitHub classifies the repository licence as NOASSERTION because LICENSE
  mixes data terms into the MIT text.
- Stale docs: `pipeline/README.md` and the runbook's `check-metrics # stub`
  comment describe the pre-009b world.

## Depends On

None. This is the first hardening release and blocks 029-032.

## Scope

- **Sources touched:** none (no new downloads; the Mobi statement is a
  source-page fact recorded in docs).
- **Cities touched:** all three; Montreal's report figures and Toronto's
  row accounting change.
- **Tier:** neither — no new metrics.
- **Published artifacts change: YES** — `forecast.json` (`fit_basis`
  corrected) and `rebalancing.json` (caveat gains the Mobi ops-trips-removed
  qualification via the registry field). The quality report regenerates.
  All other artifacts must be byte-identical.

## Changes

1. **Fix the Montreal canonical share.** Replace the era-id join with a
   query that counts trips whose station id is canonical. The published
   sentence derives from the query.
2. **Replace the encoding-loss prose with recorded fact.** Extraction
   records per-file repaired-line counts into the warehouse
   (`raw_file_audit` or equivalent); the report derives its encoding
   paragraph from that record. No hardcoded counts.
3. **Independent drop accounting.** Count duplicates directly at the clean
   stage and persist the count; the funnel residual becomes a real
   assertion (landed − kept − independently-counted drops = 0) that fails
   the report run when nonzero.
4. **The five null-station rows** are dropped by the stated rule (or
   flagged with a named reason if dropping is wrong), and the accounting
   closes. The 783,014 literal-'NULL' raw labels are investigated and the
   report states what they are; labels used anywhere for display must not
   read 'NULL'.
5. **Per-system first/last dates** exclude `implausible_date`-flagged rows
   or footnote them; no fabricated 2000 first-trip.
6. **The report goes under a gate.** `make check` regenerates the quality
   report and fails on any diff (timestamp line excluded). Pytest gains
   planted-violation tests for the generator: a wrong canonical join, a
   nonzero residual, and a hardcoded-number regression each fail the suite.
7. **`fit_basis` tells the truth**: in-sample statistics plus the 5-fold
   day-within-month holdout, described as within-month scenario validation.
   (Renaming/rescoping the Forecast section itself is spec 030's owner
   decision — this change only makes the artifact's self-description match
   what was computed.)
8. **README correction**: the "Every metric works for all three" sentence
   is replaced with the accurate statement and a pointer to the per-metric
   support table/registry.
9. **Mobi source facts recorded**: decisions.md correction entry (rounding
   is stated by the source, with the fetch date; ops trips removed);
   `docs/source-audit.md` annotated; the `rebalancing_pressure` registry
   caveat states that Vancouver's source removes operations trips, and the
   artifact/page render it.
10. **Licence separation**: `LICENSE` becomes pure MIT; all data terms move
    to `DATA-LICENSES.md` (linked from README, site methodology, and
    manifests); the footer's independent-project disclaimer names the
    operators, not only the Government of Canada.
11. **Stale docs corrected**: `pipeline/README.md`, the runbook's
    check-metrics comment, and `docs/roadmap.md`'s open-gap entry for
    encoding (now resolved-by-repair, with the source-count reconciliation
    gate deferred to 029 and said so).

## Acceptance Criteria

- [ ] The committed quality report states the Montreal canonical share
      derived from the corrected query (~88.9% against the current
      warehouse) and contains no hardcoded row counts anywhere — every
      figure traces to a query or a warehouse-recorded extraction metric.
- [ ] The funnel's duplicate count is computed independently; a planted
      double-counted reason makes the residual nonzero and fails both the
      report generation and a test.
- [ ] Zero kept rows have a null departure station id; the five 2016 rows
      are accounted for under a named reason; the report explains the
      literal-'NULL' raw labels and no rendered surface displays 'NULL' as
      a station name.
- [ ] The per-system table shows no first/last date sourced from an
      `implausible_date` row.
- [ ] `make check` fails when the committed quality report differs from a
      fresh generation (timestamp excluded); this is demonstrated by a
      planted stale report in a test.
- [ ] `forecast.json`'s `fit_basis` describes both the in-sample statistics
      and the day-holdout validation accurately; the site's forecast section
      renders consistently with it.
- [ ] `rebalancing.json`'s caveat (registry-sourced) states Vancouver's
      source removes operations trips; the operations page renders it.
- [ ] README no longer claims every metric works for all three systems.
- [ ] decisions.md carries the Mobi rounding/ops-removal correction with
      the fetch date; source-audit.md is annotated to match.
- [ ] `LICENSE` is pure MIT and GitHub's API reports the licence as MIT;
      `DATA-LICENSES.md` carries every data term verbatim (BIXI unknown,
      Toronto OGL string, ECCC restrictions, Mobi agreement pointer);
      README, manifests, and the site methodology link to it; the footer
      disclaimer names Mobi by Rogers, BIXI Montréal, and Bike Share
      Toronto as unaffiliated operators.
- [ ] `pipeline/README.md` and the runbook describe the metric gate as it
      exists; roadmap's encoding-gap entry reflects the repair.
- [ ] All artifacts byte-match the previous publish except: `forecast.json`
      (fit_basis only), any artifact carrying the `rebalancing_pressure`
      caveat or the van-mobi hour-rounding note (those fields only — the
      note now cites the source's stated rounding instead of calling the
      phase unknown), and any artifact whose Toronto 2016 figures move by
      exactly the five re-accounted rows — each diff enumerated at review
      with before/after values.

## Data Integrity Checklist

- ~~Manifest entry for every new source file~~ — no new sources.
- [ ] Schema drift mapped explicitly — unchanged; no mapping changes.
- [ ] Row accounting closes — strengthened: components now independent.
- [ ] Metrics defined identically or labelled — caveat text changes only.
- [ ] Committed artifacts reproduce byte-for-byte from a fresh run.
- [ ] Site copy derives from the data window.
- ~~New encodings explained~~ — no new visual encodings.
- [ ] Source licence attribution present — restructured into
      DATA-LICENSES.md without losing any obligation text.
- [ ] No raw trip data committed.

## Testing

Pytest: planted-violation tests for the report generator (wrong join,
nonzero residual, hardcoded number, stale committed report), null-station
invariant, first/last-date exclusion. Existing suites stay green. Vitest
for the caveat and footer rendering. `make check` exercises the new report
gate. The corrected Montreal figure is re-derived from the warehouse in the
spec record at completion, not recalled.

## Out of Scope

- Source-count reconciliation gate (rows_landed vs source records per
  file) — 029, where checksum-keyed caching lands.
- Forecast section renaming or temporal validation — 030, owner decision.
- CI — 029/031. Licence outreach emails — owner, parallel.

## Rollback

Artifacts: previous `forecast.json`/`rebalancing.json` are in git history;
revert the merge and republish. The licence restructure is a file move —
revert restores the previous LICENSE. No schema changes to the warehouse
beyond additive extraction metrics.
