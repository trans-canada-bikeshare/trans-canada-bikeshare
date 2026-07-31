A new month has started, so each system may have published a new period. This
issue was opened automatically by
[`.github/workflows/monthly-refresh-reminder.yml`](https://github.com/trans-canada-bikeshare/trans-canada-bikeshare/blob/main/.github/workflows/monthly-refresh-reminder.yml).
It is a reminder, not a result: nothing has been checked, downloaded or
rebuilt.

The refresh runs on the machine that holds the ~20 GB archive. The steps, in
order, are
**[docs/runbook.md → "Monthly refresh"](https://github.com/trans-canada-bikeshare/trans-canada-bikeshare/blob/main/docs/runbook.md#monthly-refresh)**
— follow that section, not this summary:

- [ ] `discover.py` — new periods appear automatically; a **changed URL for an
      existing period is reported and not applied**. Look at it before passing
      `--accept-changes`.
- [ ] `download.py` — idempotent; only new files are fetched.
- [ ] `census.py` — **before ETL.** A header layout the era map does not cover
      aborts extraction, and that abort is the feature.
- [ ] `etl.py --stage all`, then `publish.py`, then `quality_report.py`.
- [ ] `make check` and both suites
      (`pytest pipeline/tests`; `npm test && npm run typecheck && npm run build`).
- [ ] Commit the regenerated artifacts, manifests and quality report together.
      The site updates by exactly this; there is no other copy to edit.
- [ ] Deploy per the runbook's "Deploy" section.

Close this issue when the refresh is done, or when the sources turn out to have
published nothing — in which case say so here, because "no new data" is a
finding and an unanswered reminder is not.
