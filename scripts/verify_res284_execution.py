#!/usr/bin/env python3
"""Verify the frozen RES-284 publication against its execution-era Git source."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

EXECUTION_COMMIT = "b2b664de6bba6372e61afc1a147255a7daecb8a1"
OUTPUT_DIR = "results/audits/res284-publication"
INDEX_PATH = f"{OUTPUT_DIR}/checksum-index.json"
LEDGER_PATH = "provenance/PUBLIC_FILE_ORIGINS.csv"
BUILDER = "powerlifting_state_research.audits.res284_publication"


class VerificationError(ValueError):
    """The archived evidence or current publication does not match its hashes."""


def _git(root: Path, *args: str) -> bytes:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(root), *args],
        capture_output=True,
        check=False,
        env=env,
    )
    if result.returncode:
        raise VerificationError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _read_file(root: Path, relative: str) -> bytes:
    path = PurePosixPath(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
        raise VerificationError(f"unsafe evidence path: {relative}")
    candidate = root.joinpath(*path.parts)
    if any(parent.is_symlink() for parent in (candidate, *candidate.parents) if parent != root):
        raise VerificationError(f"symlink evidence path: {relative}")
    if candidate.is_symlink() or not candidate.is_file():
        raise VerificationError(f"missing evidence file: {relative}")
    return candidate.read_bytes()


def _hash_records(index: dict[str, object], name: str) -> dict[str, str]:
    rows = index.get(name)
    if not isinstance(rows, list):
        raise VerificationError(f"checksum index has no {name} list")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise VerificationError(f"invalid {name} entry")
        path = row.get("path")
        digest = row.get("sha256")
        if (
            not isinstance(path, str)
            or not isinstance(digest, str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
            or path in result
        ):
            raise VerificationError(f"invalid or duplicate {name} entry: {path}")
        result[path] = digest
    if not result:
        raise VerificationError(f"checksum index has an empty {name} list")
    return result


def _verify_hashes(root: Path, records: dict[str, str], label: str) -> None:
    for relative, expected in records.items():
        observed = _digest(_read_file(root, relative))
        if observed != expected:
            raise VerificationError(f"{label} SHA-256 mismatch: {relative}")


def _execution_tree(root: Path, snapshot: Path) -> None:
    _git(root, "worktree", "add", "--detach", str(snapshot), EXECUTION_COMMIT)


def _verify_current_outputs(root: Path, index_bytes: bytes, output_hashes: dict[str, str]) -> None:
    expected_paths = set(output_hashes) | {INDEX_PATH}
    directory = root / OUTPUT_DIR
    if directory.is_symlink() or not directory.is_dir():
        raise VerificationError(f"missing or unsafe publication directory: {OUTPUT_DIR}")
    actual_paths: set[str] = set()
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise VerificationError(f"symlink in RES-284 publication: {path.relative_to(root)}")
        if path.is_file():
            actual_paths.add(path.relative_to(root).as_posix())
    if actual_paths != expected_paths:
        missing = sorted(expected_paths - actual_paths)
        extra = sorted(actual_paths - expected_paths)
        raise VerificationError(f"publication inventory differs; missing={missing}; extra={extra}")
    if _read_file(root, INDEX_PATH) != index_bytes:
        raise VerificationError("current RES-284 checksum index differs from execution-era index")
    _verify_hashes(root, output_hashes, "publication output")


def _current_source_changes(
    root: Path, snapshot: Path, source_hashes: dict[str, str]
) -> list[tuple[str, str, str | None]]:
    changes: list[tuple[str, str, str | None]] = []
    for relative, expected in source_hashes.items():
        try:
            content = _read_file(root, relative)
        except VerificationError:
            changes.append((relative, "MISSING", None))
            continue
        observed = _digest(content)
        if observed != expected:
            # Compare the current ledger with the entire archived file, not a byte-count prefix.
            status = (
                "APPENDED_AFTER_EXECUTION"
                if relative == LEDGER_PATH and content.startswith(_read_file(snapshot, relative))
                else "CHANGED"
            )
            changes.append((relative, status, observed))
    return changes


def verify(root: Path) -> dict[str, object]:
    root = root.resolve()
    git_root = Path(_git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if root != git_root:
        raise VerificationError("root must be the Git worktree top level")
    head = _git(root, "rev-parse", "HEAD^{commit}").decode().strip()
    if (
        _git(root, "rev-parse", f"{EXECUTION_COMMIT}^{{commit}}").decode().strip()
        != EXECUTION_COMMIT
    ):
        raise VerificationError("execution commit did not resolve exactly")
    ancestor = subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "-C",
            str(root),
            "merge-base",
            "--is-ancestor",
            EXECUTION_COMMIT,
            head,
        ],
        capture_output=True,
        check=False,
        env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    )
    if ancestor.returncode:
        raise VerificationError("execution commit is not an ancestor of the current checkout")

    index_bytes = _git(root, "show", f"{EXECUTION_COMMIT}:{INDEX_PATH}")
    index = json.loads(index_bytes)
    if not isinstance(index, dict) or index.get("format") != "PSR_RES284_PUBLICATION_INDEX_V1":
        raise VerificationError("unexpected execution-era RES-284 checksum index")
    source_hashes = _hash_records(index, "source_files")
    output_hashes = _hash_records(index, "files")
    if INDEX_PATH in output_hashes:
        raise VerificationError("checksum index cannot hash itself")
    with tempfile.TemporaryDirectory(prefix="psr-res284-execution-") as temporary:
        snapshot = Path(temporary) / "source"
        _execution_tree(root, snapshot)
        try:
            if _read_file(snapshot, INDEX_PATH) != index_bytes:
                raise VerificationError("execution-era checksum index differs from its Git commit")
            _verify_hashes(snapshot, source_hashes, "execution-era source")
            _verify_hashes(snapshot, output_hashes, "execution-era publication")
            _verify_current_outputs(root, index_bytes, output_hashes)
            changes = _current_source_changes(root, snapshot, source_hashes)
            unexpected = [change for change in changes if change[1] != "APPENDED_AFTER_EXECUTION"]
            if unexpected:
                raise VerificationError(
                    f"current source files differ from execution era: {unexpected}"
                )

            environment = dict(os.environ)
            environment["PYTHONPATH"] = os.pathsep.join(
                part for part in (str(snapshot / "src"), environment.get("PYTHONPATH", "")) if part
            )
            replay = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    BUILDER,
                    "--root",
                    str(snapshot),
                    "--check",
                ],
                cwd=snapshot,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            if replay.returncode:
                raise VerificationError(
                    "execution-era RES-284 replay failed:\n" + replay.stdout + replay.stderr
                )
            return {
                "current_head": head,
                "execution_commit": EXECUTION_COMMIT,
                "execution_index_sha256": _digest(index_bytes),
                "execution_source_files": len(source_hashes),
                "execution_output_files": len(output_hashes),
                "current_ledger_sha256": _digest(_read_file(root, LEDGER_PATH)),
                "historical_ledger_sha256": source_hashes[LEDGER_PATH],
                "current_source_changes": changes,
                "replay_output": replay.stdout.strip(),
            }
        finally:
            _git(root, "worktree", "remove", "--force", str(snapshot))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        result = verify(args.root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"PASS: historical RES-284 source and replay at {result['execution_commit']}")
    print(
        f"PASS: {result['execution_source_files']} source files and "
        f"{result['execution_output_files']} published files match full-file SHA-256"
    )
    print(
        f"PASS: current {result['execution_output_files'] + 1}-file bundle matches "
        "the execution-era checksum index"
    )
    print(f"Current checkout HEAD: {result['current_head']}")
    print(
        "Origin ledger identity: "
        f"execution={result['historical_ledger_sha256']}; "
        f"current={result['current_ledger_sha256']}"
    )
    for path, status, observed in result["current_source_changes"]:
        print(f"Current source state: {path} {status} {observed or ''}".rstrip())
    print(result["replay_output"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
