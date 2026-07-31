# Trans-Canada Bikeshare — quality gates.
#
# These exist so `/feature review` runs commands with exit codes instead of
# self-attesting against prose. Every target runs its script directly: no
# `if [ -f ... ]`, no `||`, no fallback that prints and exits 0.
#
# They did not start that way. Each was written in spec 002 as a stub that
# announced which future spec would make it real, and `check-artifacts` and
# `check-manifest` still carried the `if [ -f script ]; then run; else echo
# "stub"; fi` shape long after the scripts existed — so a gate whose script was
# deleted, renamed or moved would have gone on printing a spec-002 message and
# exiting 0, under a `make check` that reports success. That is the exact
# failure `check-metrics` was caught in on 2026-07-29 (spec 009b): a gate that
# cannot fail, believed by everything downstream. Spec 031 removed the last two.
#
# The rule, for anything added here: a gate invokes its script unconditionally,
# and a missing script is a failed target.

PYTHON := .venv/bin/python

# Spec 011. Byte-compares committed artifacts against a fresh publish run.
# Exits non-zero and lists drifted files on any mismatch.
check-artifacts:
	$(PYTHON) pipeline/check_freshness.py

# Spec 003. Verifies every manifest entry against the archive on disk:
# checksums, byte sizes, and gaps in the expected period run.
check-manifest:
	$(PYTHON) pipeline/inventory.py

# Spec 009. Fails if a cross-city artifact publishes a metric the registry does
# not mark supported for every system in it, OR if an artifact carrying
# system-keyed data was never declared against a metric at all. The second case
# is the one spec 021 needed: it shipped stations.json across three cities
# having called guard() for neither of its artifacts, and every gate passed.
#
# This ran as a stub until 2026-07-29 — printing a message and exiting 0 while
# metric_support.json claimed it was enforced. No `|| true`, no conditional:
# a gate that cannot fail is the thing this target exists to prevent.
check-metrics:
	$(PYTHON) pipeline/check_metrics.py

# Spec 028. Regenerates docs/data-quality-report.md from the warehouse and fails
# on any difference from the committed copy, excluding only the generation
# timestamp. The report is the project's public row accounting and it sat
# outside every gate until this target existed — long enough to publish a 0.0%
# where the warehouse says 88.9%, and an encoding loss the pipeline had already
# stopped taking. Generation itself refuses on a non-zero funnel residual or a
# kept trip with no departure station, so this target is two gates in one.
check-report:
	$(PYTHON) pipeline/check_report.py

# Spec 029. The standing half of spec 028's per-file reconciliation. Extraction
# proves source records == rows landed once, against the bytes on disk that
# morning; this proves the audit is still true of the archive the manifests
# pin now, and recounts any period whose checksum has moved. Cheap by design —
# it reads files only where a pin changed, which is normally nowhere.
check-reconciliation:
	$(PYTHON) pipeline/check_reconciliation.py

# Spec 031. Regenerates docs/data-dictionary.md from the fifteen artifact
# schemas and the completeness declaration, and fails on any difference from the
# committed copy. The generated document carries no timestamp, deliberately, so
# the diff is total: every line of it is derived and every line is checked. It
# is the only gate here that needs neither the archive nor the warehouse.
check-dictionary:
	$(PYTHON) pipeline/generate_data_dictionary.py --check

# One line, deliberately: `pipeline/tests/test_reproducibility.py` reads this
# target as a single line to assert its own gate is inside it, and a backslash
# continuation would hide half the list from that check.
check: check-manifest check-metrics check-artifacts check-report check-reconciliation check-dictionary

# Spec 029. The whole pipeline end to end over a synthetic fixture archive:
# extract -> reference -> clean -> conform -> model -> publish -> quality
# report, then every gate above that a fixture tree can be asked meaningfully,
# then assertions about what came out. Two seconds, no network, and it cannot
# touch data-raw/, data-warehouse/ or src/data/generated/ — which it verifies
# rather than assumes.
#
# Every gate in `make check` but `check-dictionary` needs the ~20 GB archive,
# and this one needs nothing at all. It is therefore what CI runs, and it is the
# reason the reproducibility claim is testable by someone who has never
# downloaded a byte.
# See pipeline/tests/fixtures/README.md for what the fixtures cover.
check-fixture:
	$(PYTHON) pipeline/fixture_run.py

.PHONY: check check-artifacts check-dictionary check-fixture check-manifest \
        check-metrics check-report check-reconciliation
