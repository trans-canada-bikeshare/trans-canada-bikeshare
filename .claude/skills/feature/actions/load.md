# Load Action

1. Check $ARGUMENTS (after "load"):
   - **Looks like a spec reference** (a number like `001`, or a slug like
     `001-source-column-audit`): find it in `docs/features/`, matching on the
     `NNN` prefix if only the number was given. If several match, ask which.
   - **Multiple words**: treat as an inline feature description and derive
     goals from it. Say plainly that no spec file backs this, and offer to
     write one from `docs/features/000-template.md` if the work is more than
     a small change.
   - **Empty**: error — "load needs a spec number, a spec filename, or a
     feature description".

2. Read `docs/decisions.md` and `README.md` first. If the spec contradicts a
   logged decision or a stated principle, raise it now — before any code
   exists to argue for itself.

3. When loading a spec file, read it fully and extract:
   - **Acceptance Criteria** → the goals, verbatim. Do not paraphrase them
     into something looser or more achievable.
   - **Depends On** → warn if a dependency is not in the History of
     `docs/current-feature.md`.
   - **Scope** → which sources, which cities, and — the one that decides how
     heavy review and complete will be — **whether any published artifact
     changes**.
   - Any licence constraint attached to a source the spec introduces.

4. Update `docs/current-feature.md`:
   - H1 → `# Current Feature: NNN Name`
   - `## Goals` ← Acceptance Criteria as bullets
   - `## Notes` ← dependencies, sources and cities touched, licence
     constraints, whether published artifacts change
   - `## Status` → `Not Started`
   - `## Lifecycle` → reset all four boxes, then stamp
     `- [x] load — YYYY-MM-DD`. If a previous feature's stamps are still
     there, that feature never completed — say so before overwriting.

5. Confirm the spec is loaded and show the summary: name, goal count,
   sources and cities in scope, artifacts affected, and any dependency
   warning.
