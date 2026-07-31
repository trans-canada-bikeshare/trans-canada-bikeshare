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

## 2026-07-29: One station identity, materialised, or the fact and the dim drift

`fact_trips` and `dim_station` resolved station ids **differently**, and had
since spec 012. Both applied the Montreal era bridge; only `dim_station` also
applied the name bridge below it, which merges a station reached by its name
into the same station reached by its published id. So 781 Toronto keys covering
2,249,950 events, and 266 Vancouver keys covering 529,839, existed in the fact
with no row in the dimension at all. Montreal, the city the bridging work was
built for, was unaffected.

`40_model.sql` carried a comment asserting the two agreed. It had been false
for two of three cities for as long as it had existed, and nothing checked it.

Spec 022 then divided one by the other — flows from the fact, lifetime events
from the dim — producing a partial numerator over a merged denominator. It
inflated Vancouver's distinct-pair count by **44%**, Toronto's by 5%, and
Montreal's not at all. That is exactly the failure the same file warns about
twenty lines earlier: *"inflated by a different amount each, which is the worst
possible failure for a side-by-side comparison."* The warning was right, was
about this very mechanism, and did not prevent it.

Decision: **the resolution is a materialised table, `station_identity`, and
every consumer joins it.** Not a CTE inlined in whichever query needs it, and
not a comment claiming two computations match. A shared identity that is only
shared by convention will drift the moment one side gains a step the other
does not.

The rule generalises past stations: **when two tables must agree on a key, the
agreement is a table, not a claim.** Any invariant stated only in a comment is
one nobody has tested.

## 2026-07-29: A number in prose needs a query, not a memory

Three false figures shipped in spec 022's first draft, each written from
recollection of an earlier query rather than the one that matched the claim:

- *"a handful of stations reach 90%"* — no station on the map exceeds 0.735.
  The 90% came from a query over stations **without coordinates**, which are
  never drawn.
- *"In all three cities they are loops at parks"* — true for Toronto (14 of 20)
  and Vancouver (11), false for Montreal (5), and the third row rendered
  directly beneath the sentence was a metro-to-street commute.
- The loop counts written into the spec minutes after the list shrank from 20
  entries to 8, without re-deriving them.

The fix that actually holds is not more care. Every one of these is now
**derived in the component from the artifact**, so the sentence cannot drift
from the data it describes. Where a figure genuinely must be prose — a spec, a
commit message — it gets re-run at the moment of writing, not recalled.

## 2026-07-30: ECCC weather, and a licence named from memory

Spec 013 adds Environment and Climate Change Canada daily climate data — the
first new external source since spec 003. **Airport stations**, one per city:
longest continuous records, conventional, and verified to span each city's full
trip window before the spec was written. A downtown station sits closer to the
riding, but coverage matters more here than a few kilometres, and the record
already has gaps.

**The licence was recorded wrong, confidently.** The first version named the
"Environment and Climate Change Canada Data Servers End-use Licence", gave a
URL, and stamped it `checked 2026-07-29`. That is a real instrument — it
governs MSC Datamart and GeoMet — but it does not govern
`climate.weather.gc.ca` bulk historical data, and its name appears nowhere on
the page that was linked. The attribution string invented alongside it
("Contains information licensed under…") matched neither instrument.

What the governing licence actually says, read off the page:

- It is the **Licence Agreement for Use of Environment and Climate Change
  Canada Data**, headed "LIMITED USE SOFTWARE AND DATA PRODUCT LICENCE
  AGREEMENT".
- The required acknowledgement is **"based on Environment and Climate Change
  Canada data"**.
- It carries **redistribution restrictions no other source here has**: no fee
  may be charged explicitly for the ECCC product, and any party it is
  redistributed to must agree to the same restrictions before use.

The error ran in the dangerous direction — it understated the obligations, one
spec before [023](features/023-forecast.md) publishes derived weather under
them.

This is the mirror of the BIXI decision. BIXI's licence is *unknown and
labelled*, and that is honest; nobody downstream will mistake it for settled.
This was *stated and wrong*, with a URL and a checked-on date, which is the
combination that stops anyone looking again. **A licence gets read, not
recalled** — and the check date means the page was opened, so the date itself
becomes a false assurance when it was not.

