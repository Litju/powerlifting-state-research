#!/usr/bin/env python3
"""Scan the exact candidate history and tree, emitting only a sanitized receipt."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from check_repository_integrity import (
    BINARY_SUFFIXES,
    OLD_MODULE_NAMES,
    PRIVATE_PATH,
    PRIVATE_REPO,
    PRIVATE_RUN,
    SECRET,
)

URL = re.compile(r"https?://[^\s<>\"']+")
GITLEAKS_VERSION = "8.18.4"


class SecurityScanError(RuntimeError):
    """The candidate fails security scanning or required evidence is unavailable."""


def parse_gitleaks_report(report: str) -> int:
    """Return the actual JSON finding count; malformed or non-object reports fail closed."""
    try:
        value = json.loads(report)
    except json.JSONDecodeError as error:
        raise SecurityScanError("Gitleaks produced invalid JSON") from error
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise SecurityScanError("Gitleaks JSON must be an array of finding objects")
    return len(value)


def require_clean_gitleaks_report(report: str, exit_code: int) -> None:
    findings = parse_gitleaks_report(report)
    if findings:
        raise SecurityScanError(f"Gitleaks found {findings} finding(s)")
    if exit_code != 0:
        raise SecurityScanError("Gitleaks failed before completing the scan")


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as error:
        raise SecurityScanError("Git history evidence could not be read") from error


def _scan_text(data: bytes, counts: Counter[str], hosts: set[str]) -> None:
    text = data.decode("utf-8", "replace")
    counts["credential_or_private_key_matches"] += len(SECRET.findall(text))
    counts["private_absolute_path_matches"] += len(PRIVATE_PATH.findall(text))
    counts["private_repository_marker_matches"] += text.lower().count(PRIVATE_REPO.lower())
    counts["private_execution_id_matches"] += len(PRIVATE_RUN.findall(text))
    urls = URL.findall(text)
    counts["url_occurrences_reviewed"] += len(urls)
    for value in urls:
        host = urlparse(value.rstrip(".,);]")).hostname
        if host:
            hosts.add(host.lower())


def _path_counts(paths: set[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for name in paths:
        parts = Path(name).parts
        if Path(name).suffix.lower() in BINARY_SUFFIXES:
            counts["historical_archive_or_binary_suffix_paths"] += 1
        if PRIVATE_REPO.lower() in name.lower():
            counts["private_repository_marker_matches"] += 1
        if PRIVATE_RUN.search(name):
            counts["private_execution_id_matches"] += 1
        if (
            parts
            and parts[0] in {"src", "tests", "docs"}
            and not ({"provenance", "history"} & set(parts))
        ):
            if any(
                part.lower() in OLD_MODULE_NAMES
                or part.lower().startswith(("pl_legacy_", "pl_response_"))
                for part in parts
            ):
                counts["legacy_alias_path_hits"] += 1
    return counts


def _reachable_blobs(root: Path, head: str) -> tuple[list[str], int]:
    object_ids = _git(root, "rev-list", "--objects", "--no-object-names", head)
    check = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "cat-file",
            "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        ],
        input=object_ids,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if check.returncode:
        raise SecurityScanError("Git object inventory failed")
    blobs: list[str] = []
    total_bytes = 0
    for line in check.stdout.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[1] == b"blob":
            blobs.append(fields[0].decode("ascii"))
            total_bytes += int(fields[2])
    return blobs, total_bytes


def _scan_blobs(root: Path, blobs: list[str]) -> tuple[Counter[str], set[str]]:
    counts: Counter[str] = Counter()
    hosts: set[str] = set()
    process = subprocess.Popen(
        ["git", "-C", str(root), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert process.stdin is not None and process.stdout is not None
    try:
        for blob in blobs:
            process.stdin.write(blob.encode("ascii") + b"\n")
            process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3 or header[1] != b"blob":
                raise SecurityScanError("Git blob stream is incomplete")
            size = int(header[2])
            data = process.stdout.read(size)
            process.stdout.read(1)
            if len(data) != size:
                raise SecurityScanError("Git blob stream is truncated")
            counts["reachable_blob_count"] += 1
            if b"\x00" in data:
                counts["binary_or_archive_signatures"] += int(
                    data.startswith((b"PK\x03\x04", b"\x1f\x8b", b"Rar!\x1a\x07"))
                )
                counts["non_text_blobs"] += 1
                continue
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                counts["non_text_blobs"] += 1
                continue
            _scan_text(data, counts, hosts)
    finally:
        process.stdin.close()
        process.wait()
    if process.returncode:
        raise SecurityScanError("Git blob scan failed")
    return counts, hosts


def _scan_worktree(root: Path) -> tuple[Counter[str], set[str], int]:
    counts: Counter[str] = Counter()
    hosts: set[str] = set()
    paths = {
        item.decode("utf-8")
        for item in _git(
            root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"
        ).split(b"\0")
        if item
    }
    counts.update(_path_counts(paths))
    for name in paths:
        try:
            data = (root / name).read_bytes()
        except OSError:
            counts["unreadable_candidate_files"] += 1
            continue
        if b"\x00" in data:
            counts["binary_or_archive_signatures"] += int(
                data.startswith((b"PK\x03\x04", b"\x1f\x8b", b"Rar!\x1a\x07"))
            )
            counts["non_text_blobs"] += 1
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            counts["non_text_blobs"] += 1
            continue
        _scan_text(data, counts, hosts)
    return counts, hosts, len(paths)


def _gitleaks_scan(binary: str, root: Path, head: str, *, history: bool) -> tuple[str, int]:
    try:
        version = subprocess.check_output(
            [binary, "version"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise SecurityScanError("Gitleaks is unavailable") from error
    if GITLEAKS_VERSION not in version:
        raise SecurityScanError(f"Expected Gitleaks {GITLEAKS_VERSION}")
    with tempfile.TemporaryDirectory(prefix="res297-gitleaks-") as tmp:
        report_path = Path(tmp) / "report.json"
        command = [
            binary,
            "detect",
            "--source",
            str(root),
            "--redact=100",
            "--report-format=json",
            f"--report-path={report_path}",
            "--exit-code=1",
            "--log-level=error",
            "--no-banner",
        ]
        if history:
            command.append(f"--log-opts={head}")
        else:
            command.append("--no-git")
        result = subprocess.run(command, capture_output=True, check=False)
        if not report_path.is_file():
            raise SecurityScanError("Gitleaks did not produce a JSON report")
        report = report_path.read_text(encoding="utf-8")
        require_clean_gitleaks_report(report, result.returncode)
        findings = parse_gitleaks_report(report)
    return version, findings


def build_receipt(root: Path, gitleaks: str = "gitleaks") -> dict[str, object]:
    root = root.resolve()
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    if _git(root, "status", "--porcelain=v1"):
        raise SecurityScanError("Exact-HEAD scan requires a clean worktree")
    commits = _git(root, "rev-list", "--count", head).decode().strip()
    blobs, blob_bytes = _reachable_blobs(root, head)
    history_counts, hosts = _scan_blobs(root, blobs)
    history_paths = {
        line.decode("utf-8")
        for line in _git(root, "log", "--format=", "--name-only", head).splitlines()
        if line
    }
    history_counts.update(_path_counts(history_paths))
    worktree_counts, worktree_hosts, current_paths = _scan_worktree(root)
    hosts.update(worktree_hosts)
    metadata = _git(root, "log", "--format=%H%x09%aI%x09%an <%ae>%n%B", head).decode(
        "utf-8", "replace"
    )
    author_identities: set[str] = set()
    for line in metadata.splitlines():
        if "\t" in line:
            parts = line.split("\t", 2)
            if len(parts) == 3:
                author_identities.add(parts[2])
        _scan_text(line.encode("utf-8"), history_counts, hosts)
    version, history_findings = _gitleaks_scan(gitleaks, root, head, history=True)
    _, working_tree_findings = _gitleaks_scan(gitleaks, root, head, history=False)
    history_counts["distinct_git_author_identities"] = len(author_identities)
    history_counts["distinct_hosts_seen"] = len(hosts)
    history_counts["history_commit_metadata_records_scanned"] = int(commits)
    blocking = {
        key: history_counts.get(key, 0) + worktree_counts.get(key, 0)
        for key in (
            "binary_or_archive_signatures",
            "credential_or_private_key_matches",
            "private_absolute_path_matches",
            "private_execution_id_matches",
            "private_repository_marker_matches",
            "legacy_alias_path_hits",
            "historical_archive_or_binary_suffix_paths",
            "non_text_blobs",
            "unreadable_candidate_files",
        )
    }
    blocking["gitleaks_findings"] = history_findings + working_tree_findings
    if any(blocking.values()):
        raise SecurityScanError("Security/history scan found blocking findings")
    return {
        "format": "PSR_RES297_SECURITY_HISTORY_SCAN_V1",
        "scanned_head": head,
        "worktree_clean": True,
        "coverage": {
            "reachable_commits": int(commits),
            "reachable_blobs": history_counts.get("reachable_blob_count", 0),
            "reachable_blob_bytes": blob_bytes,
            "historical_paths": len(history_paths),
            "candidate_paths": current_paths,
            "gitleaks_version": version,
            "gitleaks_history_findings": history_findings,
            "gitleaks_candidate_tree_findings": working_tree_findings,
        },
        "repository_pattern_scan": {
            **dict(history_counts),
            "candidate_tree_credential_or_private_key_matches": worktree_counts.get(
                "credential_or_private_key_matches", 0
            ),
            "candidate_tree_private_absolute_path_matches": worktree_counts.get(
                "private_absolute_path_matches", 0
            ),
            "candidate_tree_private_execution_id_matches": worktree_counts.get(
                "private_execution_id_matches", 0
            ),
            "candidate_tree_private_repository_marker_matches": worktree_counts.get(
                "private_repository_marker_matches", 0
            ),
            "candidate_tree_non_text_blobs": worktree_counts.get("non_text_blobs", 0),
            "candidate_tree_url_occurrences_reviewed": worktree_counts.get(
                "url_occurrences_reviewed", 0
            ),
            "candidate_tree_distinct_hosts_seen": len(worktree_hosts),
            "raw_values_or_matching_paths_published": False,
        },
        "limitations": [
            (
                "Pattern scans do not prove the absence of every secret, private identifier, "
                "or sensitive datum."
            ),
            (
                "Only Git objects reachable from the exact scanned HEAD and the clean candidate "
                "tree were inspected."
            ),
            (
                "Unreachable Git objects, private workspaces, and external artifact storage "
                "were not scanned."
            ),
            (
                "No cloud-provider credential validation or legal ownership determination "
                "was performed."
            ),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--gitleaks", default="gitleaks")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    try:
        receipt = build_receipt(args.root, args.gitleaks)
        output = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        if args.json_out:
            args.json_out.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
    except (OSError, SecurityScanError) as error:
        print(f"FAIL: sanitized RES-297 security/history verification: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
