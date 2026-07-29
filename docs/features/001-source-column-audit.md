# Spec 001 — Source column audit and feasibility map

## Status

Ready

## Context

Three systems, three independent schema histories, and no pipeline code yet.
The Vancouver project needed 34 distinct raw headers mapped across 31 layouts
for **one** city; there is no reason to expect Montreal and Toronto to be
tidier, and at least one incompatible break is already known — BIXI's format
changes at 2022, and `start_station_code` becomes `emplacement_pk_start` in
2021.

More pointedly: the README promises e-bike share as a headline metric, and it
is currently unknown whether Montreal or Toronto publish a bike-type field at
all in their open trip data. Toronto's own business reporting cites 1.1M e-bike
trips in 2024, but that figure may come from internal data rather than the open
CSV. If the flag is not in the open files, that metric cannot be like-for-like,
and the site's headline set has to change. Better to know now than after four
specs of pipeline are built on the assumption.

This spec reads the real files and writes down what is actually there. No
guessing, no inference from other people's analyses, no pipeline code.

## Depends On

None. This is the first spec.

## Scope

- **Sources touched:** Mobi by Rogers trip archive; BIXI Montréal open data;
  Bike Share Toronto ridership data (CKAN); the GBFS feed for each system.
- **Cities touched:** Vancouver, Montreal, Toronto.
- **Tier:** 1 (docked, like-for-like).
- **Published artifacts change:** No. The deliverable is
  `docs/source-audit.md` plus a decisions entry. Nothing is published, and no
  pipeline code is written.

## Changes

1. **Sample selection.** Choose the smallest set of real files that covers
   every suspected schema era per system, and record why each was chosen:
   - **Vancouver** — the `ALL of 2017` workbook, one early monthly CSV, and the
     most recent published month. Source page:
     `https://www.mobibikes.ca/en/system-data`
   - **Montreal** — one year from each candidate era: 2014, 2021, 2022, and the
     most recent published year. Annual ZIPs from `https://bixi.com/en/open-data`
   - **Toronto** — `bikeshare-ridership-2014-2015.xlsx`, one mid-era annual ZIP,
     and the most recent annual ZIP, via the CKAN `package_show` API for
     `bike-share-toronto-ridership-data`
   - **All three** — the current GBFS `station_information` feed
2. **Download to `data-raw/audit/`**, which `.gitignore` already covers via
   `data-raw/`. Record SHA-256 and byte size for every file as it lands. These
   are not manifest entries yet — the manifest is spec 003 — but the checksums
   recorded here must match what 003 later pins.
3. **Read headers directly** from each file, including one member CSV from
   inside each annual ZIP. Record every header **verbatim**, including
   misspellings, casing, accents, and mojibake. The Vancouver project ships
   `Memebership type` and `Return temperature (Â°C)` as real headers; assume
   the other two cities have their own.
4. **Sample real values** — at least three rows per file — for every field that
   maps to a canonical concept. A header name is not evidence of what the
   column contains.
5. **Write `docs/source-audit.md`** with the per-system, per-era column tables
   and the feasibility verdicts below.
6. **Log the outcome in `docs/decisions.md`** — specifically any headline
   metric that turns out not to be derivable for all three systems.

## The canonical fields to resolve

For each system and era, the audit answers: which raw column, what type, what
precision, and observed or inferred.

| Canonical field | Why it matters |
| --- | --- |
| `departure_ts` / `return_ts` | Every time series. Precision and timezone decide whether hourly comparison is honest |
| `departure_station` / `return_station` | Flows, station counts, maps |
| station coordinates | Maps and transit proximity. Inline, separate file, or GBFS-only |
| `duration_s` | Trip length distributions |
| `distance_m` | Vancouver has it; the others likely do not |
| `membership` / user type | Member vs casual mix |
| `bike_id` | Fleet-level signals |
| **`is_ebike` / bike type** | **The headline metric most at risk. Resolve first** |
| `system_id` | Assigned by us, not by the source |

## Acceptance Criteria

- [ ] Every distinct header in every sampled file is recorded verbatim in
      `docs/source-audit.md`, attributed to the system, period, and file it
      came from
- [ ] For each of the nine canonical fields above, the audit states per system
      one of **present** (naming the raw column), **absent**, or **derivable**
      (naming the derivation and its caveat)
- [ ] Every era boundary is identified by the period at which headers change,
      with both the before and after header sets recorded
- [ ] E-bike derivability is answered **yes or no per system**, each backed by a
      named column and a sampled value, or by an explicit statement that no such
      column exists in the open files
- [ ] Timestamp format, precision, and timezone are recorded per system and era,
      each with a real sampled value pasted in
- [ ] Station coordinate availability is recorded per system, naming the file
      that carries it and whether historical stations are covered or only
      currently-live ones
- [ ] The licence for each system's trip data is recorded with its URL and the
      date checked, and any conflict with the claims in `LICENSE` is flagged
- [ ] Every sampled file has its SHA-256, byte size, and retrieval URL recorded
- [ ] Every claim in the document is marked **observed** or **inferred**; no
      claim about a column's contents rests on a header name alone
- [ ] The audit ends with a go / no-go per README headline metric — trips,
      active stations, e-bike share, station flows, forecast, signals — stating
      for each whether it can be computed like-for-like across all three systems
      from open data

## Data Integrity Checklist

- [ ] Checksums recorded for every sampled file, so spec 003's manifest can be
      cross-checked against them
- [ ] Every header recorded verbatim — nothing normalized, corrected, or
      silently skipped
- [ ] Every claim marked observed or inferred
- [ ] Source licence recorded per system, with any conflict against `LICENSE`
      flagged
- [ ] No raw trip data committed — samples live in gitignored `data-raw/audit/`
- ~~Row accounting~~ — n/a, no ETL exists yet
- ~~Artifacts reproduce~~ — n/a, this spec publishes no artifacts
- ~~Metrics defined identically across cities~~ — n/a, this spec *determines*
  which metrics can be; spec 009 encodes the answer
- ~~Copy derives from the data window~~ — n/a, no site yet
- ~~Encodings explained~~ — n/a, no visuals

## Testing

No unit tests — the deliverable is a document. Verification instead, per
`/feature test`:

1. Re-download at least one file per system and confirm its SHA-256 matches
   what the audit recorded.
2. Re-read the headers of one file per system per era, independently of the
   first pass, and confirm they match the recorded tables character for
   character.
3. Confirm every "observed" claim has a sampled value behind it in the
   document. Any claim that cannot be traced to a sample gets downgraded to
   inferred or removed.

## Out of Scope

- Any pipeline code, including the downloader — that is spec 003
- The manifest format itself — spec 003
- Column era maps as machine-readable JSON — spec 005 writes those *from* this
  audit
- Calgary and Edmonton dockless data — tier 2, deferred to v2 per
  `docs/decisions.md`
- Deciding the site's metric set. This spec reports what is derivable; the
  product decision follows from it

## Rollback

Nothing to roll back — no code, no artifacts. If the audit is found to be wrong
later, correct `docs/source-audit.md` and re-run the affected downstream spec.
The document is the contract; specs 005 through 008 read from it.
