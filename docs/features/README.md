# Feature specs

One file per spec, `NNN-name.md`, written from [`000-template.md`](000-template.md).
Each runs through the `/feature` workflow: **load → start → test → review →
complete**. See [`../../CLAUDE.md`](../../CLAUDE.md) for the workflow and
[`../roadmap.md`](../roadmap.md) for why the sequence is what it is.

**Every number 001–027 has a file, including the ones not built and the one
that was folded away.** A gap in the sequence would read as something missing
or hidden; a file saying "not built, here is what it would be" is more useful
to a reader and to anyone who wants to pick the work up.

## Conventions

- **A `b` suffix** (`002b`, `009b`) is work that belongs to an existing number
  rather than a new one — a second pass, or the half that did not ship the
  first time. It keeps the original number's meaning intact.
- **A range in the filename** (`005-008`) is several specs that shipped as one
  piece of work. That file says why.
- **"Written retrospectively"** at the top of a spec means the feature shipped
  before its spec existed, during the overnight autonomous build of
  2026-07-28/29, and the file records what happened rather than what was
  planned. Inventing a plan after the fact would misrepresent the work.

## Status

| # | Spec | Status |
|---|---|---|
| 001 | [Source column audit](001-source-column-audit.md) | Complete |
| 002 | [Repo scaffold](002-repo-scaffold.md) | Complete |
| 002b | [Brand identity](002b-brand-identity.md) | Complete |
| 003 | [Manifests and downloaders](003-manifests-and-downloaders.md) | Complete |
| 004 | [Inventory and archive verification](004-inventory-and-archive-verification.md) | **Folded into 003** |
| 005–008 | [Extract, clean, conform, model](005-008-warehouse.md) | Complete |
| 009 | [Metric support registry](009-metric-support-registry.md) | Complete — shipped half-built, see 009b |
| 009b | [The metric gate](009b-metric-gate.md) | Complete |
| 010 | [Quality report](010-quality-report.md) | Complete |
| 011 | [Freshness gate](011-freshness-gate.md) | Complete |
| 012 | [Station geography](012-station-geography.md) | Complete |
| 013 | [Weather](013-weather.md) | Complete |
| 014 | [Publish aggregates](014-publish-aggregates.md) | Complete |
| 015 | [App shell](015-app-shell.md) | Complete |
| 016 | [Overview](016-overview.md) | Complete |
| 017 | [Trips and seasonality](017-trips-and-seasonality.md) | Complete |
| 018 | [Active stations](018-active-stations.md) | Complete |
| 019 | [E-bike share](019-ebike-share.md) | Complete — two-city, Montreal labelled |
| 020 | [Membership mix](020-membership-mix.md) | Complete — Toronto 2021-10..2023-12 withheld, source defect |
| 021 | [Station maps](021-station-maps.md) | Complete |
| 022 | [Station flows](022-station-flows.md) | Complete |
| 023 | [Forecast](023-forecast.md) | Complete — coefficients published, not predictions; out-of-sample fit stated |
| 024 | [Operational signals](024-operational-signals.md) | Complete — Montreal in the comparable core |
| 025 | [Methodology and data quality](025-methodology-and-data-quality.md) | Complete |
| 026 | [Accessibility and responsive](026-accessibility-and-responsive.md) | Complete |
| 027 | [Deploy](027-deploy.md) | **Not built, deliberately** |

## Where the record actually lives

A spec states intent and acceptance criteria. What shipped is the commit, and
`git log` is the account of record — several specs here were backfilled from it
rather than from memory.

Two files carry the reasoning that outlives any single spec:

- [`../decisions.md`](../decisions.md) — the choices that bind the work, and
  what was passed on. Read this before starting anything.
- [`../roadmap.md`](../roadmap.md) — the sequence, the dependencies, and the
  gaps carried openly.
