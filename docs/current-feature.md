# Current Feature: 001 Source column audit and feasibility map

## Status

In Progress — branch `feature/001-source-column-audit`

## Lifecycle

<!-- Each action stamps its own line with the date it ran. `/feature complete`
     refuses to proceed while `review` is unstamped. -->

- [x] load — 2026-07-28
- [x] start — 2026-07-28
- [x] test — 2026-07-28
- [x] review — 2026-07-28

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
| Headers recorded verbatim | **Met** for all nine files read |
| Nine canonical fields per system | **Met** |
| Era boundaries | **Met** — BIXI 4 eras, Toronto 4 layouts; unread years sit inside observed eras |
| **E-bike yes/no per system** | **Met** — Vancouver yes (observed), Toronto yes (`Bike_Model`), Montreal no |
| Timestamp format and precision | **Met** with samples; timezone basis deferred |
| Station coordinates | **Met** — GBFS verified ×3, per-era key bridge resolved |
| Licence per system | **Met** — Toronto confirmed, BIXI confirmed as none stated, Mobi carried |
| Byte size and URL per file | **Met**; SHA-256 amended out to spec 003 |
| Observed / inferred tagging | **Met** |
| **Go/no-go per headline metric** | **Met** |

**Test action (2026-07-28).** No suites exist yet — nothing to run, and nothing
invented. Verification instead, per the document-deliverable branch of
`actions/test.md`:

- Four headers re-read over fresh connections and compared to the recorded
  tables — **all four match character-for-character** (Toronto 2025, Toronto
  2022 including the double-spaced `Trip  Duration`, BIXI 2021, BIXI 2025).
- Vancouver `2025-01` downloaded in full: all thirteen headers match the
  carried map, and SHA-256 + byte size are **identical to the sister project's
  pinned manifest** — an independent reproduction of the source.
- Reproducibility gate n/a — this spec publishes no artifacts.

**Findings.** E-bike share and membership mix cannot be three-city comparisons.
BIXI has unterminated trips (rate not quantifiable from a partial scan — an
earlier 13.3% figure was corrected to 2.8% and then withdrawn as unreliable,
since the file is not randomly ordered). BIXI states no licence, contradicting
`LICENSE`. Toronto dates are month-first, confirmed empirically. No city's
period label can be trusted as its content month.

## History

<!-- Appended by `/feature complete`, oldest first. ONE LINE per feature:
     `YYYY-MM-DD` `<sha>` — what shipped. Spec path.
     The detail lives in the merge commit; `git show <sha>` is the record.
     Keep this file cheap to load — it enters context every session. -->
