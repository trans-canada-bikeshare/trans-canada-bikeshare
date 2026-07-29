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

## 2026-07-29: "Dormant", not "retired" — and one dot scale for all three maps

Spec 021's review forced two definitional choices that bind every station-level
surface after it.

**A station is "dormant", not "retired".** `is_active` means the station had a
trip in the last six months of *its own system's* data. That is not the same as
decommissioned: 25 Montreal and 3 Toronto stations the map drew as hollow are
listed in the GBFS feed downloaded the same morning, including one carrying
431,464 lifetime events. The flag is worth keeping — it is the only signal the
trip data supports — but the word on screen has to be one the data can defend.
Anything the site can only infer from absence is described as absence.

**Dot size uses one ceiling shared by all three maps.** Sizing each map to its
own busiest station made a 9 px dot mean 1,182,789 events in Montreal and
429,534 in Vancouver — three panels side by side, encoding at rates 2.75x
apart, under a single sentence explaining the encoding. Per-map normalisation
is defensible on a page showing one city; it is not defensible in a grid whose
heading is "Three networks, three shapes". The like-for-like invariant applies
to visual encodings, not only to numbers.

Corollary, also from 021: **a label must come from whatever supplied the
position.** Trip-file station names were chosen by `arg_max(name, last_ts)`,
and Toronto reuses retired station ids — id 7823 carries "Greenwood Ave /
Sammon Ave" on 4,771 rows and "Bloor St W / Christie St" on 3, and the three
won on a 54-minute timestamp margin. That shipped two dots labelled "Bloor St W
/ Christie St" 7.2 km apart. Where GBFS gives a usable coordinate, GBFS names
it too.

## 2026-07-29: A rendering surface is not verified until it has been rendered

Spec 021 shipped three station maps that drew **zero dots**. `seriesColor()`
returns `hsl(var(--series-van))`, which is correct for every SVG chart on this
site because the browser resolves it. MapLibre parses colours in JavaScript,
could not resolve the custom property, and rejected the whole layer — silently,
because registering an `error` listener suppresses MapLibre's own console
logging and that listener filtered for `/style/i`. Every gate passed: 52 tests,
typecheck, build, byte-identical artifacts, and a correct 260-station count
rendered above each empty box, under a caption reading "Select a station".

The author's own completion note said the dots had not been confirmed in a
browser. That sentence was the finding, and it was written and merged past.

Rule: **a feature whose output is rendered is not testable by its inputs.** If
the acceptance criteria say something is drawn, the review has to observe it
drawn.

The colour fix was necessary and not sufficient. With the layer finally
accepted, all three maps were *still* blank — and the second cause was worse,
because it produced no signal at all. MapLibre v6 spawns its tile-parsing
worker from a blob that resolves `maplibre-gl-worker.mjs` against
`import.meta.url` at runtime. Rollup cannot see that string, so no chunk was
emitted; the built site requested `/assets/maplibre-gl-worker.mjs`, the SPA
fallback answered **HTTP 200 with index.html**, and the worker died trying to
parse HTML as a module. No 404. No main-thread error. MapLibre parses both
vector tiles *and* GeoJSON in that worker, so the basemap and our own dots
failed together — which is why the symptom read as "maps don't work" rather
than "our layer is wrong". Dev failed differently, via Vite's dep
pre-bundling, so the two environments needed separate fixes.

**Verify renders in a headed browser, driven directly.** Headless Playwright
and backgrounded automation tabs throttle `requestAnimationFrame` to zero.
MapLibre then never renders, never requests a tile, and reports nothing —
every reading is equally consistent with "working" and "completely broken".
Five rounds of diagnostics were spent on tabs that could not answer the
question, and twice concluded "probably the environment" from evidence that
could not distinguish the two. A headed Chromium answered it in one run.

Corollary: **when a diagnostic disagrees with the person looking at the
screen, the person is right.** The owner reported blank maps while the
instrumentation said the layer was accepted; the instrumentation was measuring
a throttled tab. Three control pages written to settle it were themselves
broken — a 404'd script tag, then a wrong import shape — and each blank result
looked like a finding.

Two regression guards, both cheap: a test that nothing handed to MapLibre
contains `var(`, and a build-time assertion that the worker assets reached
`dist/assets`.

## Next

Spec 001: download one real month from BIXI and Bike Share Toronto, read the
actual headers, and write a verified column-by-column feasibility map
(especially: e-bike flags, membership fields, station coordinates, timestamp
precision) before any pipeline code.
