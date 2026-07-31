"""Policy assertions over `.github/` — the properties, not the formatting.

There is no YAML parser in `pipeline/requirements.lock` and this is not a
reason to add one: every assertion below is about a line of text that must or
must not appear, and a parse would not make any of them stronger. GitHub itself
rejects a workflow it cannot parse, and both files here are parsed as part of
spec 031's verification with an external parser; what a parser cannot tell you
is whether an action is pinned to a tag someone can repoint.

Comments are stripped before the forbidden-token checks, deliberately. The CI
workflow's own header explains why there is no `continue-on-error` in it, and a
naive grep for that string finds the explanation and fails — which would teach
whoever met the failure to delete the explanation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

GITHUB = Path(__file__).resolve().parents[2] / ".github"
WORKFLOWS = sorted((GITHUB / "workflows").glob("*.yml"))

# `uses: owner/repo@<ref>`, with whatever trails it.
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)\s*(#.*)?$")
SHA_PINNED = re.compile(r"^[^@]+@[0-9a-f]{40}$")
VERSION_COMMENT = re.compile(r"#\s*v\d+(\.\d+)*")


def strip_comments(text: str) -> str:
    """Whole-line comments removed; nothing else touched."""
    return "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("#"))


def jobs(text: str) -> dict[str, str]:
    """Job name -> its block, by indentation. No parser, and none needed."""
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line == "jobs:")
    except StopIteration:  # pragma: no cover - guarded by a test below
        return {}
    found: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[start + 1:]:
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            current = match.group(1)
            found[current] = []
        elif current is not None:
            if line and not line.startswith("  "):
                break
            found[current].append(line)
    return {name: "\n".join(body) for name, body in found.items()}


def test_there_are_workflows_to_check():
    assert WORKFLOWS, "no workflows found; this suite would pass vacuously"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_sha_with_its_version_beside_it(path):
    """A tag is a pointer its owner can move; a sha is the code reviewed."""
    seen = 0
    for line in strip_comments(path.read_text(encoding="utf-8")).splitlines():
        match = USES.match(line)
        if not match:
            continue
        seen += 1
        ref, comment = match.group(1), match.group(2) or ""
        assert SHA_PINNED.match(ref), (
            f"{path.name}: `uses: {ref}` is not pinned to a 40-character "
            "commit sha")
        assert VERSION_COMMENT.search(comment), (
            f"{path.name}: `uses: {ref}` carries no `# vX.Y.Z` comment, so "
            "nobody can tell which release the sha is without resolving it")
    assert seen, f"{path.name} uses no actions; the check would be vacuous"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_soft_failures(path):
    body = strip_comments(path.read_text(encoding="utf-8"))
    for token in ("continue-on-error", "|| true", "|| :", "set +e"):
        assert token not in body, (
            f"{path.name} contains {token!r}. A gate that cannot fail is the "
            "thing this repository's Makefile header exists to prevent.")


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_checkouts_do_not_persist_credentials(path):
    # Comments stripped first: both workflows explain the setting in prose,
    # and counting those explanations would make the check pass on a workflow
    # that merely talks about the flag.
    text = strip_comments(path.read_text(encoding="utf-8"))
    checkouts = len(re.findall(r"uses:\s*actions/checkout@", text))
    persists = len(re.findall(r"persist-credentials:\s*false", text))
    assert persists == checkouts, (
        f"{path.name}: {checkouts} checkout(s), {persists} with "
        "`persist-credentials: false`. The default writes the job's token into "
        ".git/config, where every later step can read it.")


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_job_declares_a_timeout(path):
    found = jobs(path.read_text(encoding="utf-8"))
    assert found, f"{path.name}: no jobs found"
    for name, body in found.items():
        assert "timeout-minutes:" in body, (
            f"{path.name}: job `{name}` has no timeout-minutes. A hung job "
            "holds a runner until GitHub's six-hour default kills it.")


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_workflow_declares_permissions(path):
    body = strip_comments(path.read_text(encoding="utf-8"))
    assert re.search(r"^permissions:", body, re.MULTILINE), (
        f"{path.name} declares no top-level `permissions:` block, so it runs "
        "with whatever the repository default is.")


def test_the_reminder_workflow_is_least_privilege():
    path = GITHUB / "workflows" / "monthly-refresh-reminder.yml"
    body = strip_comments(path.read_text(encoding="utf-8"))
    block = re.search(r"^permissions:\n((?:  .*\n)+)", body, re.MULTILINE)
    assert block, "the reminder workflow declares no permissions block"
    granted = dict(re.findall(r"\s*([a-z-]+):\s*(\S+)", block.group(1)))
    assert granted == {"contents": "read", "issues": "write"}, (
        f"the reminder workflow grants {granted}. It opens an issue and reads "
        "a template; anything else is more than it needs.")


def test_the_reminder_cron_is_monthly():
    path = GITHUB / "workflows" / "monthly-refresh-reminder.yml"
    crons = re.findall(r"cron:\s*'([^']+)'",
                       strip_comments(path.read_text(encoding="utf-8")))
    assert crons == ["0 14 1 * *"], (
        f"the reminder cron is {crons}; the runbook documents "
        "`0 14 1 * *` (14:00 UTC on the 1st).")


def test_dependabot_covers_every_ecosystem_this_repository_has():
    path = GITHUB / "dependabot.yml"
    text = strip_comments(path.read_text(encoding="utf-8"))
    ecosystems = set(re.findall(r"package-ecosystem:\s*(\S+)", text))
    assert ecosystems == {"npm", "pip", "github-actions"}, ecosystems
    assert text.count("interval: monthly") == 3
    assert text.count("groups:") == 3, "each ecosystem updates as one PR"


def test_issue_templates_exist_and_blank_issues_are_disabled():
    directory = GITHUB / "ISSUE_TEMPLATE"
    names = {p.name for p in directory.glob("*.yml")}
    assert {"bug.yml", "data-quality.yml", "config.yml"} <= names, names
    config = (directory / "config.yml").read_text(encoding="utf-8")
    assert "blank_issues_enabled: false" in config


def test_the_data_quality_template_asks_for_provenance():
    """The five fields that make a disagreement about a number actionable."""
    text = (GITHUB / "ISSUE_TEMPLATE" / "data-quality.yml").read_text(
        encoding="utf-8")
    for field in ("id: system", "id: period", "id: published", "id: computed",
                  "id: query"):
        assert field in text, f"the data-quality template has no {field}"
    assert text.count("required: true") >= 5
