# Start Action

1. Read `docs/current-feature.md` — the Goals section must be populated. If
   it is empty, error: "Run `/feature load` first".
2. Read `docs/decisions.md` for the constraints that bind every feature.
3. Set Status to `In Progress` and stamp `- [x] start — YYYY-MM-DD` in
   `## Lifecycle`.
4. Branch from an up-to-date `main`:
   ```bash
   git checkout main && git pull --ff-only
   git checkout -b feature/NNN-slug
   ```
   Derive the branch name from the H1 (e.g. `feature/001-source-column-audit`).
   One feature per branch — always.
5. List the goals, then implement them one at a time, in order.
6. Hold these while you build. They are the project's promises, and every one
   of them is cheaper to honour now than to retrofit at review:
   - **Every source file gets a manifest entry with a checksum**, in the same
     commit that starts using it. A number nobody can trace back to a pinned
     file is the failure this project cannot recover from.
   - **Nothing is guessed silently.** An unknown header, an unmapped code, an
     unexpected value — the pipeline stops. No bare `except`, no silent
     `fillna`, no coalesce-to-zero standing in for a missing field.
   - **Every row dropped or flagged is counted**, by reason, into the quality
     report.
   - **A metric is defined identically for every tier-1 city** — same units,
     same trip filter, same window, same null handling — or it is visibly
     labelled as not comparable. "Measured the same way" is the product.
   - **Dockless stays separate.** Calgary and Edmonton never appear as a
     like-for-like column beside the docked systems.
   - **Copy derives from the data window.** No hardcoded counts, dates, or
     "latest month" strings.
   - **Raw trip data never enters git.** Check `.gitignore` covers any new
     download path before the first run writes to it.
7. After each goal, run whatever fast check the repo has — typecheck, lint,
   unit tests. If the repo does not have one yet, say so rather than
   implying a check ran.
8. Keep scratch work out of the tree, or in a path that is already ignored.
   Exploratory notebooks, sample CSVs, and screenshots are the things that
   get committed by accident at complete.
