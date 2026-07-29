# Spec 003 — Per-city manifests and downloaders

## Status

Ready

## Context

Every number the site will ever show has to trace back to a specific file with
a specific checksum. That is the first principle in `README.md` and the first
item in the review gate, and nothing satisfies it today — spec 001 read headers
over range requests and deliberately deferred checksums here.

The three systems publish in three different ways, and spec 001 established
exactly how:

| System | Discovery | Files |
| --- | --- | --- |
| `van-mobi` | scrape `mobibikes.ca/en/system-data` for Google Drive links | one 2017 workbook + monthly, xlsx/csv/sheets |
| `mtl-bixi` | scrape `bixi.com/en/open-data/` for CDN links | one ZIP per year, 2014–2026 |
| `tor-bikeshare` | CKAN `package_show` API | one ZIP per year, 2014–2026 |

**Discovery is cheap; downloading is not.** The full archive is several GB —
BIXI 2024 alone is 476 MB and its 2025 file is 2.8 GB uncompressed. So this
spec separates the two: discovery populates every manifest entry from each
system's own source of truth without fetching payloads, and downloading is an
explicit, resumable operator action.

## Depends On

- Spec 001 — the URL inventory, per-system file shapes, and licence findings.
  Complete as of `5425262`.
- Spec 002 — `common.py`'s `SYSTEMS` registry, `sha256_file`, `detect_format`,
  and the manifest read/write helpers. Complete as of `7093bac`.

## Scope

- **Sources touched:** all three trip archives and their discovery surfaces.
- **Cities touched:** Vancouver, Montreal, Toronto.
- **Tier:** 1.
- **Published artifacts change:** No. Manifests are committed; `src/data/generated/`
  stays empty until spec 014.

## Changes

1. **`pipeline/discover.py`** — refresh each manifest from its system's source
   of truth. Per-system discovery, one shared writer.
   - `van-mobi`: parse Drive/Sheets links and their period labels, including
     the `Novemeber 2021` misspelling and the `ALL of 2017` label
   - `mtl-bixi`: parse the annual ZIP links
   - `tor-bikeshare`: CKAN `package_show`, taking resource URLs by year
   - **New periods are added. A changed URL for an existing period is
     reported, never applied**, unless `--accept-changes` is passed. A source
     that silently repoints is the failure this whole design exists to catch —
     Toronto re-published 2024–2026 on the day of the spec-001 audit.
2. **`pipeline/download.py`** — fetch what the manifests list.
   - Idempotent: a file already on disk whose SHA-256 matches its pin is
     skipped without a request.
   - On download, detect format by magic bytes and store `sha256`, `bytes`,
     `content_format`, and `downloaded_at` into the manifest.
   - **A re-download whose content differs from an existing pin fails**, listing
     the periods that drifted, unless `--accept-changes` is passed.
   - `--system` and `--period` scope the run; the default is everything.
   - Reference data (GBFS `station_information` per system) is fetched by the
     same path and pinned the same way.
3. **`pipeline/manifests/{van-mobi,mtl-bixi,tor-bikeshare}.json`** — committed.
   Populated by discovery for every period; checksums fill in as files are
   downloaded, so a partially-downloaded archive is a valid state.
4. **Licence block per manifest**, carrying what spec 001 established: name,
   URL, date checked, and required attribution string. `null` with a note where
   none is stated, which is currently Montreal's situation.
5. **Fix `LICENSE`.** Its BIXI claim is unsupported by the source page, and its
   Toronto entry omits the required attribution wording. Correct both to what
   spec 001 observed.
6. **`make check-manifest`** stops being a stub: verify every manifest entry
   against disk — checksum, byte size, and gaps in the expected period run —
   and exit non-zero on any mismatch. Files not yet downloaded are reported as
   pending, not as failures.

## Acceptance Criteria

- [ ] `discover.py` populates all three manifests with every period each system
      publishes, from the live source, with no payload downloads
- [ ] A changed URL for an existing period is **reported and not applied**
      without `--accept-changes`
- [ ] `download.py` fetches a requested period, stores SHA-256, byte size, and
      magic-byte-detected format into the manifest
- [ ] Re-running `download.py` on an already-correct file makes **no network
      request** and leaves the manifest byte-identical
- [ ] A pinned file whose content changes causes a **non-zero exit** naming the
      drifted period, and does not overwrite the pin
- [ ] Format is determined by magic bytes; a file whose extension disagrees with
      its content is stored by content
- [ ] At least one real file per system is downloaded, checksummed, and pinned —
      and the Vancouver pin matches the sister project's manifest for the same
      period, which is an independent reproduction of that archive
- [ ] GBFS `station_information` is pinned for all three systems
- [ ] Every manifest carries a licence block reflecting spec 001's findings,
      including Montreal's absence of stated terms
- [ ] `LICENSE` no longer makes the unsupported BIXI claim and carries Toronto's
      required attribution wording
- [ ] `make check-manifest` exits 0 on a consistent archive and non-zero on a
      corrupted one, distinguishing *pending* from *failed*
- [ ] `pytest` covers the pure logic — period parsing, change detection,
      verification — without touching the network

## Data Integrity Checklist

- [ ] Manifest entry with checksum and licence for every downloaded source file
- [ ] Schema drift mapped explicitly — n/a here; extraction is spec 005. But
      discovery must fail loudly on an unrecognized link label rather than skip
      it silently
- ~~Row accounting~~ — n/a, no ETL yet
- [ ] Metrics defined identically — n/a, no metrics yet
- ~~Artifacts reproduce~~ — n/a, no published artifacts yet
- ~~Copy derives from the data window~~ — n/a, site untouched
- ~~Encodings explained~~ — n/a, no visuals
- [ ] Source licence attribution present in each manifest and corrected in
      `LICENSE`
- [ ] No raw trip data committed — everything lands in gitignored `data-raw/`

## Testing

- **pytest, no network:** period-label parsing per system (including
  `Novemeber 2021` and `ALL of 2017`), URL-change detection, checksum
  verification, pending-vs-failed classification, and the refusal to overwrite
  a drifted pin.
- **Live, one file per system:** download, confirm the stored checksum matches
  a recomputed one, re-run to prove idempotency, then corrupt a byte and
  confirm `make check-manifest` fails.
- Full-archive acquisition is an operator action, not a test.

## Out of Scope

- Downloading the complete multi-GB archive — the commands support it; running
  it is the operator's call
- Any parsing of file *contents* beyond magic bytes — extraction is spec 005
- Inventory reporting beyond `check-manifest`'s pass/fail — spec 004
- ECCC weather acquisition — spec 013

## Rollback

Single revert. Manifests are additive and nothing downstream reads them yet.
Downloaded files under `data-raw/` are untracked and unaffected.
