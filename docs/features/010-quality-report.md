# Spec 010 — Quality report

## Status

Complete. Shipped 2026-07-28.

> **Written retrospectively on 2026-07-29**, from `cb10b98`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## Context

The project's second principle is that every row dropped or flagged is
accounted for. That is only true if the accounting is generated, committed, and
regenerated — a number in a README rots the first time the pipeline runs.

## What shipped

`pipeline/quality_report.py`, writing `docs/data-quality-report.md`: the stage
funnel per system, drop reasons with counts, quality-flag counts, membership
mapping coverage, and trips per month per source file.

The report is generated, never hand-edited. Its header says so, because a
generated file that someone has edited by hand is worse than no file.

## Known weakness

Row ordering at an exact tie is not deterministic — `ORDER BY 1, 4 DESC` with
no tiebreaker lets two equal rows swap places between runs. It moves no figure,
but it means the file does not byte-reproduce, and `make check-artifacts` does
not cover `docs/` so nothing catches it. Found in spec 021's review.

## Where the record is

- `pipeline/quality_report.py`, `docs/data-quality-report.md`
