# Data licences, attribution, and source terms

The repository's **source code is licensed MIT — see [`LICENSE`](LICENSE)**,
which now contains the MIT text and nothing else. This file carries everything
that is not code.

The MIT licence applies to the SOURCE CODE only. Generated data artifacts in
this repository are analysis outputs derived from each bike share system's
published open data and remain governed by the source licences below. Every
obligation here is also recorded in the manifest entry for the files it covers
(`pipeline/manifests/*.json`) and surfaced on the site's methodology section.

## Vancouver — Mobi by Rogers

- Mobi by Rogers trip data: Mobi Data License Agreement, non-commercial
  analysis use (https://www.mobibikes.ca/en/system-data).

### What the source states about the data itself

Recorded 2026-07-31 from https://www.mobibikes.ca/en/system-data, which states,
verbatim:

> Departure and Return times of trips have been rounded to the nearest hour to maintain the privacy of our users.

> Trips made by our Operations team for purposes of rebalancing and maintenance have been removed.

These are not licence terms, but they bind what the published data can be used
to say, so they are recorded here beside them. Two consequences carried through
this project:

- Vancouver's hour-of-day surfaces are the source's own **rounded** hour
  labels, and the rounding is a deliberate privacy measure rather than an
  unexplained artifact. This corrects the earlier reading in `docs/decisions.md`
  (2026-07-30, "Mobi publishes the hour and nothing finer"), which said whether
  the label floored or rounded "is not stated and cannot be recovered". The
  source states it.
- Vancouver's **implied rebalancing** signal is computed from data whose
  publisher has removed actual operations movements, so it can neither be
  checked against them nor include them. The `rebalancing_pressure` caveat in
  `pipeline/mappings/metric_support.json` says so, and the site renders it.

## Montreal — BIXI

- BIXI Montreal trip data: **no licence, terms, or attribution text is stated
  on the source page** (https://bixi.com/en/open-data/, checked 2026-07-28).
  BIXI publishes these files as open data, and this project attributes them to
  BIXI Montreal throughout, but the absence of stated terms is UNRESOLVED and
  recorded as such in pipeline/manifests/mtl-bixi.json, docs/decisions.md, and
  the site's methodology. A previous version of this file claimed "BIXI
  Montreal open data terms"; that claim was not supported by the source and has
  been removed.

## Toronto — Bike Share Toronto

- Bike Share Toronto ridership data: Open Government Licence – Toronto
  (https://open.toronto.ca/open-data-licence/), the portal-wide default.
  Required attribution, reproduced on the site and in the manifest:

      Contains information licensed under the Open Government Licence – Toronto.

## Weather — Environment and Climate Change Canada

- Daily climate data: **Licence Agreement for Use of Environment and Climate
  Change Canada Data** ("LIMITED USE SOFTWARE AND DATA PRODUCT LICENCE
  AGREEMENT"), https://climate.weather.gc.ca/prods_servs/attachment1_e.html,
  checked 2026-07-30. Required attribution, in the wording the licence itself
  gives, reproduced on the site and in each manifest:

      based on Environment and Climate Change Canada data

  This licence carries REDISTRIBUTION RESTRICTIONS that the other source
  licences here do not: no fee may be charged explicitly for the ECCC product,
  and any party it is redistributed to must agree to the same restrictions
  before use. Charges for value-added services are permitted. This binds any
  surface that publishes weather-derived values.

  A previous version of this file named the "Environment and Climate Change
  Canada Data Servers End-use Licence" — a real instrument, but one that
  governs MSC Datamart/GeoMet rather than climate.weather.gc.ca, and which
  carries no such restrictions. The name and the attribution string were both
  wrong and have been replaced with what the licence page actually says.

  One airport station per city — VANCOUVER INTL A (climate 1108395), MONTREAL
  INTL A (7025251), TORONTO INTL A (6158731) — pinned per year by checksum in
  pipeline/manifests/*.json. See docs/features/013-weather.md.

## Other sources

- Any additional city sources carry the licence stated in their manifest entry.

## Marks

The 11-point maple leaf in this project's marks is the leaf of the National
Flag of Canada, used in a design per Order in Council P.C. 1965-1623 s.4. No
exclusive right to the maple leaf is claimed. The bicycle pictogram is the
German StVO 1992 Sinnbild Radfahrer, public domain under §5(1) UrhG. This
project is not affiliated with or endorsed by Mobi by Rogers, BIXI Montréal,
Bike Share Toronto, or the Government of Canada.

## Raw data

Raw trip data is never committed to this repository.
