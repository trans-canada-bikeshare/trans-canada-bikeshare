# Decisions

A short log of choices that shape the project, oldest first. Feature specs
live in docs/features/ once implementation starts, following the same
NNN-name.md convention as the Vancouver project.

## 2026-07-26: Name

**Trans-Canada Bikeshare.** Coined here; at the time of writing there were no
web or GitHub uses of the name. "Trans-Canada" follows the national
convention (Highway, Trail) rather than "Trans Canadian". The descriptive
form ("comparing Canada's bike share systems") lives in taglines, not the
name. Considered and passed on: "Trans Canadian Bikeshare Systems" (long,
clinical ending), "Canadian Bike Share Systems" (generic, hard to own).

## 2026-07-26: Separate repository from mobi-transit-explorer

The Vancouver project stays untouched as the single-city deep dive: it is
live, stable, personally voiced, and built around the Mobi Data License
Agreement. This project copies its patterns (manifest, era maps, staged
DuckDB SQL, freshness gate, contract tests, quality report, derived copy)
but designs for multiple systems from the first commit: a system dimension
in the star schema, one manifest and one era map per city, per-city publish
artifacts plus comparison artifacts. No shared library between the repos;
the READMEs cross-reference instead.

## 2026-07-26: Tier 1 before tier 2

v1 compares the three docked systems with per-trip OD data (Vancouver,
Montreal, Toronto). Calgary and Edmonton (dockless micromobility, anonymized
locations, no stations) arrive in v2 as a visibly separate panel, because
presenting fuzzed scooter trips as comparable to dock-to-dock rides would
undermine the honesty the methodology depends on.

## 2026-07-28: The /feature workflow

Features run through a single Claude skill, `/feature`, taking one of `load |
start | test | review | complete`. The five steps are the lifecycle the
Vancouver project already documents in prose (`docs/feature-lifecycle.md`
there); the skill mechanism — a thin `SKILL.md` dispatcher over one file per
action in `actions/` — is carried from the canadatest project, where it has
run about a hundred features. Working file `docs/current-feature.md`, specs
in `docs/features/NNN-name.md` from `000-template.md`.

Two gates block, and they are the reason the workflow exists rather than a
checklist nobody reads. **Review** blocks on data integrity and
comparability: provenance pinned to a checksummed manifest, no silent
guessing, row accounting that closes, artifacts that reproduce byte for
byte, and metrics defined identically across tier-1 cities or visibly
labelled as not comparable. **Complete** blocks on committing raw or large
files, and stops for an explicit yes or no — a raw trip file in git is
permanent, is in every future clone, and may breach a source licence, which
makes it the one mistake here a revert does not fix.

Passed on: the canadatest skill's sixth action, `explain` (the History entry
written at complete already carries the what-and-why); and its SEO gate,
which guards that project's growth lever and has no analogue here. What
belongs in that slot for this project is data honesty, so that is what the
review gate enforces.

## 2026-07-28: BIXI publishes no licence — UNRESOLVED, shipping anyway

The BIXI open-data page states no licence, no terms, and no attribution
requirement (observed in spec 001). A third party republishes the 2014–2021
files under CC BY-SA 4.0, but that is that author's choice and says nothing
about BIXI's terms.

Decision: **ingest and publish Montreal, and say plainly that the terms are
unknown.** Absence of stated terms is not a prohibition — BIXI presents these
files as open data on its own site — and a three-city comparison without
Montreal is not the project. The unresolved status is recorded in
`pipeline/manifests/mtl-bixi.json`, in `LICENSE`, and on the methodology page,
and BIXI Montreal is attributed throughout.

`LICENSE` previously claimed "BIXI Montreal open data terms". That claim was
unsupported and has been removed rather than softened. Toronto's required
attribution string — "Contains information licensed under the Open Government
Licence – Toronto" — was missing and has been added.

**Open action for the owner:** ask BIXI directly. If terms arrive that forbid
this use, the fix is one publish run: Montreal drops out of
`src/data/generated/` and the site renders it as unavailable.

## 2026-07-28: E-bike share and membership ship as two-city comparisons

Spec 001 established that Montreal publishes no bike-type field in any era and
loses `is_member` at the 2022 format break. Two of the README's headline
metrics therefore cannot be three-city comparisons.

Decision: **show both for Vancouver and Toronto, with Montreal explicitly
marked "not published" rather than absent.** A visible, explained gap is more
informative than a quietly missing city, and it is what "every visual encoding
says what it means" requires. Passed on: demoting the metrics to per-city
detail, and dropping them — Toronto's e-bike share reaching ~22% is the most
interesting trend in the data, and hiding it to keep a tidy grid would be the
wrong trade.

Spec 009's metric registry makes this enforceable rather than a matter of care:
publishing a cross-city series for a metric the registry does not mark
supported in every system in it is an error, not a judgement call.

## 2026-07-28: Overnight autonomous build, specs 003–026

Owner decisions for the run: ingest **every year each city publishes**,
resumable, with the site's copy deriving from whatever actually loaded so
partial coverage stays honest; **stop before deployment** — spec 027 is written
as a runbook and never executed; and prefer **depth over breadth** if time runs
short, always stopping on a merged spec rather than leaving work in flight.

## 2026-07-29: Review is delegated to a different model, never self-review

`/feature review` now launches Fable subagents rather than reviewing in the
authoring context. One agent per dimension the change touches, in parallel,
told nothing about what the author already suspects or fixed.

The evidence for the rule, from the overnight build of specs 003-026: a
self-review passed work that an independent Fable pass then found to contain
three separate data losses — 320,229 Toronto trips in a zip nested inside the
annual zip, 217,569 in an unread second worksheet of a workbook, and ~31,000
dropped silently on invalid encoding — plus 8.9M Montreal rows landing on the
wrong local day because BIXI's 2022+ epoch milliseconds are UTC while every
other era publishes local time. The site meanwhile carried four claims its own
data contradicted, including a winter-closure note that was false in present
tense directly above the chart disproving it.

All three losses had the same shape: a container whose contents were only
partially enumerated. The gates in this project fired precisely where their
author had anticipated failure and were silent everywhere else — which is the
structural argument, not a claim about any one model. The blind spot that
produces a bug also shapes the review of it, so the reviewer has to be
somewhere else. A different model makes that independence real rather than
nominal.

Corollaries written into `actions/review.md`: the reviewer is told nothing
about existing suspicions; findings need a query that demonstrates them, not a
reading of the code; every severity-1 finding is verified by the author before
being acted on; and a reviewer that reports nothing because it was blocked has
not delivered a pass.

## Next

Spec 001: download one real month from BIXI and Bike Share Toronto, read the
actual headers, and write a verified column-by-column feasibility map
(especially: e-bike flags, membership fields, station coordinates, timestamp
precision) before any pipeline code.
