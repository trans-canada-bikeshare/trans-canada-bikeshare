# Complete Action

0. **Lifecycle check.** Read `## Lifecycle` in `docs/current-feature.md`.
   If `review` is unstamped, **stop**:

   > 🚫 `review` has not passed for this feature. Run `/feature review` first.

   Do not offer to skip it, and do not run review inline as part of complete —
   a review whose findings land in the same breath as the merge is not a
   review. If `test` is unstamped, say so and ask whether that was deliberate
   (some specs have no testable surface) before continuing.

1. **Run the test suites.** If any fail, abort and report the failures.
2. **Typecheck, lint, and build.** If any error, abort and report.
3. **Reproducibility gate.** If the feature could have changed a published
   artifact, run the freshness check that byte-compares committed artifacts
   against a fresh pipeline run. Drift means abort — regenerate, re-review
   the diff, then come back. If nothing artifact-bearing changed, say you
   skipped it and why.
4. **Clean ephemeral artifacts** created while building, before staging
   anything: screenshots at the repo root, `.playwright-mcp/`,
   `playwright-report/`, `test-results/`, `__pycache__/`, scratch notebooks,
   sample CSVs, and one-off query outputs.
   **Keep** spec files, test files, and real committed assets.

5. 🚨 **Raw data and large file gate (BLOCKING — needs an explicit reply).**

   Run both checks over everything git could commit — staged, modified, and
   untracked. Anything `.gitignore` already covers is correctly invisible
   here; that is the point.

   ```bash
   # 1. anything over 1 MB
   git status --porcelain -uall | cut -c4- | while IFS= read -r f; do
     [ -f "$f" ] && du -k "$f"
   done | awk '$1 > 1024 { printf "%.1f MB\t%s\n", $1/1024, $2 }' | sort -rn

   # 2. raw-data paths and trip-data file types
   git status --porcelain -uall | cut -c4- \
     | grep -Ei '^(data-raw|data-warehouse)/|\.(csv|parquet|zip|db|duckdb)$'
   ```

   Both silent means clean — proceed. If either prints anything, STOP and
   surface it.

   > ⚠️ **LARGE / RAW FILE IN THE COMMIT PATH**
   > {list the files with sizes}
   >
   > A raw trip file committed to git is permanent — it stays in every future
   > clone whether or not it is deleted later, and it may breach the source
   > system's open data licence. Undoing it means rewriting the history of a
   > published repo.
   >
   > This is the one mistake in this project that `git revert` does not fix.
   >
   > Commit these anyway?
   > - **yes** → I stage them and note why in the commit message
   > - **no** → I leave them out and add the paths to `.gitignore`
   >
   > Reply with an explicit "yes" or "no".

   **Wait for the reply. Never assume yes.** If unclear, treat it as no.

6. **Stage explicit paths** — never `git add -A`. Eyeball `git status` first
   so nothing strays in. Commit with a message naming the spec:
   `feat: spec NNN — short description`.

7. **Merge into `main` locally** (no push yet) and delete the local feature
   branch. Use `--no-ff` and write the record into the **merge commit body** —
   this is where the detail lives now that History is one line:
   - what shipped and why
   - sources and cities touched; whether artifacts were regenerated
   - what was verified: test counts, freshness check, build, lint
   - anything deliberately deferred or out of scope
   - how to roll back

8. **Reset `docs/current-feature.md`:**
   - H1 back to `# Current Feature`
   - Status back to `_No feature in progress._`
   - Clear all four `## Lifecycle` stamps back to unchecked
   - Clear Goals and Notes, keeping the placeholder comments
   - Append **one line** to the end of History (oldest first):
     ```
     - 2026-07-28 `a1b2c3d` — spec 003: Toronto 2017-2024 trips into the
       warehouse; artifacts regenerated. `docs/features/003-toronto-etl.md`
     ```
     One line. Not a paragraph. The full story — what was verified, what was
     deferred, how to roll back — belongs in the **merge commit body**, where
     `git show` will find it and where it costs nothing to keep. This file is
     read into context every session; the sister project let these grow into
     500-word entries and reached 79 KB before it had to be split.

9. **Commit the reset:** `chore: reset current-feature.md after spec NNN`.

10. **Push `main` to `origin` once** — a single push carrying everything.

11. **Attribution gate.** If the feature added a source system or a new data
    file from an existing one, confirm before finishing that its licence and
    credit are live in both the manifest and the site, per `DATA-LICENSES.md`. If the
    site does not exist yet, confirm the manifest entry and note the site
    credit as owed.

12. **Do not delete the remote feature branch** unless the user explicitly
    asks. (House rule carried from the Vancouver project.)
