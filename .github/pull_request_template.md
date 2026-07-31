<!--
Thanks for the PR. The checklists below are the project's gates, not
formalities: `make check` is what stands between a SQL edit and a wrong number
on a live page. Delete nothing — an unticked box with a reason beside it is a
useful answer, and a ticked box that was not run is the one thing this file
exists to prevent.

CONTRIBUTING.md explains every command here, including how to run the whole
pipeline offline from a clean clone in about two seconds.
-->

## What this changes, and why

<!-- One concern per PR. The why is the part that survives. -->

## Gates

Tick what you ran; say "not run — no archive" or "not applicable" beside
anything you did not. **A skip is not a pass.**

- [ ] `.venv/bin/python -m pytest pipeline/tests`
- [ ] `npm test && npm run typecheck && npm run build`
- [ ] `make check-fixture` — the whole pipeline over the synthetic fixtures,
      offline, no archive needed
- [ ] `make check` — manifest, metrics, artifacts, report, reconciliation,
      data dictionary. **Needs the ~20 GB archive**; "not run — no archive" is
      the expected answer from a contributor, and CI does not cover it.

CI runs `pytest` and `check-fixture` on a clean runner and must be green before
this merges.

## Data

- [ ] **No raw trip data, and nothing from `data-raw/`, is in this diff.** A
      raw file in git is in every future clone and may breach a source licence;
      it is the one mistake here a revert does not fix.
- [ ] Published artifacts in `src/data/generated/` are **unchanged** by this
      PR — or, if they changed, `make check-artifacts` was run and the diff is
      explained below.
- [ ] Any artifact shape change moves its schema in `pipeline/schemas/` in the
      same commit, and `python pipeline/generate_data_dictionary.py` was rerun.
- [ ] A new or changed published number is stated below **with the query that
      produced it**. A figure in prose needs a query, not a memory.
- [ ] Nothing is guessed silently: no new bare `except`, no `fillna`, no
      default standing in for a missing field. An unknown value should stop the
      pipeline and name itself.
- [ ] Cross-city claims use identical definitions, or the metric is labelled as
      not comparable in `pipeline/mappings/metric_support.json`.

### Numbers this PR moves

<!-- Artifact/field, before → after, and the query. "None" is a fine answer. -->

None.

## Rendered surfaces

- [ ] Not applicable — this PR renders nothing new.
- [ ] Verified in a **headed** browser, and I say below what I saw.

<!-- Headless and backgrounded tabs throttle requestAnimationFrame to zero, so
they cannot tell a drawn map from a blank one: spec 021 shipped three maps
drawing zero dots with every automated check green. If the acceptance criteria
say something is drawn, someone has to have watched it draw. -->
