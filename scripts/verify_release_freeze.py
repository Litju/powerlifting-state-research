#!/usr/bin/env python3
"""Audit immutable G1-G4/RES-284 release inputs against a pinned Git commit.

This read-only release *preservation* check is not a numerical study replay.
Requires a Git checkout containing the baseline commit (not a shallow-only tip).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

BASELINE = "de014231569442c7e83d1774877a8b92a9abc314"
FROZEN = "studies/synthetic_pretraining_transfer/frozen-evidence.json"
PROTOCOL = "studies/synthetic_pretraining_transfer/protocol.json"
G4_MANIFEST = "results/studies/synthetic_pretraining_transfer/public-native/manifest.json"
PROTECTED_PREFIXES = (
    "results/studies/observation_inversion/",
    "results/studies/target_sufficient_structural_reconstruction/",
    "results/studies/public_surrogate_reconstruction/",
    "results/studies/synthetic_pretraining_transfer/",
    "results/audits/res284-publication/",
)


class FreezeError(RuntimeError):
    """The declared baseline cannot be independently inspected."""


def _git(root: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False
    )
    if proc.returncode:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise FreezeError(f"git {' '.join(args[:2])}: {detail}")
    return proc.stdout


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _checked_file(root: Path, path: str) -> str | None:
    candidate = root / path
    return _digest(candidate.read_bytes()) if candidate.is_file() else None


def _baseline_bytes(root: Path, commit: str, path: str) -> bytes:
    return _git(root, "show", f"{commit}:{path}")


def _status(current: str | None, baseline: str) -> str:
    if current is None:
        return "MISSING"
    return "UNCHANGED" if current == baseline else "CHANGED"


def _tracked(root: Path, commit: str) -> set[str]:
    rows = _git(root, "ls-tree", "-r", "--name-only", "-z", commit, "--", *PROTECTED_PREFIXES)
    return {part.decode("utf-8") for part in rows.split(b"\0") if part}


def inspect(root: Path, baseline: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", baseline):
        raise FreezeError("baseline must be a complete 40-character commit SHA")
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    if _git(root, "rev-parse", f"{baseline}^{{commit}}").decode().strip() != baseline:
        raise FreezeError("baseline ref did not resolve to the specified commit")
    _git(root, "merge-base", "--is-ancestor", baseline, "HEAD")
    frozen_bytes = _baseline_bytes(root, baseline, FROZEN)
    protocol = json.loads(_baseline_bytes(root, baseline, PROTOCOL))
    frozen = json.loads(frozen_bytes)
    frozen_digest = _digest(frozen_bytes)
    recorded_digest = protocol["frozen_evidence"]["sha256"]
    pinned = frozen.get("files")
    if not isinstance(pinned, dict) or not pinned:
        raise FreezeError("baseline has no frozen source-file map")
    upstream: list[dict[str, str | None]] = []
    for path, expected in sorted(pinned.items()):
        if path.startswith("/") or ".." in Path(path).parts:
            raise FreezeError(f"unsafe frozen path: {path}")
        actual = _digest(_baseline_bytes(root, baseline, path))
        current = _checked_file(root, path)
        upstream.append(
            {
                "path": path,
                "frozen_sha256": expected,
                "baseline_sha256": actual,
                "candidate_sha256": current,
                "baseline_status": "PASS" if actual == expected else "FAIL",
                "candidate_status": _status(current, actual),
            }
        )
    manifest = json.loads(_baseline_bytes(root, baseline, G4_MANIFEST))
    bound_sources = manifest.get("source_hashes")
    if not isinstance(bound_sources, dict) or not bound_sources:
        raise FreezeError("baseline G4 manifest has no bound execution-source hashes")
    execution_sources: list[dict[str, str | None]] = []
    for path, expected in sorted(bound_sources.items()):
        if path.startswith("/") or ".." in Path(path).parts:
            raise FreezeError(f"unsafe execution-source path: {path}")
        actual = _digest(_baseline_bytes(root, baseline, path))
        current = _checked_file(root, path)
        execution_sources.append(
            {
                "path": path,
                "recorded_sha256": expected,
                "baseline_sha256": actual,
                "candidate_sha256": current,
                "baseline_status": "PASS" if expected == actual else "FAIL",
                "candidate_status": _status(current, actual),
            }
        )
    protected_paths = _tracked(root, baseline)
    originals: list[dict[str, str | None]] = []
    for path in sorted(protected_paths):
        original = _digest(_baseline_bytes(root, baseline, path))
        current = _checked_file(root, path)
        originals.append(
            {
                "path": path,
                "baseline_sha256": original,
                "candidate_sha256": current,
                "candidate_status": _status(current, original),
            }
        )
    current_tracked = {
        part.decode("utf-8")
        for part in _git(root, "ls-files", "-z", "--", *PROTECTED_PREFIXES).split(b"\0")
        if part
    }
    added_outputs = sorted(current_tracked - protected_paths)
    baseline_bad = sorted(x["path"] for x in upstream if x["baseline_status"] != "PASS")
    execution_baseline_bad = sorted(
        x["path"] for x in execution_sources if x["baseline_status"] != "PASS"
    )
    execution_candidate_bad = sorted(
        x["path"] for x in execution_sources if x["candidate_status"] != "UNCHANGED"
    )
    candidate_upstream_bad = sorted(
        x["path"] for x in upstream if x["candidate_status"] != "UNCHANGED"
    )
    candidate_output_bad = sorted(
        x["path"] for x in originals if x["candidate_status"] != "UNCHANGED"
    )
    blockers = []
    if frozen_digest != recorded_digest:
        blockers.append("FROZEN_MANIFEST_DIGEST_MISMATCH")
    if baseline_bad or execution_baseline_bad:
        blockers.append("FROZEN_BASELINE_SOURCE_MISMATCH")
    if candidate_upstream_bad or execution_candidate_bad or candidate_output_bad or added_outputs:
        blockers.append("FROZEN_CANDIDATE_FILES_CHANGED")
    return {
        "format": "PSR_RELEASE_FROZEN_SOURCE_AUDIT_V1",
        "scope": "source/byte preservation; not scientific or rights qualification",
        "baseline_commit": baseline,
        "candidate_head": head,
        "frozen_manifest_sha256": frozen_digest,
        "recorded_frozen_manifest_sha256": recorded_digest,
        "summary": {
            "upstream_frozen_paths": len(upstream),
            "upstream_baseline_mismatches": len(baseline_bad),
            "upstream_candidate_changes": len(candidate_upstream_bad),
            "g4_execution_source_paths": len(execution_sources),
            "g4_execution_source_baseline_mismatches": len(execution_baseline_bad),
            "g4_execution_source_candidate_changes": len(execution_candidate_bad),
            "published_baseline_paths": len(originals),
            "published_candidate_changes": len(candidate_output_bad),
            "unexpected_published_candidate_paths": len(added_outputs),
            "status": "PASS" if not blockers else "FAIL",
        },
        "blockers": blockers,
        "changed_upstream_paths": candidate_upstream_bad,
        "changed_execution_source_paths": execution_candidate_bad,
        "changed_publication_paths": candidate_output_bad,
        "unexpected_publication_paths": added_outputs,
        "upstream": upstream,
        "execution_sources": execution_sources,
        "published": originals,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline", default=BASELINE)
    parser.add_argument(
        "--json-out", type=Path, help="optional evidence path (outside Git worktree)"
    )
    args = parser.parse_args()
    try:
        result = inspect(args.root.resolve(), args.baseline)
    except (FreezeError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"NOT_RUN: cannot establish independent frozen-source qualification: {exc}")
        return 2
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    summary = result["summary"]
    print(
        f"{summary['status']}: {summary['upstream_frozen_paths']} frozen upstream files; "
        f"{summary['g4_execution_source_paths']} bound G4 source files; "
        f"{summary['published_baseline_paths']} publication files; "
        f"{summary['upstream_baseline_mismatches']} baseline mismatches; "
        f"{summary['upstream_candidate_changes']} upstream changes; "
        f"{summary['g4_execution_source_candidate_changes']} G4 source changes; "
        f"{summary['published_candidate_changes']} publication changes; "
        f"{summary['unexpected_published_candidate_paths']} unexpected publication files"
    )
    for blocker in result["blockers"]:
        print(f"- {blocker}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
