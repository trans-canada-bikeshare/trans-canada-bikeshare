"""Enforce the metric registry against the artifacts that actually shipped.

`pipeline/mappings/metric_support.json` says of itself that publishing a
cross-city series for a metric not marked supported in every system it contains
is "an ERROR, checked by `make check-metrics` — not a matter of anyone
remembering". Until this file existed that was false: `make check-metrics` was
a stub that printed a message and exited 0, so `make check` reported success
without ever running it. The only enforcement was `guard()` inside
`publish.py`, which fires at publish time and only for the metrics whose author
remembered to call it.

Spec 021 is why that distinction matters. It published `stations.json` and
`stations_meta.json` — a per-system series across all three cities — and called
`guard()` for neither. Every gate passed. A checker that validated only the
artifacts it already knew about would have been just as silent, so the central
rule here is the opposite one:

    **Every artifact carrying system-keyed data must be declared, or this
    fails.** Adding a new one is a decision, not an omission.

This reads `src/data/generated/` as committed. It does not re-run the pipeline
and does not need the warehouse — it checks what the site would actually serve.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import common

REGISTRY = common.MAPPINGS_DIR / "metric_support.json"
GENERATED = common.GENERATED_DIR

# Which registry metric governs which artifact. An artifact whose rows are
# per-system is a cross-city series and the registry governs it.
ARTIFACT_METRIC: dict[str, str] = {
    "trips_monthly": "trips",
    "seasonality": "seasonality",
    "stations_yearly": "active_stations",
    "stations": "active_stations",
    "stations_meta": "active_stations",
    "ebike_share": "ebike_share",
    "duration": "duration",
    # Declared 2026-07-29, after this gate refused spec 022's new artifact on
    # its first publish run — which is the behaviour it was written for.
    "flows": "station_flows",
    # Declared 2026-07-30, after the gate refused it too. Montreal appears
    # here under `partial_until`, not as a supported system.
    "membership": "membership_mix",
    # Spec 024. `operational_signals` was one registry entry covering two
    # metrics with different support: the trip-only signals every system can
    # carry, and dwell, which needs a bike identifier Montreal has never
    # published. One key could only be as narrow as its narrowest signal, so
    # the split is what lets Montreal into the comparable core.
    "rebalancing": "rebalancing_pressure",
    "dwell": "bike_dwell",
}

# Artifacts that carry system ids without being a comparative metric. Each
# needs a reason, because "it is not really a metric" is exactly the argument
# that would let an ungoverned series through.
EXEMPT: dict[str, str] = {
    "meta": (
        "Coverage and provenance per system — trip counts, date span, licence. "
        "Describes what was ingested, not a metric computed across cities."
    ),
    "incomplete_months": (
        "Periods excluded from every chart. A statement about what is NOT "
        "published, so registry support cannot apply to it."
    ),
    "exclusions": (
        "Row-accounting for dropped and flagged rows. Quality reporting, "
        "required to cover every system precisely because it is not a metric."
    ),
}

# Keys under which a system id appears. `system_id` is the normal form;
# `s` is the compact key used by stations.json, which is the largest artifact
# the site ships and is keyed tersely on purpose.
SYSTEM_KEYS = {"system_id", "s"}


class MetricGateFailure(Exception):
    """An artifact violates the registry, or was never declared against it."""


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def supported_systems(registry: dict, metric: str) -> set[str]:
    entry = registry["metrics"][metric]
    return {k for k, v in entry["systems"].items() if v.get("supported")}


def partial_systems(registry: dict, metric: str) -> set[str]:
    """Systems publishing a metric for only part of their range.

    The registry has carried `partial_until` since spec 009 and nothing read
    it. Montreal's membership field exists for 2014-2021 and vanishes at the
    2022 format break: publishing it as a supported column would imply a
    comparison that ends five years before the others, and refusing it
    entirely would hide 35 million labelled trips behind a "not published"
    that is simply false.

    A partial system may appear in the artifact. It is reported separately
    from a supported one, because the distinction is the whole point.
    """
    entry = registry["metrics"][metric]
    if entry.get("comparable"):
        # A partial system may never enter a comparable metric — see the same
        # rule in publish.py. Without it, `partial_until` on any system under
        # `trips` would have opened a comparable series to a fragment.
        return set()
    return {k for k, v in entry["systems"].items()
            if not v.get("supported") and v.get("partial_until")}


def systems_in(node: object) -> set[str]:
    """Every system id anywhere in a parsed artifact.

    Walks the whole structure rather than assuming a shape, so an artifact
    that nests its series (`{"series": [...]}`) is covered without this file
    having to know which ones do.
    """
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key in SYSTEM_KEYS and isinstance(value, str):
                found.add(value)
            else:
                found |= systems_in(value)
    elif isinstance(node, list):
        for item in node:
            found |= systems_in(item)
    return found


def check(generated: Path | None = None, verbose: bool = True) -> list[str]:
    """Returns a list of failures. Empty means the gate passes."""
    generated = generated or GENERATED
    registry = load_registry()
    failures: list[str] = []
    known = set(common.SYSTEMS)

    present = sorted(p.stem for p in generated.glob("*.json"))
    if not present:
        raise MetricGateFailure(
            f"no artifacts in {generated} — run pipeline/publish.py first. "
            "An empty directory is not a pass."
        )

    for name in present:
        declared = name in ARTIFACT_METRIC
        exempt = name in EXEMPT
        payload = json.loads((generated / f"{name}.json").read_text(encoding="utf-8"))
        systems = systems_in(payload)

        if not declared and not exempt:
            failures.append(
                f"{name}.json is not declared in ARTIFACT_METRIC and not "
                f"exempt. It carries {sorted(systems) or 'no'} system ids. "
                "Declare which metric governs it, or add it to EXEMPT with a "
                "reason. This is the check that spec 021 needed and did not have."
            )
            continue

        if declared and exempt:
            failures.append(
                f"{name}.json is both declared and exempt — one or the other."
            )
            continue

        unknown = systems - known
        if unknown:
            failures.append(
                f"{name}.json contains unknown system id(s) {sorted(unknown)}; "
                f"known: {sorted(known)}"
            )

        if exempt:
            if verbose:
                print(f"  {name:<20} exempt — {EXEMPT[name].split('.')[0]}.")
            continue

        metric = ARTIFACT_METRIC[name]
        if metric not in registry["metrics"]:
            failures.append(
                f"{name}.json is declared against metric '{metric}', which the "
                "registry does not define."
            )
            continue

        allowed = supported_systems(registry, metric)
        partial = partial_systems(registry, metric)
        offenders = sorted((systems & known) - allowed - partial)

        # A partial system may appear in the artifact but never inside its
        # `series` key, which is the comparable pair. The audit moved
        # Montreal's rows from `partial` into `series` and the gate passed,
        # because systems_in() walks the whole document without seeing keys.
        # This is the check that closes that.
        if partial and isinstance(payload, dict) and "series" in payload:
            in_series = systems_in(payload["series"]) & partial
            if in_series:
                failures.append(
                    f"{name}.json carries partial system(s) "
                    f"{sorted(in_series)} inside its `series` key — the "
                    "comparable pair. Partial systems belong under `partial`."
                )
        if offenders:
            reasons = "; ".join(
                f"{s}: "
                + registry["metrics"][metric]["systems"]
                .get(s, {})
                .get("reason", "not marked supported")
                for s in offenders
            )
            failures.append(
                f"{name}.json publishes metric '{metric}' for unsupported "
                f"system(s) {offenders}. {reasons}"
            )
        elif verbose:
            comparable = registry["metrics"][metric].get("comparable")
            tag = "" if comparable else "  [not comparable — per-city only]"
            shown_partial = sorted((systems & known) & partial)
            if shown_partial:
                until = ", ".join(
                    f"{s} to {registry['metrics'][metric]['systems'][s]['partial_until']}"
                    for s in shown_partial
                )
                tag += f"  [partial: {until}]"
            print(
                f"  {name:<20} {metric:<16} "
                f"{len(systems & known & allowed)}/{len(allowed)} supported systems{tag}"
            )

    # A metric the registry defines but nothing publishes is not a failure —
    # specs 022-024 are unwritten. Report it so the gap stays visible.
    if verbose:
        governed = set(ARTIFACT_METRIC.values())
        unpublished = sorted(set(registry["metrics"]) - governed)
        if unpublished:
            print(f"\n  registry metrics not yet published: {', '.join(unpublished)}")

    return failures


def main() -> int:
    print(f"check-metrics: {GENERATED.relative_to(common.REPO_ROOT)}")
    try:
        failures = check()
    except MetricGateFailure as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr)
        return 1

    if failures:
        print(f"\nFAIL: {len(failures)} violation(s)\n", file=sys.stderr)
        for f in failures:
            print(f"  - {f}\n", file=sys.stderr)
        return 1

    print("\nall published artifacts are governed by the registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
