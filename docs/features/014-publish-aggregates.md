# Spec 014 — Publish aggregates

## Status

Complete. Shipped 2026-07-28.

> **Written retrospectively on 2026-07-29**, from `cb10b98`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## Context

No per-trip data ever reaches the browser. The site is static, so everything it
renders must be a small committed aggregate.

## What shipped

`pipeline/publish.py`, writing typed JSON to `src/data/generated/` under an
enforced size budget of 320 KB gzip total. Ten artifacts today, at 19.9% of
budget.

Two rules the code enforces rather than documents:

**`TRUSTED`** — rows flagged `implausible_date` stay in `fact_trips` and in the
quality report, so nothing is hidden, but they never reach a published series.
One stray row would stretch a chart axis back to the year 2000.

**The incomplete-month rule** — a trailing partial month, or a stub of three
days or fewer, is excluded and listed in `incomplete_months.json` rather than
plotted as a collapse. An earlier version of this rule was too broad and
excluded BIXI's real mid-April and mid-November operating months; it was
narrowed to trailing partials and short stubs only.

## Where the record is

- `pipeline/publish.py`, `src/data/generated/`
- `incomplete_months.json` — what is excluded and why, rendered on the site
