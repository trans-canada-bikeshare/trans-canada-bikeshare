# Trans-Canada Bikeshare — quality gates.
#
# These exist so `/feature review` runs commands with exit codes instead of
# self-attesting against prose. Each target below is a stub until its spec
# lands; every stub says which spec makes it real and exits 0 so the workflow
# can call them from the first data spec onward.

PYTHON := .venv/bin/python

# Spec 011. Byte-compares committed artifacts against a fresh publish run.
# Exits non-zero and lists drifted files on any mismatch.
check-artifacts:
	@if [ -f pipeline/check_freshness.py ]; then \
		$(PYTHON) pipeline/check_freshness.py; \
	else \
		echo "check-artifacts: stub — spec 011 makes this real."; \
		echo "  will byte-compare src/data/generated/ against a fresh publish run"; \
	fi

# Spec 003. Verifies every manifest entry against the archive on disk:
# checksums, byte sizes, and gaps in the expected period run.
check-manifest:
	@if [ -f pipeline/inventory.py ]; then \
		$(PYTHON) pipeline/inventory.py; \
	else \
		echo "check-manifest: stub — specs 003/004 make this real."; \
		echo "  will verify pipeline/manifests/*.json against data-raw/"; \
	fi

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

check: check-manifest check-metrics check-artifacts check-report

.PHONY: check check-artifacts check-manifest check-metrics check-report
