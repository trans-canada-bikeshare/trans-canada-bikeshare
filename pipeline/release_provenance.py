"""The provenance block that ships with a release.

A tagged release of this project is a claim about bytes: *these* artifacts,
computed by *this* commit, with *this* toolchain, over *these* data windows.
The tag alone carries none of that — it names a commit, and the artifacts are
JSON files a reader has no independent way to check. So the release body
carries the block this module prints, and every line of it is read from a file
in the repository rather than typed:

    commit          the argument, or `git rev-parse HEAD`
    artifacts       sha256 and byte size of every file in src/data/generated/
    Python, DuckDB  pipeline/requirements.lock
    Node            .github/workflows/ci.yml
    data windows    src/data/generated/meta.json

Nothing here is recalled and nothing is passed in as prose. The one figure a
release note would otherwise be written from memory — how many trips, over what
window, per system — is the artifact's own.

Usage:

    python pipeline/release_provenance.py v1.0.0 <sha>   # the block
    python pipeline/release_provenance.py --check        # assert it renders

`--check` is the gate: it renders the block and refuses if any source is
missing, unreadable or disagrees with another — an artifact with no schema, a
lock whose Python does not match `common.PYTHON_REQUIRES`, a workflow with no
Node version. A release body assembled by hand at the moment of tagging is
exactly when nobody notices that one of those went missing.

Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import artifact_schemas
import common

LOCK = common.PIPELINE_DIR / "requirements.lock"
CI_WORKFLOW = common.REPO_ROOT / ".github" / "workflows" / "ci.yml"
GENERATED = common.REPO_ROOT / "src" / "data" / "generated"

REPO_URL = "https://github.com/trans-canada-bikeshare/trans-canada-bikeshare"


class ProvenanceUnavailable(Exception):
    """A source the block is read from is missing or says something else."""


# ---------------------------------------------------------------------------
# The sources
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    if not path.exists():
        raise ProvenanceUnavailable(f"{path} does not exist")
    return path.read_text(encoding="utf-8")


def git_sha(sha: str | None = None) -> str:
    """The commit the release names. Given, or resolved from the working tree."""
    if sha:
        if not re.fullmatch(r"[0-9a-f]{7,40}", sha):
            raise ProvenanceUnavailable(
                f"{sha!r} is not a git object name. Pass the full commit sha "
                "the tag points at.")
        return sha
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"],
                             cwd=common.REPO_ROOT, capture_output=True,
                             text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ProvenanceUnavailable(
            "no commit given and `git rev-parse HEAD` failed") from exc
    return out.stdout.strip()


def artifact_hashes() -> list[tuple[str, str, int]]:
    """`(name, sha256, bytes)` for every published artifact, sorted by name.

    The set is checked against the schema set on the way past: an artifact with
    no contract, or a contract with no artifact, is a refusal here too. A
    provenance block is a statement about a complete set of files, and a block
    that quietly listed fourteen of fifteen would be worse than none.
    """
    if not GENERATED.is_dir():
        raise ProvenanceUnavailable(f"{GENERATED} does not exist")
    files = sorted(GENERATED.glob("*.json"))
    if not files:
        raise ProvenanceUnavailable(f"no artifacts in {GENERATED}")

    have = {p.stem for p in files}
    want = set(artifact_schemas.declared())
    if have != want:
        missing = sorted(have - want)
        orphan = sorted(want - have)
        raise ProvenanceUnavailable(
            "the published artifacts and the schemas disagree"
            + (f"; no schema for {missing}" if missing else "")
            + (f"; schema with no artifact for {orphan}" if orphan else ""))

    out: list[tuple[str, str, int]] = []
    for path in files:
        data = path.read_bytes()
        out.append((path.name, hashlib.sha256(data).hexdigest(), len(data)))
    return out


def python_version() -> str:
    """The interpreter the lock is built for, read off the lock's own wheels."""
    tags = sorted(set(re.findall(r"-cp(\d)(\d+)-", _read(LOCK))))
    if not tags:
        raise ProvenanceUnavailable(
            f"{LOCK} names no CPython wheel, so the Python version it pins "
            "cannot be read from it")
    if len(tags) > 1:
        found = ", ".join(f"{a}.{b}" for a, b in tags)
        raise ProvenanceUnavailable(
            f"{LOCK} carries wheels for more than one Python: {found}")
    major, minor = tags[0]
    version = f"{major}.{minor}"
    stated = ".".join(str(n) for n in common.PYTHON_REQUIRES)
    if version != stated:
        raise ProvenanceUnavailable(
            f"{LOCK} holds cp{major}{minor} wheels but common.PYTHON_REQUIRES "
            f"says {stated}. The lock and the code disagree about the "
            "interpreter this pipeline runs on.")
    return version


def locked_version(package: str) -> str:
    """A package's pinned version, from the lock and nowhere else."""
    match = re.search(rf"^{re.escape(package)}==([^\s\\]+)",
                      _read(LOCK), re.MULTILINE | re.IGNORECASE)
    if not match:
        raise ProvenanceUnavailable(f"{package} is not pinned in {LOCK}")
    return match.group(1)


