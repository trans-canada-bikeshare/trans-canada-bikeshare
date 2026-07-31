# Contributing

Thank you for looking. This is a data project before it is a code project: the
thing being maintained is a claim that every number on the site can be traced
to a pinned source file and computed the same way for every city. Most of what
follows exists to keep that claim true.

Two things are worth knowing before you spend time:

- **Raw trip data is never committed.** The pipeline reads a ~20 GB archive
  that lives outside git. Everything published is a small aggregate in
  `src/data/generated/`. A PR containing a raw trip file cannot be merged, and
  a merged one cannot be un-merged from anyone's clone.
- **Nothing is guessed silently.** An unknown column header, an unmapped
  membership label, a file whose date order its own values cannot prove — each
  of these stops the pipeline. Those aborts are the feature. If you are fixing
  one, map the new value explicitly; do not widen an `except`.

The full picture is in [`README.md`](README.md) (scope and principles),
[`docs/runbook.md`](docs/runbook.md) (how to rebuild and refresh),
[`docs/decisions.md`](docs/decisions.md) (the choices that bind the work) and
[`docs/data-dictionary.md`](docs/data-dictionary.md) (every published field).

## Run it from a clean clone

You do **not** need the 20 GB archive to work on this. The pipeline runs end to
end over a small synthetic fixture archive that is committed, in about two
seconds, with no network. That is what CI runs, and it is the reason the
reproducibility claim is checkable by someone who has never downloaded a byte.

Every command below was run, in this order, in a fresh clone on 2026-07-31:

```bash
git clone https://github.com/trans-canada-bikeshare/trans-canada-bikeshare.git
cd trans-canada-bikeshare

# Python 3.11 exactly. pipeline/requirements.lock holds CPython 3.11 (cp311)
# wheel hashes and nothing else, so another minor version has nothing to
# install; common.require_python asserts it again at import.
python3.11 -m venv .venv
.venv/bin/pip install --require-hashes -r pipeline/requirements.lock

# The whole pipeline over the fixture archive, then the real gates against it.
make check-fixture PYTHON=.venv/bin/python

.venv/bin/python -m pytest pipeline/tests

npm ci
npm test
```

What that gets you: `--require-hashes` means every distribution, direct and
transitive, must match a sha256 in the lock or the install aborts.
`check-fixture` runs extract → reference → clean → conform → model → publish →
quality report over the fixtures and then runs `check-manifest`,
`check-metrics`, `check-artifacts`, `check-report` and `check-reconciliation`
against the result — and verifies it touched nothing under `data-raw/`,
`data-warehouse/` or `src/data/generated/` rather than assuming it did not.

In a clone with no archive and no warehouse the warehouse-backed tests
**skip**, and say so. A skip is not a pass; if you are changing pipeline
behaviour, say in the PR which suites actually ran.

## The gates

```bash
make check          # manifest, metrics, artifacts, report, reconciliation,
                    #   data dictionary. Everything but the dictionary needs
                    #   the full archive, so this is a maintainer gate.
make check-fixture  # the whole pipeline over the synthetic fixtures (~2s)
.venv/bin/python -m pytest pipeline/tests
npm test && npm run typecheck && npm run build
```

Notes that save time:

- `make check` needs the ~20 GB archive, so it is a maintainer gate. CI runs
  `pytest` and `check-fixture`, which is everything a clean runner can prove.
- A gate that cannot fail is worse than an absent one. There is no
  `continue-on-error` and no `|| true` anywhere in `.github/`, and no
  Makefile target falls back to printing when its script is missing —
  `pipeline/tests/test_gate_targets.py` asserts both.
- `npm run build` carries its own assertion that MapLibre's tile-parsing worker
  reached `dist/assets`. It is a gate, not a smoke test: spec 021 shipped three
  maps that drew zero dots with every other check green.
- Changing an artifact's shape means changing its schema in
  `pipeline/schemas/` in the same commit, and regenerating the dictionary with
  `python pipeline/generate_data_dictionary.py`. Both are checked.

## Two merge paths, and why

**The maintainer's path is a local merge.** Features run through the
`/feature` skill in `.claude/skills/feature/` — `load → start → test → review →
complete` — which branches from `main`, implements one spec from
`docs/features/NNN-name.md`, runs the gates above **against the real archive**,
delegates review to a different model, and merges locally before pushing
`main`. That path is stronger than CI, not weaker: CI can only run the fixture
pipeline, whereas `/feature complete` refuses to merge while review is
unstamped, aborts on a failing suite or build, and — whenever the change could
have touched a published artifact — byte-compares the committed artifacts
against a fresh publish run over the real 135.6M-trip archive. Review is never
self-review, for reasons recorded in `docs/decisions.md` (2026-07-29): a
self-review once passed work an independent pass then found to contain three
separate data losses.

**Everyone else's path is a pull request.** Branch, push, open a PR, and CI
must be green before it merges. Branch protection on `main` enforces this and
exempts administrators (`enforce_admins: false`), which is what lets the
local-merge path above continue to work. The exemption is deliberate and it is
stated here rather than left to be discovered: the maintainer's merges are
gated by more than CI, and disabling the bypass would replace a strong gate
with a weaker one.

If you would rather the maintainer's changes also went through a PR, say so in
an issue — it is a trade-off (full-archive gates and independent review, vs.
the visible history a PR leaves), not a principle.

## Opening a PR

- One concern per PR. A data fix and a design change in one branch cannot be
  reviewed, because the evidence for each is a different kind of thing.
- Fill in the template. It asks which gates you ran and which you skipped;
  "skipped, no archive" is a fine answer and a false "passed" is not.
- If your change moves a published number, say which number, by how much, and
  show the query. A figure in prose needs a query, not a memory — three false
  figures shipped in spec 022 exactly that way.
- Commits describe what changed and why. The why is the part that survives.

## Reporting a data problem

If a number on the site looks wrong, that is the most valuable issue you can
file. Use the **Data quality report** template: it asks for the system, the
period, the number on the site, the number you computed and the query you
computed it with. All five, because a disagreement between two numbers is only
actionable when both can be re-derived.

Security issues go through GitHub's private vulnerability reporting — see
[`SECURITY.md`](SECURITY.md). Conduct concerns go to the issue tracker or to
the maintainer via [adnanreza.com](https://adnanreza.com), per
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Licence

Code is MIT. Contributions are accepted under the same licence. Published data
artifacts remain governed by each source system's terms, recorded in
[`DATA-LICENSES.md`](DATA-LICENSES.md) — which is the authority, and which no
other file in this repository restates.
