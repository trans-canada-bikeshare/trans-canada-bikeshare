# Review Action

## Review is delegated. You do not review your own work.

**Launch the review as a subagent on a different model — `model: "fable"`.**
Use the Agent tool, `subagent_type: "general-purpose"`, one agent per dimension
the change touches (data/SQL, pipeline code, frontend/docs), run in parallel.

### If Fable is unavailable

Fall back, in this order — **never** to reviewing in the authoring context:

1. `model: "fable"` — preferred.
2. `model: "opus"` in a **separate subagent**. Most of what review catches comes
   from independence rather than diversity: a fresh context that did not write
   the code and is told nothing about what its author suspects. That is
   preserved here. What is lost is a second set of blind spots — an author and
   a reviewer on the same model may share systematic ones, and neither can
   observe that from the inside.
3. `model: "sonnet"` for smaller or lower-risk changes.

The fallback is about the model only. Every other rule below still binds:
separate agent, fresh context, no hints, empirical proof, author verifies
severity-1 findings, and a blocked reviewer is not a pass.

When the review ran on anything other than Fable, **say so in the completion
note**, so the level of assurance behind a merge is recoverable later.

This is not ceremony. On 2026-07-29 a self-review of this project passed work
that an independent Fable pass then found to contain **three separate data
losses** — 320,229 Toronto trips inside a nested zip, 217,569 in an unread
second worksheet, ~31,000 to silent encoding errors — plus **8.9M Montreal rows
on the wrong local day**, and four claims on the site its own data
contradicted. The gates written into this project fired exactly where their
author had anticipated failure, and were silent everywhere else. That is the
structural problem: the blind spot that produces a bug also shapes the review
of it. A different model makes the independence real rather than nominal.

**Rules for the delegation:**

- Do **not** tell the reviewer what you already fixed or suspect. If it
  independently re-surfaces something you believe fixed, that fix did not hold.
- Require **empirical proof**: a query whose output demonstrates the finding,
  not a reading of the code. Give the agent the warehouse path and note that
  read-only DuckDB queries are cheap.
- Require it to say plainly when something is **fine** — a review that only
  lists problems cannot be distinguished from one that missed the good parts.
- **Verify every severity-1 finding yourself before acting on it.** Reviewers
  are wrong sometimes, and a confident wrong finding costs more than none.
- A reviewer that reports **nothing** because it was blocked (a database lock,
  a missing dep) has **not** delivered a clean result. Resume it. Never present
  a stalled run as a pass.
- Reviewers work from a snapshot. If you fix something mid-review, expect it to
  be flagged anyway; say so rather than treating the reviewer as wrong.

Then apply your own judgement to what comes back, and carry out steps 1-7 below
against the findings.

---

1. Read `docs/current-feature.md` for the goals and the spec for full context.
2. Review every change on the branch: `git diff main` and
   `git diff main --stat`.
3. Check for:
   - ✅ Goals met — verified against the Acceptance Criteria, not asserted
   - ❌ Goals missing or partial
   - ⚠️ Bugs, quality problems, dead code
   - 🚫 Scope creep — code beyond the goals
   - ♿ Accessibility — keyboard reachable, focus visible, contrast AA, chart
     meaning available without relying on colour alone
   - 🧱 Build health — typecheck, lint, production build, no console errors
   - 📊 **The data integrity gate below. It is blocking.**

4. 📊 **Data integrity and comparability gate (BLOCKING).**

   A feature that fails any item below **does not ship**, even if every one
   of its own goals is met. This project's entire claim is that Canada's bike
   share systems are measured the same way from pinned, reproducible sources.
   A ranking regression can be recovered in months; a number on the site that
   nobody can trace, or a comparison that quietly is not one, costs the
   credibility the whole thing rests on.

   **First, derive which items apply** from the spec's Scope section — it
   already declares sources touched, cities touched, and whether published
   artifacts change. Then work the applicable items one at a time.

   Print the verdict as a table before the prose, so a skipped item cannot
   pass as a checked one:

   | Item | Verdict |
   |---|---|
   | Provenance pinned | pass / **FAIL** / n/a — no new source read |

   `n/a` **requires a reason naming what in Scope makes it inapplicable.**
   "Probably fine", "unchanged", and a silent omission are all fails. If
   Scope is missing or vague, the gate does not shrink — every item applies
   until the spec says otherwise.

   - **Provenance is pinned.** Every source file the feature reads has a
     manifest entry with a checksum and a stated licence. No number reaches
     an artifact without a traceable file behind it.
   - **Nothing is guessed silently.** Unknown headers, unmapped codes, and
     unexpected values stop the pipeline. Every schema-drift mapping is
     explicit and scoped to its era. Grep the diff for the quiet ones: bare
     `except`, `errors="coerce"`, `fillna(0)`, `COALESCE(x, 0)`, `.get(k, 0)`
     — each is either justified in a comment or a fail.
   - **Row accounting closes.** Rows in equals rows kept plus rows dropped by
     named reason, and the quality report says so. A drop rate that moved
     without an explanation is a fail even with green tests.
   - **Artifacts reproduce.** Committed artifacts byte-match a fresh pipeline
     run. If SQL, mappings, or source data changed and artifacts were not
     regenerated, the site would serve numbers no current code produces —
     fail.
   - **Like-for-like actually holds.** Any metric shown across cities is
     defined identically for each: same units, same trip filter, same time
     window, same null handling, same rounding. Where a city cannot support
     the metric, it is **absent or labelled** — never approximated into
     looking comparable. Read the SQL per city and confirm, do not trust that
     one function was called three times.
   - **The tier boundary is intact.** Calgary and Edmonton (dockless,
     anonymized locations, no stations) appear only in their own clearly
     labelled panel, never as a column beside the docked systems.
   - **Copy derives from the data.** No hardcoded counts, dates, city lists,
     or "latest month" strings. Prose may lag the data; it may never
     contradict it. Check the data-window text on every page the change
     touches.
   - **Encodings say what they mean.** Any new colour, size, thickness, or
     ordering encoding is explained where a first-time viewer will look —
     not only in the methodology page.
   - **Attribution ships with the data.** A new source is credited per its
     licence, in the manifest and on the site, per `LICENSE`.
   - **No raw data in the diff.** No trip-level file, no warehouse file, no
     large binary.

   **When in doubt, regenerate from scratch and diff the artifacts.** If the
   only diff is the intended one, it passes. If anything else moved, it
   fails until it is explained.

5. Confirm the feature did not weaken a decision in `docs/decisions.md`. If
   it should change one, that is a decisions entry, not a silent drift.

6. Final verdict: **ready to complete**, or **needs changes** with a specific
   list. A failed gate item is always a blocker — say which item, what was
   found, and what would fix it.

7. Stamp `## Lifecycle` in `docs/current-feature.md`:
   - verdict ready → `- [x] review — YYYY-MM-DD`
   - verdict needs changes → leave it unstamped. `/feature complete` is
     blocked until a later review passes, which is the point.