def node_version() -> str:
    """The Node major version CI installs, from the workflow."""
    match = re.search(r"node-version:\s*'?\"?([0-9.]+)", _read(CI_WORKFLOW))
    if not match:
        raise ProvenanceUnavailable(
            f"{CI_WORKFLOW} states no node-version, so the Node this site is "
            "built with cannot be read from it")
    return match.group(1)


def data_windows() -> list[dict]:
    """Each system's trips and window, from meta.json."""
    meta = json.loads(_read(GENERATED / "meta.json"))
    systems = meta.get("systems") or []
    if not systems:
        raise ProvenanceUnavailable("meta.json carries no systems")
    for entry in systems:
        for key in ("system_id", "city", "system", "trips",
                    "first_trip", "last_trip"):
            if key not in entry:
                raise ProvenanceUnavailable(
                    f"meta.json system entry is missing {key!r}")
    return sorted(systems, key=lambda s: s["system_id"])


# ---------------------------------------------------------------------------
# The block
# ---------------------------------------------------------------------------


def render(version: str, sha: str | None = None) -> str:
    commit = git_sha(sha)
    hashes = artifact_hashes()
    systems = data_windows()
    total = sum(int(s["trips"]) for s in systems)

    lines: list[str] = []
    w = lines.append

    w("## Provenance")
    w("")
    w(f"Everything below is read from the repository at this commit by")
    w("`pipeline/release_provenance.py`, not written by hand.")
    w("")
    w(f"- **Commit** [`{commit[:12]}`]({REPO_URL}/commit/{commit}) — `{commit}`")
    w(f"- **Tag** `{version}`")
    w(f"- **Python** {python_version()} "
      f"(`pipeline/requirements.lock`, hash-pinned, CPython-only)")
    w(f"- **DuckDB** {locked_version('duckdb')} — **numpy** "
      f"{locked_version('numpy')} — **jsonschema** "
      f"{locked_version('jsonschema')}")
    w(f"- **Node** {node_version()} (`.github/workflows/ci.yml`)")
    w("")
    w("### Data windows")
    w("")
    w("| System | Trips | First trip | Last trip |")
    w("| --- | ---: | --- | --- |")
    for entry in systems:
        w(f"| {entry['city']} — {entry['system']} (`{entry['system_id']}`) "
          f"| {int(entry['trips']):,} | {entry['first_trip']} "
          f"| {entry['last_trip']} |")
    w(f"| **Total** | **{total:,}** | | |")
    w("")
    w("Each window is the archive's own first and last trip for that system,")
    w("read from `src/data/generated/meta.json`. A system's window ending")
    w("earlier than another's is the source's publishing pace, not a gap in")
    w("this project.")
    w("")
    w("### Published artifacts")
    w("")
    w("sha256 of every file the site reads. Raw trip data is not published and")
    w("is not in this repository; these aggregates are the whole output.")
    w("")
    w("| Artifact | Bytes | sha256 |")
    w("| --- | ---: | --- |")
    for name, digest, size in hashes:
        w(f"| `{name}` | {size:,} | `{digest}` |")
    w("")
    w("Verify a clone against this table:")
    w("")
    w("```bash")
    w("shasum -a 256 src/data/generated/*.json")
    w("```")
    w("")
    w("### Licence")
    w("")
    w("Code is MIT (`LICENSE`). The artifacts above are analysis outputs")
    w("derived from each system's published open data and remain governed by")
    w("the source terms recorded in `DATA-LICENSES.md` — including ECCC's")
    w("redistribution restrictions, which bind anyone redistributing from")
    w("here. That file is the authority; this block does not restate it.")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("version", nargs="?", default="v1.0.0",
                    help="the tag this block describes (default v1.0.0)")
    ap.add_argument("sha", nargs="?", default=None,
                    help="the commit the tag points at; default `git rev-parse HEAD`")
    ap.add_argument("--out", type=Path, default=None,
                    help="write the block to a file instead of stdout")
    ap.add_argument("--check", action="store_true",
                    help="render the block and refuse if any source is "
                         "missing or inconsistent; print nothing but the verdict")
    args = ap.parse_args()

    try:
        block = render(args.version, args.sha)
    except (ProvenanceUnavailable, artifact_schemas.SchemaViolation,
            json.JSONDecodeError) as exc:
        print(f"the release provenance block cannot be built: {exc}",
              file=sys.stderr)
        return 1

    if args.check:
        artifacts = len(artifact_hashes())
        systems = len(data_windows())
        print(f"release provenance renders: {artifacts} artifact(s) hashed, "
              f"{systems} system window(s), Python {python_version()}, "
              f"DuckDB {locked_version('duckdb')}, Node {node_version()}")
        return 0

    if args.out:
        args.out.write_text(block, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(block, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
