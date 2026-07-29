# Spec 011 — Freshness gate

## Status

Complete. Shipped 2026-07-28 in `b077d75`.

> **Written retrospectively on 2026-07-29**, from `b077d75`. This records what shipped; it did not guide it. The original overnight run built these features without writing their specs first, and inventing a plan after the fact would misrepresent how the work happened.

## Context

The site serves `src/data/generated/`, not the warehouse. A SQL change that
nobody republished would ship numbers no current code produces, and every test
would still pass — the artifacts are committed, so the site renders fine.

## What shipped

`pipeline/check_freshness.py`, wired to `make check-artifacts`. It runs a fresh
publish into a temporary location and byte-compares every committed artifact
against it, exiting non-zero and naming the drifted files on any mismatch.

This turns the review gate's reproducibility item from a judgement into an exit
code. It is the gate that matters most before any release.

## Where the record is

- `pipeline/check_freshness.py`, `make check-artifacts`
- `docs/runbook.md`
