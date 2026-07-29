# Current Feature: 001 Source column audit and feasibility map

## Status

Not Started

## Lifecycle

<!-- Each action stamps its own line with the date it ran. `/feature complete`
     refuses to proceed while `review` is unstamped. -->

- [x] load — 2026-07-28
- [ ] start
- [ ] test
- [ ] review

## Goals

- Every distinct header in every sampled file is recorded verbatim in
  `docs/source-audit.md`, attributed to the system, period, and file it came from
- For each of the nine canonical fields, the audit states per system one of
  **present** (naming the raw column), **absent**, or **derivable** (naming the
  derivation and its caveat)
- Every era boundary is identified by the period at which headers change, with
  both the before and after header sets recorded
- E-bike derivability is answered **yes or no per system**, each backed by a
  named column and a sampled value, or by an explicit statement that no such
  column exists in the open files
- Timestamp format, precision, and timezone are recorded per system and era,
  each with a real sampled value pasted in
- Station coordinate availability is recorded per system, naming the file that
  carries it and whether historical stations are covered or only currently-live
  ones
- The licence for each system's trip data is recorded with its URL and the date
  checked, and any conflict with the claims in `LICENSE` is flagged
- Every sampled file has its SHA-256, byte size, and retrieval URL recorded
- Every claim in the document is marked **observed** or **inferred**; no claim
  about a column's contents rests on a header name alone
- The audit ends with a go / no-go per README headline metric — trips, active
  stations, e-bike share, station flows, forecast, signals — stating for each
  whether it can be computed like-for-like across all three systems from open data

## Notes

**Depends on:** nothing. First spec.

**Sources:** Mobi by Rogers (`mobibikes.ca/en/system-data`); BIXI Montréal
(`bixi.com/en/open-data`); Bike Share Toronto via CKAN
(`bike-share-toronto-ridership-data`); GBFS `station_information` for all three.

**Cities:** Vancouver, Montreal, Toronto. Tier 1.

**Published artifacts change:** No. Deliverable is `docs/source-audit.md` plus a
`docs/decisions.md` entry. No pipeline code — that is spec 003 onward.

**Licence constraints:** Mobi Data License Agreement (non-commercial analysis).
BIXI terms need confirming — a third-party republication cites CC BY-SA 4.0,
which if it applies to BIXI's own files carries share-alike obligations that
`LICENSE` does not currently reflect. Toronto's CKAN record returns a null
licence field; the portal-wide Open Government Licence – Toronto is the
presumed default and must be confirmed. **Any conflict found gets flagged, not
resolved silently.**

**Known risk this spec exists to resolve:** e-bike share is a README headline
metric and may not be derivable from Montreal or Toronto open data. Toronto's
business reporting cites 1.1M e-bike trips in 2024, but that may be internal
rather than open data. Resolve this first — a no answer changes the site's
headline metric set and spec 019.

**Samples land in** gitignored `data-raw/audit/`. Checksums recorded here must
match what spec 003's manifest later pins.

## History

<!-- Appended by `/feature complete`, oldest first. ONE LINE per feature:
     `YYYY-MM-DD` `<sha>` — what shipped. Spec path.
     The detail lives in the merge commit; `git show <sha>` is the record.
     Keep this file cheap to load — it enters context every session. -->