**Owner decision, 2026-07-30: proceed and publish under these terms.** Asked
directly whether spec 023 should publish weather-derived values given the
redistribution restrictions, the answer was to proceed. The conditions are
satisfiable for this project as it stands — the site is free, so no fee is
charged for the ECCC product, and value-added services are expressly permitted.
The obligation that survives is on anyone redistributing *from* here: they must
agree to the same restrictions. That is why the restriction text lives in
`LICENSE` and in every manifest rather than only in this entry.

**The current year is pinned but marked `volatile`.** ECCC is still writing
2026, so its export gains a row daily and its checksum cannot be stable.
Refusing it would have made `--accept-changes` a daily routine, and a flag used
routinely stops protecting the entries that genuinely must not move. Every
closed year remains immutable and drift-refusing; only the open one is allowed
to advance, and the pin still records exactly what was used.

## 2026-07-30: Toronto's member label dies inside an era, so the era is withheld

> **Corrected the same day, by the adversarial audit below: the boundary was
> wrong.** The vocabulary change at 2018-01 was a tidy boundary, not the true
> one. The corruption is file-scoped and begins at 2021-10 — daily member
> share steps at file edges (68.2% -> 37.8% overnight at the 2021-10 file
> boundary, recovering to 78.9% at 2021-12) and 2018-2019 are indistinguishable
> from the clean eras by both share-tracking and the commute-hour behavioural
> discriminant. The first exclusion withheld 45 extra months — 10,092,788
> trips showing no sign of the defect. The withheld window is now
> **2021-10..2023-12** (11,089,535 trips), the contiguous span from the first
> corrupted file to the last. "Nothing in the data says when it stopped being
> trustworthy" was wrong: the data says it, at file boundaries — it just took
> a reviewer told to attack the boundary to look.

Spec 020 found that Bike Share Toronto's published files lose the member label
across 2018-2023. The vocabulary partitions the archive, and the boundaries are
a fact of the files rather than a judgement:

```
2016-01..2017-12   {Member, Casual}                74.6%, 78.0% member
2018-01..2023-12   {Annual Member, Casual Member}  81.8% -> 6.4%
2024-01..2026-03   {Member, Casual}                77.2%, 72.6%, 88.9%
```

(Trip-weighted year shares — members divided by labelled trips across the whole
year. Every figure in this entry uses that basis.)

Inside the middle era "Annual Member" decays to nothing — 50,961 trips in
March 2023, 12,226 in July, 138 in August, absent from September — while
ridership is at its yearly peak. Annual members do not vanish.

**It is Toronto's defect and it is unrecoverable.** The raw CSVs carry the same
header and the same `User Type` column with the values decaying inside it. CKAN
reports the 2023 resource last modified 2024-01-09 and never corrected; no
summary dataset carries the counts; the package readme documents only the
2014-2016 schemas. Imputing membership from trip behaviour would be inventing
data, which is the one thing this project cannot do.

**Decision: withhold the entire 2018-2023 era.** Not a chosen month — the
vocabulary is the boundary. The era begins at 81.8%, consistent with the eras
either side and with Vancouver, and ends at 6.4%; nothing in the data says when
it stopped being trustworthy, so no month inside it can be vouched for.
Dropping data that cannot be validated beats keeping data that cannot be
checked.

Passed on: excluding only 2023-07..12, which was the first plan. It would have
left a five-year decline in membership on the chart that never happened — a
worse lie than the one it fixed, because it is gradual enough to look real.
Also passed on: dropping Toronto's membership entirely, which the two stable
eras do not deserve.

What survives is coherent. On the same trip-weighted basis as the table above,
Toronto reads **74.6% and 78.0%** before the break and **77.2%, 72.6%, 88.9%**
after, while Vancouver's yearly figures sit in the same range. An earlier
version of this paragraph quoted 83/83 and 81/78/90 — the *unweighted mean of
monthly shares*, a different basis from the table three paragraphs above it,
with nothing saying so. It also called Vancouver "steady 70-86% throughout";
Vancouver's monthly share actually runs **59.2% to 93.4%** and falls outside
that band in 42 of 114 months, because it swings about 25 points every summer.
The point stands — the broken era was the only thing suggesting Toronto
differed from Vancouver — but it stands on the yearly basis, and a comparison
has to say which basis it is on.

