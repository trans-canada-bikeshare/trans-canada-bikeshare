"""Download what the manifests list, and pin what comes back.

Idempotent: a file already on disk whose SHA-256 matches its pin is skipped
without a request. A re-download whose content differs from an existing pin
FAILS and leaves the pin alone — that refusal is the whole point of the
manifest, and --accept-changes is the only way past it.

Nothing here trusts a URL's extension. Formats are read from magic bytes,
because all three publishers have shipped content that disagrees with its
filename.

Usage:
  python pipeline/download.py [--system SYSTEM] [--period PERIOD]
                              [--reference-only] [--accept-changes]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

import common

CHUNK = 1 << 20


class Drift(Exception):
    """Downloaded content does not match the manifest pin."""


def refine_archive_format(path: Path) -> str:
    """Both .xlsx and .zip start with PK. Tell them apart by looking inside."""
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
    except zipfile.BadZipFile:
        return "zip"
    return "xlsx" if any(n == "[Content_Types].xml" for n in names) else "zip"


def stream_to(url: str, dest: Path) -> tuple[str, int, str, Path, Path]:
    """Download to a .part file, returning (sha256, bytes, format, tmp, final)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    head = b""
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(
        url, stream=True, timeout=300, headers={"User-Agent": common.USER_AGENT}
    ) as response:
        response.raise_for_status()
        with tmp.open("wb") as handle:
            for chunk in response.iter_content(CHUNK):
                if not chunk:
                    continue
                if len(head) < 8192:
                    head += chunk[: 8192 - len(head)]
                digest.update(chunk)
                size += len(chunk)
                handle.write(chunk)

    content_format = common.detect_format(head)
    if content_format == "zip":
        content_format = refine_archive_format(tmp)
    if content_format in ("html", "unknown"):
        tmp.unlink(missing_ok=True)
        raise Drift(
            f"{url} returned {content_format!r}, not data — the link may have "
            "expired or now serves an interstitial page"
        )

    # Deliberately does NOT put the file in place. The caller verifies the pin
    # first and commits only on success — otherwise a refused download would
    # overwrite the last verified copy of bytes the source no longer serves,
    # destroying the archive at exactly the moment the refusal exists to
    # protect it.
    final = dest.with_suffix(common.extension_for(content_format))
    return digest.hexdigest(), size, content_format, tmp, final


def entry_is_satisfied(entry: dict, path: Path) -> bool:
    """True when the pin is recorded, the file is present, and it still hashes
    to the pin. This is what makes a re-run free."""
    if not entry.get("sha256"):
        return False
    if not path.exists():
        return False
    if entry.get("bytes") is not None and path.stat().st_size != entry["bytes"]:
        return False
    return common.sha256_file(path) == entry["sha256"]


def apply_result(
    entry: dict, sha: str, size: int, content_format: str | None, accept_changes: bool
) -> str:
    """Record a download into its manifest entry, or refuse on drift.

    Returns a short status word. Raises Drift when the pin disagrees and the
    operator has not explicitly accepted the change.
    """
    pinned = entry.get("sha256")
    if pinned and pinned != sha:
        # A `volatile` entry is one the source is still writing — ECCC's bulk
        # export for the CURRENT calendar year gains an observation every day,
        # so its checksum is guaranteed to move. Refusing it would make
        # --accept-changes a daily routine, and a flag used routinely stops
        # protecting the entries that actually matter. The pin still records
        # exactly what was used; it is just expected to advance.
        if entry.get("volatile"):
            status = "moved"
        elif not accept_changes:
            raise Drift(
                f"content changed: pinned {pinned[:12]}… but downloaded "
                f"{sha[:12]}… — re-run with --accept-changes to repin"
            )
        else:
            status = "repinned"
    else:
        status = "pinned" if not pinned else "verified"
    entry["sha256"] = sha
    entry["bytes"] = size
    if content_format is not None:
        entry["content_format"] = content_format
    entry["downloaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return status


def download_system(
    system_id: str,
    periods: list[str] | None,
    accept_changes: bool,
    reference_only: bool,
) -> int:
    manifest = common.load_manifest(system_id)
    sources = manifest.get("sources", {})
    if not sources and not manifest.get("reference"):
        print(f"  nothing to download; run discover.py --system {system_id} first")
        return 0

    failures = 0
    targets = [] if reference_only else sorted(periods or sources)
    for period in targets:
        entry = sources.get(period)
        if entry is None:
            print(f"  {period}: not in the manifest", file=sys.stderr)
            failures += 1
            continue
        path = common.local_path(system_id, period, entry.get("content_format"))
        if entry_is_satisfied(entry, path):
            print(f"  {period}: ok (skipped, no request)")
            continue
        try:
            sha, size, fmt, tmp, final = stream_to(entry["url"], path)
            try:
                status = apply_result(entry, sha, size, fmt, accept_changes)
            except Drift:
                tmp.unlink(missing_ok=True)   # keep the verified copy intact
                raise
            tmp.replace(final)
            # Save after every file, not at the end of the system. A multi-GB
            # run that dies on file 80 must not throw away the first 79 pins.
            common.save_manifest(system_id, manifest)
            print(f"  {period}: {status} {fmt} {size:,}B {sha[:12]}…", flush=True)
        except (Drift, requests.RequestException, OSError) as exc:
            print(f"  {period}: FAILED — {exc}", file=sys.stderr, flush=True)
            failures += 1

    for name, entry in (manifest.get("reference") or {}).items():
        path = common.reference_path(system_id, name)
        if entry_is_satisfied(entry, path):
            print(f"  {name}: ok (skipped, no request)")
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            response = requests.get(
                entry["url"], timeout=120, headers={"User-Agent": common.USER_AGENT}
            )
            response.raise_for_status()
            sha = hashlib.sha256(response.content).hexdigest()
            # Verify before writing, for the same reason as above.
            status = apply_result(entry, sha, len(response.content), None, accept_changes)
            path.write_bytes(response.content)
            print(f"  {name}: {status} {len(response.content):,}B {sha[:12]}…")
        except (Drift, requests.RequestException) as exc:
            print(f"  {name}: FAILED — {exc}", file=sys.stderr)
            failures += 1

    common.save_manifest(system_id, manifest)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", choices=sorted(common.SYSTEMS), action="append")
    parser.add_argument("--period", action="append")
    parser.add_argument("--reference-only", action="store_true")
    parser.add_argument("--accept-changes", action="store_true")
    args = parser.parse_args()

    if args.period and len(args.system or []) != 1:
        parser.error("--period requires exactly one --system")

    failures = 0
    for system_id in args.system or sorted(common.SYSTEMS):
        print(f"\n=== {system_id} ({common.SYSTEMS[system_id]['city']})")
        failures += download_system(
            system_id, args.period, args.accept_changes, args.reference_only
        )
    if failures:
        print(f"\n{failures} download(s) failed", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
