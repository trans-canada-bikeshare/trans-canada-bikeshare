# Spec 004 — Inventory and archive verification

## Status

**Folded into 003 on 2026-07-28. No separate implementation.**

This number is kept so the sequence has no holes, and because the decision to
fold is worth more than the file it replaced.

## What happened

`pipeline/inventory.py` shipped inside spec 003: checksum and byte verification
against the manifests, gap detection (monthly for Vancouver, annual for the
other two), `PENDING` separated from `MISSING` and `CORRUPT`, wired to
`make check-manifest`.

Splitting it into its own spec would have been padding. The downloader and the
thing that verifies the download are one piece of work — the manifest is
written by one and read by the other, and a bug in either shows up as the same
symptom.

## Where the record is

- `docs/features/003-manifests-and-downloaders.md`
- `docs/roadmap.md`, Phase 1
- `pipeline/inventory.py`, `make check-manifest`
