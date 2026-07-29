---
name: feature
description: Manage the feature lifecycle for this project - load, start, test, review or complete
argument-hint: load|start|test|review|complete
---

# Feature Workflow

Runs one feature from spec to merged `main`. Five steps, always in order:

**load → start → test → review → complete**

This is the lifecycle the Vancouver project uses
(`mobi-transit-explorer/docs/feature-lifecycle.md`), automated, with the
gates a public data project needs.

## Working File

@docs/current-feature.md

## Feature Specs

Specs live in `docs/features/` as `NNN-name.md`, numbered in the order they
were written: `001-source-column-audit.md`, `002-manifest.md`, and so on.
`docs/features/000-template.md` is the template — every spec carries
**Acceptance Criteria** (the goals), **Depends On**, **Scope** (sources,
cities, whether published artifacts change), and a **Data Integrity
Checklist**.

### current-feature.md structure

- `# Current Feature` — H1 gains the feature name while one is active
- `## Status` — Not Started | In Progress | Complete
- `## Lifecycle` — four boxes stamped by the actions that ran. `complete`
  refuses while `review` is unstamped
- `## Goals` — the spec's Acceptance Criteria, verbatim
- `## Notes` — dependencies, sources and cities touched, licence
  constraints, whether published artifacts change
- `## History` — one line per completed feature, oldest first, append only.
  The detail lives in the merge commit, not here

## Reference

Read `docs/decisions.md` before starting any feature. It is the log of
choices that bind the work — the tier-1/tier-2 split, the separate-repo
decision, the naming. A feature that contradicts a logged decision is a
conversation to have at load, not at review.

`README.md` states the project's principles. They are not aspirations; they
are the review gate in `actions/review.md`.

**Review is never self-review.** `/feature review` delegates to subagents on a
different model. The reason, and the evidence for it, is at the top of
`actions/review.md`.

## Task

Execute the requested action: $ARGUMENTS

| Action | Description |
|--------|-------------|
| `load` | Load a feature spec or inline description into the working file |
| `start` | Branch from `main` and implement the goals |
| `test` | Test or verify what was built, against the acceptance criteria |
| `review` | **Delegated to Fable subagents** — goals, quality, and the blocking data integrity gate |
| `complete` | Test, build, commit, merge, push, reset |

See [actions/](actions/) for the detailed instructions for each.

If no action is given, show the current status from `docs/current-feature.md`
and list the available actions.

## This project is young

There is no pipeline and no site yet. Actions that call for a test suite, a
build, or an artifact check must **say what does not exist yet and move on** —
never invent a command, and never report a gate as passed when it was
skipped because the thing it guards has not been built.
