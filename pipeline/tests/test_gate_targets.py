"""A gate whose script has vanished must fail the target, not print about it.

Every `check-*` target in the Makefile was written in spec 002 as a stub: `if
[ -f pipeline/<script>.py ]; then run it; else echo "stub — spec NNN makes this
real"; fi`, exiting 0 either way. That shape was correct for exactly as long as
the script did not exist. `check-metrics` kept it for a month after its script
landed — printing "stub" and exiting 0 while `metric_support.json` claimed the
registry was enforced — and spec 009b removed it there. `check-artifacts` and
`check-manifest` still carried it until spec 031.

The failure the shape produces is the one this repository fears most: a gate
that cannot fail, believed by everything downstream. A renamed script, a moved
file, a typo in a path — `make check` would report success over a gate that
never ran.

Two tests, deliberately of two different kinds:

  * a behavioural one, which copies the Makefile somewhere the scripts do not
    exist and asserts every gate target FAILS there. That is the property, and
    it holds however the recipe is written;
  * a textual one, which asserts no recipe contains a fallback branch, because
    a `|| echo` re-added to a target whose script still exists would pass the
    first test and reintroduce exactly the defect.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

MAKEFILE = Path(__file__).resolve().parents[2] / "Makefile"

# Every `check-*` target, read from the file rather than listed here — a target
# added without a test is the gap this test exists to close.
TARGET = re.compile(r"^(check-[a-z-]+):", re.MULTILINE)


def targets() -> list[str]:
    found = TARGET.findall(MAKEFILE.read_text(encoding="utf-8"))
    assert found, "no check-* targets found in the Makefile"
    return sorted(set(found))


def recipes() -> dict[str, list[str]]:
    """Target -> its recipe lines (the tab-indented ones under it)."""
    out: dict[str, list[str]] = {}
    current: str | None = None
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        match = TARGET.match(line)
        if match:
            current = match.group(1)
            out[current] = []
        elif current and line.startswith("\t"):
            out[current].append(line)
        elif line and not line.startswith((" ", "\t")):
            current = None
    return out


def test_every_gate_target_fails_when_its_script_is_missing(tmp_path):
    """The Makefile alone, in a tree with no `pipeline/`: every gate must fail."""
    if shutil.which("make") is None:  # pragma: no cover - environment
        pytest.skip("make is not installed")
    shutil.copy(MAKEFILE, tmp_path / "Makefile")

    for target in targets():
        result = subprocess.run(
            ["make", target, f"PYTHON={sys.executable}"],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            f"`make {target}` exited 0 in a tree where its script does not "
            f"exist. A gate that cannot fail is worse than an absent one.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def test_no_gate_recipe_carries_a_fallback():
    """No `if [ -f ]`, no `else`, no `||`, no stub message."""
    forbidden = ("if [", "else", "|| ", "stub", "|| true")
    for target, lines in recipes().items():
        for line in lines:
            body = line.strip()
            for token in forbidden:
                assert token not in body, (
                    f"`{target}` recipe contains {token!r}:\n    {body}\n"
                    "A gate invokes its script unconditionally; a missing "
                    "script is a failed target. See the Makefile header."
                )


def test_check_runs_every_gate_target():
    """`make check` must aggregate them all — a gate nothing calls is decoration."""
    text = MAKEFILE.read_text(encoding="utf-8")
    aggregate = re.search(r"^check:(.*?)(?=\n\S|\n\n)", text,
                          re.MULTILINE | re.DOTALL)
    assert aggregate, "no `check:` aggregate target in the Makefile"
    called = set(aggregate.group(1).replace("\\\n", " ").split())

    # `check-fixture` is deliberately outside `make check`: it is the offline
    # fixture pipeline CI runs, and `make check` is the full-archive battery.
    expected = set(targets()) - {"check-fixture", "check"}
    missing = sorted(expected - called)
    assert not missing, (
        f"gate target(s) {missing} exist and `make check` does not run them"
    )
