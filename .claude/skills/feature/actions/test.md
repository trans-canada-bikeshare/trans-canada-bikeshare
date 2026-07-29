# Test Action

1. Read `docs/current-feature.md` and the spec's Acceptance Criteria.
2. Work out what kind of thing was built, and test it accordingly:

   | What changed | How it gets tested |
   |---|---|
   | Pipeline, SQL, column mappings | Contract tests over real source data |
   | Derived metrics | Unit tests with hand-checked expected values |
   | Site components | Vitest |
   | A document — audit, feasibility map, methodology | **Verification, not tests.** See step 4. |

   Do not write tests to look thorough. A spec whose deliverable is a
   verified document is finished when the document is verified.

3. For pipeline work, the tests that earn their keep here:
   - **Schema contract** — the expected headers for each source and era. An
     unknown header fails the test, exactly as it must fail the pipeline.
   - **Row accounting** — rows in equals rows kept plus rows dropped, and
     every drop has a named reason.
   - **Cross-city definition** — the same metric computed for each tier-1
     city agrees on units, trip filter, time window, and null handling.
   - **Boundary rows** — DST changes, month edges, midnight, leap day, trips
     that start in one month and end in the next.
   - **Known-bad rows** — negative durations, zero-second same-station
     trips, null stations, coordinates outside the service area.

4. For a document deliverable, verification means going back to the source:
   - Re-download at least one pinned file and confirm its checksum matches
     what the document claims.
   - Confirm the headers the document reports are the headers the file
     actually has — read them, do not trust the notes.
   - Confirm every claim about a field's presence, type, or coverage is
     backed by something you ran, and say which claims are inferred rather
     than observed.

5. Run the suites that exist in the repo. If none exist yet, say so.

6. **If any published artifact could have changed, check reproducibility now.**
   A green suite over stale artifacts proves nothing — the tests pass against
   code, the site serves the committed files.

7. Report: what was written or verified, what passed, which acceptance
   criteria are covered, and which need a human eye (a legend that reads
   clearly, a colour ramp that works, a sentence that is honest).

8. Stamp `- [x] test — YYYY-MM-DD` in `## Lifecycle`, but only if step 5
   actually ran something or step 4 actually re-derived something. A stamp
   means work happened, not that this action was invoked.