**Lift this** if Toronto republishes those years with the label intact. It is
recorded in `pipeline/publish.py` as `UNRELIABLE_LABEL_ERAS`, the withheld
months ship in `membership.json` as `label_lost`, and the site explains the gap
from that artifact rather than asserting it.

## 2026-07-30: The audit, the transposed quarter, and the containment gate

A full adversarial audit of the overnight-and-after work found the worst data
defect this project has had: **Toronto's 2016.xlsx Q4 worksheet was corrupted
by Toronto's own Excel before publication**, and the pipeline reproduced it
faithfully. The sheet was built from D/M/Y text; Excel coerced every date with
day <= 12 into an M/D/Y datetime — day and month transposed — and left days
13-31 as strings. Uncorrected, 80,109 of 217,569 trips landed in January
through September, **fabricating six months of 2016 ridership that never
happened** (each existing only on days 9-12, one day past the incomplete-month
gate's threshold) and stripping Oct-Dec of their first twelve days. It was
live on the site in four artifacts.

Row accounting could never catch this: every row landed, on the wrong date.
The repair is a pure month/day swap, exactly scoped — within that sheet,
serial rows decode to day <= 12 and string rows parse to day >= 13, so the
predicate cannot touch a healthy row. Verified against the workbook with an
independent parser, and the post-repair boundary residue (467 rows moving to
Sep 30) is exactly the UTC->local shift.

Two permanent gates came out of it, because the class matters more than the
instance:

- **Containment**: every file's trips must live inside the period its name
  declares (2% tolerance for the timezone boundary; the defect was 37%).
  Swept the whole archive: 185 monthly and 34 annual files, zero violations
  post-repair. This is the check that catches date corruption that row
  accounting is structurally blind to.
- **Coercion signature**: any file whose Excel-serial dates never exceed
  day 12 fails the suite. A real month reaches day 28.

Also from the audit: the literal string 'NULL' is no longer accepted as a
station key (it minted a station with 7,947 trips); a partial system can no
longer open a *comparable* metric, and `check-metrics` now fails if a partial
system's rows appear under an artifact's `series` key — both holes the 020
review demonstrated live; months where most trips carry no label are withheld
(Vancouver 2025-05 was measured on eleven days and nothing said so); and the
quality report is order-deterministic.

## 2026-07-30: A model is validated against days that happened, not against its own R²

Spec 023's first ridership model was additive in month-of-year and calendar
year: August is busy, 2025 was a big year, add the two. Every gate passed. Log
R² sat at 0.87-0.93, the coefficients were signed the way anyone would expect,
the artifact reproduced byte for byte, and the tests were green.

Then it was asked a question the tests had not: what does it say about a warm
dry August 2025 weekday in Vancouver, and what actually happened on those days?
It said **7,636 trips**. The six comparable days averaged **5,331** — a 43%
overstatement, on the number the section renders in its largest type.

The cause is structural, not a bug. An additive model cannot represent a season
that was unusual *for its own year*, and Vancouver's 2025 was exactly that: up
on 2024 in January, down 18% in August. Its 2025 level averaged both. Marginal
residuals by month and by year were zero to three decimals, which is what OLS
with dummies guarantees and is why no diagnostic built from the fit itself
could have found this.

**Decision: give every calendar month its own level.** The weather coefficients
are then estimated only from how days differed *within* a month, which is the
cleanest identification of a weather effect the data supports, and the same
check now reads 1.03-1.10 across the three cities. The cost is real and is
stated on the page rather than buried: most of the parameters are calendar
levels, so these coefficients say nothing about seasonality, and the site's
seasonality section answers that question from its own artifact instead.

The general rule, and the reason this is here rather than only in the spec:
**a model's fit statistics cannot tell you the model is wrong in the way that
matters.** R², residual plots, byte-reproducibility and a full test suite were
all consistent with a headline number that was half again too big. What found
it was leaving the model and asking the warehouse what a day like that actually
looked like. Every model this project ships gets that check, and the check goes
in the spec file with its numbers.

Two smaller rules came out of the same work:

- **Refuse a rank-deficient design.** `numpy.linalg.lstsq` answers a singular
  system with the minimum-norm solution rather than failing — coefficients that
  fit exactly as well as infinitely many others, picked by LAPACK. It is a
  wrong number and a reproducibility hazard at once, since another BLAS may
  pick a different member of the same set. `fit_system` now checks the returned
  rank. It caught two singular designs in the tests within minutes of existing.
- **A rendered control is not verified until it has been driven.** The headed
  browser check, not any test, found that dragging the daily-high dial below
  the daily-low dial produced three "that is not a day" refusals and hid the
  one thing the control exists to show. The dials are now coupled. This is the
  2026-07-29 rule about rendering, extended: interaction is output too.

## 2026-07-30: A registry key is split by what each signal needs, not by its narrowest one

`operational_signals` covered two things: signals any trip record supports, and
dwell, which needs a bike identifier. One key can only ever be as narrow as its
narrowest signal, so it marked Montreal unsupported wholesale — and Montreal is
88M of the archive's 135.6M trips. The flagship system was excluded from a
comparable metric by a field it does not need.

Split into `rebalancing_pressure` (comparable, all three) and `bike_dwell` (not
comparable; Montreal unsupported, Vancouver and Toronto era-limited). Both gates
then enforce the two different answers instead of one wrong one.

**The rule this generalises to: a registry key is one metric with one support
answer.** Two signals with different support are two keys. The tell that a key
is doing too much is a `supported: false` whose reason applies to only part of
what the key describes — which is exactly what Montreal's read here.

`rebalancing_pressure` also carries the metric's caveat as a registry **field**,
not a comment: the artifact copies it and the page renders it verbatim. An
implied lower bound is the number on this site most easily read as a
measurement, and the sentence that says so should not be able to drift away
from it.

## 2026-07-30: Mobi publishes the hour and nothing finer

Found while checking why Vancouver's dwell quartiles were 3600 / 10800 / 50400
seconds in **every year**. `data-raw/van-mobi/2025-01.csv` has 62,518 rows and
**24 distinct time-of-day strings**. In the warehouse, 100% of Vancouver rows
carry both timestamps exactly on the hour in every era but two files (`2019-04`
and `2025-05`), against 0.000% of Montreal's and 0.003% of Toronto's.

It is the source, not the pipeline. `Duration (sec.)` is intact and is what the
duration metric uses, so nothing already published moves. But it binds every
future time-of-day surface:

- **Vancouver's hour buckets are the source's own hour labels.** The bucketing
  is genuine — 27.5% of its linked trips have a return hour differing from
  their departure hour, against 25.8% predicted by its own durations, in line
  with the other two — but whether the label floors or rounds the true time is
  not stated and cannot be recovered. The phase inside the hour is unknown.
- **Anything finer than an hour is unavailable for Vancouver.** Dwell, dock
  turnaround, minute-level demand: not a modelling choice, an absence.

`docs/source-audit.md` recorded "minute precision" from a sample whose rows all
read `0:00`. That reading is consistent with hour-only data and settled nothing,
and it stood for two specs. **A precision claim needs the distinct-value count,
not a row that happens to look like the claim.**

Registry treatment: `qualified: true` with the note, the shape Montreal already
carries under `station_flows`. Not `supported: false` — the hour-of-day
comparison holds, with a stated resolution — and not silence.

## 2026-07-30: A day the system did not operate is not a day

Montreal's archive ends 2026-06-30 and trips departing on the last days return
after it. Dating each event by its own timestamp is right; treating the dates
those returns land on as days the system ran is not. Twenty-one July dates carry
Montreal returns and no departures, one of them 617 returns against a
3,000-move norm, and averaging over them **diluted Montreal's implied
rebalancing by 3.8%**. Toronto has the same edge at 2026-04-01.

This is the incomplete-month gate's problem one level down. That gate is keyed
on the departure month, so a month with no departures at all is invisible to it
— not an incomplete month but a month that does not exist, carrying events
anyway.

**Rule: a per-day denominator counts days the system operated, evidenced by an
event that starts there.** And more generally, every archive has two edges, and
a metric averaged over time has to say which days it divided by.

The related decision, same spec: **a year the archive clips cannot be told apart
from a year the system only operated part of.** Montreal's 2014 opens in April
because BIXI opens in April; its 2026 stops in June because the archive does.
From inside the data those are identical, so the yearly chart draws only years
covered 1 January to 31 December and the page names the five it dropped.

## Next

Spec 001: download one real month from BIXI and Bike Share Toronto, read the
actual headers, and write a verified column-by-column feasibility map
(especially: e-bike flags, membership fields, station coordinates, timestamp
precision) before any pipeline code.
