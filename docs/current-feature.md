# Current Feature: 001 Source column audit and feasibility map

## Status

In Progress — branch `feature/001-source-column-audit`

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

### Progress against the goals (2026-07-28)

`docs/source-audit.md` written. Verified by reading real files over HTTP range
requests: BIXI 2021 and 2022 (the exact format break), BIXI 2025, Toronto 2017
and 2025. Vancouver carried from the sister project's mapping of 34 headers
across 102 files.

| Goal | State |
| --- | --- |
| Headers recorded verbatim | Met for every era read |
| Nine canonical fields per system | Met for every era read |
| Era boundaries | BIXI break located exactly; Toronto endpoints read, 2018–2024 unread |
| **E-bike yes/no per system** | **Met** — Vancouver yes, Toronto yes (`Bike_Model`), Montreal no |
| Timestamp format and precision | Formats and precision met with samples; **timezone basis unverified** |
| Station coordinates | Recorded per system; GBFS shape unread |
| Licence per system | Findings recorded; **none confirmed** |
| SHA-256 per sampled file | **Not met — deviation, see below** |
| Observed / inferred tagging | Met |
| **Go/no-go per headline metric** | **Met** |

**Deviation to resolve:** range reads never materialize a whole file, so
per-file checksums could not be computed. The audit defers them to spec 003.
That is a real departure from the spec as written — either accept it and amend
001's criteria, or download the sampled files in full to satisfy it.

**Headline finding:** e-bike share and membership mix **cannot** be three-city
comparisons. Montreal publishes no bike type in any era and drops `is_member`
at the 2022 break. Also: 13.3% of scanned BIXI 2025 trips have no recorded end,
and BIXI's page states no licence at all — which contradicts `LICENSE`.

**Not ready for `/feature test`.** Five goals are partial and one is unmet.

## History

<!-- Appended by `/feature complete`, oldest first. ONE LINE per feature:
     `YYYY-MM-DD` `<sha>` — what shipped. Spec path.
     The detail lives in the merge commit; `git show <sha>` is the record.
     Keep this file cheap to load — it enters context every session. -->
