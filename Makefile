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
# not mark supported for every system in it. This is the executable form of the
# like-for-like promise — spec 001 already found two metrics it must catch.
check-metrics:
	@if [ -f pipeline/check_metrics.py ]; then \
		$(PYTHON) pipeline/check_metrics.py; \
	else \
		echo "check-metrics: stub — spec 009 makes this real."; \
		echo "  will enforce pipeline/mappings/metric_support.json across published series"; \
	fi

check: check-manifest check-metrics check-artifacts

.PHONY: check check-artifacts check-manifest check-metrics
