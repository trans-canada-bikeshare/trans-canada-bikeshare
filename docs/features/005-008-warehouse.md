# Specs 005–008 — Extract, clean, conform, model

## Status

In progress

## Why these four are one spec

The roadmap lists them separately. They ship together because they are one
pipeline and none of them can be verified alone: extract's output is
untypeable until clean runs, clean's drops are meaningless until conform
explains them, and conform's station identity is unprovable until model builds
the dimension it feeds. Four merge cycles on code that only works as a unit
would be ceremony, not review.

Recorded here rather than silently: the roadmap numbering is unchanged, and
each stage keeps its own SQL file and its own row accounting.

## Depends On

- Spec 001 / the full-archive census — the era maps are authored from observed
  headers, not guesses.
- Spec 003 — the acquired archive and its manifests.

## Scope

- **Sources touched:** all three trip archives, plus Montreal's annual station
  snapshots.
- **Cities touched:** Vancouver, Montreal, Toronto. **Tier:** 1.
- **Published artifacts change:** No — the warehouse is not committed. Spec 014
  publishes from it.

## Changes

1. **Era maps** (`pipeline/mappings/{system}.json`), authored from
   `pipeline/census.py` over every acquired file. Unified columns are the
   **union** across systems; a field a system does not publish stays NULL, and
   that absence is what spec 009 reads.
2. **`10_extract.sql` + `run_extract`** — every file lands as VARCHAR with
   headers unified. **An unmapped header aborts the run.** Archives are unpacked
   once and cached. Tables are `IF NOT EXISTS` and the runner deletes only the
   systems it is reloading, so `--system` runs compose instead of wiping.
3. **`20_clean.sql` + `run_clean`** — typing, six timestamp formats plus epoch
   milliseconds, and drops limited to rows with no usable departure time or no
   departure station. Row accounting closes by construction: duplicates are
   *derived* as landed − kept − named-reasons, and a negative result raises.
4. **`30_conform.sql`** — station identity per system, canonical month derived
   from the timestamp, and quality flags.
5. **`40_model.sql`** — `fact_trips`, `dim_system`, `dim_station`, `dim_date`,
   `dim_membership`.

## The three decisions worth arguing about

**Unterminated trips are kept, not dropped.** BIXI's 2022+ files contain trips
with a start and no end. Dropping them would understate Montreal's ridership;
keeping them unflagged would corrupt every duration and flow figure. They are
kept, flagged `unterminated`, counted, and excluded by name wherever an ending
is required.

**Station identity falls back to a normalised name, and says when it did.**
Vancouver carries the id inside the station name (`0069 7th & Granville`).
Montreal uses three key spaces across four eras. Toronto ships names only for
2016 and half of 2017. So the conformed key is the published id where one
exists and a normalised name otherwise — and every row records **which**, via
the `station_matched_by_name` flag, because a name match is a weaker claim and
the quality report has to be able to say how much of the archive rests on one.

**"Active" is measured against each system's own latest data**, not the
archive's. A shared cutoff would retire stations in whichever system publishes
least often, which would be an artifact of publishing cadence masquerading as a
finding.

## Acceptance Criteria

- [ ] Every acquired file loads, or the run aborts naming the unmapped header
- [ ] `--system X` twice in a row yields identical counts, not doubled ones
- [ ] The clean funnel closes: landed = kept + dropped-by-named-reason, and a
      negative derived count raises rather than being reported
- [ ] Toronto 2014–2015 is excluded with its reason recorded, not silently
      skipped
- [ ] Canonical month is derived from the timestamp, never from the period label
- [ ] `is_ebike` is true/false only where the system publishes a signal, and
      NULL for Montreal in every era — never false-by-default
- [ ] Station coordinates resolve for Montreal from its annual snapshots
- [ ] Quality flags mark, and never delete, suspect rows
- [ ] `pytest` covers the pure logic; SQL is exercised against the real archive

## Data Integrity Checklist

- [ ] Manifest and checksums — inherited from 003, verified by `make check-manifest`
- [ ] Schema drift mapped explicitly; unknown headers abort
- [ ] Row accounting closes and is recorded in `etl_metrics`
- [ ] Metrics defined identically across cities — enforced at spec 009, but
      `is_ebike` NULL-for-Montreal is established here
- ~~Artifacts reproduce~~ — n/a, nothing published yet
- ~~Copy derives from the data window~~ — n/a, no site surface yet
- [ ] No raw data committed — the warehouse and archive are both gitignored

## Out of Scope

- The metric registry (009), quality report (010), freshness gate (011)
- GBFS coordinates (012) and weather (013)
- Anything published (014)

## Rollback

Single revert. The warehouse is a local build artifact and is rebuilt by
re-running the stages; nothing committed depends on it yet.
