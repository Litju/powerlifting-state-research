"""Release preservation verifier checks in a disposable Git fixture."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_release_freeze.py"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=True, text=True
    )
    return result.stdout.strip()


def _fixture(root: Path) -> str:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Release Fixture")
    protected = root / "artifacts/registry.txt"
    protected.parent.mkdir(parents=True)
    protected.write_text("original scientific contract\n", encoding="utf-8")
    report = root / "results/studies/observation_inversion/report.md"
    report.parent.mkdir(parents=True)
    report.write_text("original published report\n", encoding="utf-8")
    frozen = root / "studies/synthetic_pretraining_transfer/frozen-evidence.json"
    frozen.parent.mkdir(parents=True)
    original_sha = "sha256:" + hashlib.sha256(protected.read_bytes()).hexdigest()
    frozen.write_text(json.dumps({"files": {"artifacts/registry.txt": original_sha}}))
    frozen_sha = "sha256:" + hashlib.sha256(frozen.read_bytes()).hexdigest()
    (frozen.parent / "protocol.json").write_text(
        json.dumps({"frozen_evidence": {"sha256": frozen_sha}})
    )
    g4 = root / "results/studies/synthetic_pretraining_transfer/public-native/manifest.json"
    g4.parent.mkdir(parents=True)
    protocol_sha = (
        "sha256:" + hashlib.sha256((frozen.parent / "protocol.json").read_bytes()).hexdigest()
    )
    source_paths = {"studies/synthetic_pretraining_transfer/protocol.json": protocol_sha}
    g4.write_text(json.dumps({"source_hashes": source_paths}))
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "test baseline")
    return _git(root, "rev-parse", "HEAD")


def _run(root: Path, baseline: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    path = root.parent / "release-freeze.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--baseline",
            baseline,
            "--json-out",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result, json.loads(path.read_text()) if path.exists() else {}


def test_original_source_and_publication_are_byte_identical(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    base = _fixture(root)
    process, report = _run(root, base)
    assert process.returncode == 0, process.stdout + process.stderr
    assert report["summary"]["upstream_frozen_paths"] == 1
    assert report["summary"]["published_baseline_paths"] == 2
    assert report["summary"]["g4_execution_source_paths"] == 1
    assert report["summary"]["status"] == "PASS"


def test_candidate_modification_fails_preservation(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    base = _fixture(root)
    (root / "artifacts/registry.txt").write_text("changed\n")
    (root / "results/studies/observation_inversion/report.md").write_text("changed\n")
    process, report = _run(root, base)
    assert process.returncode == 1
    assert report["summary"]["upstream_candidate_changes"] == 1
    assert report["summary"]["published_candidate_changes"] == 1
    assert "FROZEN_CANDIDATE_FILES_CHANGED" in report["blockers"]


def test_unavailable_baseline_is_not_marked_pass(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    _fixture(root)
    process, report = _run(root, "0" * 40)
    assert process.returncode == 2
    assert process.stdout.startswith("NOT_RUN")
    assert report["summary"]["status"] == "NOT_RUN"


def test_execution_bound_source_modification_fails(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    base = _fixture(root)
    (root / "studies/synthetic_pretraining_transfer/protocol.json").write_text("different")
    process, report = _run(root, base)
    assert process.returncode == 1
    assert report["summary"]["g4_execution_source_candidate_changes"] == 1


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "symlink",
        "parent_symlink",
        "untracked",
        "ignored",
        "staged",
        "hidden_head",
        "hidden_index",
        "mode",
        "mode_filemode_false",
        "frozen_manifest",
    ],
)
def test_preservation_rejects_false_pass(tmp_path: Path, case: str) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    base = _fixture(root)
    report = root / "results/studies/observation_inversion/report.md"
    if case in {"mode", "mode_filemode_false"}:
        if case == "mode_filemode_false":
            _git(root, "config", "core.filemode", "false")
        report.chmod(report.stat().st_mode | 0o111)
    elif case == "missing":
        report.unlink()
    elif case == "symlink":
        external = tmp_path / "external"
        external.write_bytes(report.read_bytes())
        report.unlink()
        report.symlink_to(external)
    elif case == "parent_symlink":
        directory = report.parent
        external = tmp_path / "external"
        directory.rename(external)
        directory.symlink_to(external, target_is_directory=True)
    elif case in {"untracked", "ignored", "staged"}:
        added = report.parent / "extra.txt"
        added.write_text("new evidence")
        if case == "ignored":
            (root / ".gitignore").write_text("extra.txt\n")
        elif case == "staged":
            _git(root, "add", ".")
    elif case in {"hidden_head", "hidden_index"}:
        original = report.read_bytes()
        report.write_text("changed commit")
        _git(root, "add", ".")
        if case == "hidden_head":
            _git(root, "commit", "-qm", "changed scientific evidence")
        report.write_bytes(original)
    else:
        (root / "studies/synthetic_pretraining_transfer/frozen-evidence.json").write_text("{}")
    process, result = _run(root, base)
    assert process.returncode == 1, process.stdout + process.stderr
    assert result["summary"]["status"] == "FAIL"


def test_output_cannot_overwrite_scientific_evidence(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    base = _fixture(root)
    output = root / "artifacts/registry.txt"
    original = output.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--baseline",
            base,
            "--json-out",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert output.read_bytes() == original


def test_malformed_evidence_is_inconclusive(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    _fixture(root)
    (root / "studies/synthetic_pretraining_transfer/frozen-evidence.json").write_text("[]")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "unsupported evidence")
    process, result = _run(root, _git(root, "rev-parse", "HEAD"))
    assert process.returncode == 2
    assert result["summary"]["status"] == "INCONCLUSIVE"


def test_git_replace_cannot_substitute_baseline(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    base = _fixture(root)
    (root / "studies/synthetic_pretraining_transfer/frozen-evidence.json").write_text("[]")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "substituted evidence")
    replacement = _git(root, "rev-parse", "HEAD")
    _git(root, "reset", "--hard", base)
    _git(root, "replace", base, replacement)
    process, report = _run(root, base)
    assert process.returncode == 0, process.stdout + process.stderr
    assert report["summary"]["status"] == "PASS"


def test_external_hardlink_output_preserves_original(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    base = _fixture(root)
    original = root / "artifacts/registry.txt"
    data = original.read_bytes()
    (root.parent / "release-freeze.json").hardlink_to(original)
    process, _ = _run(root, base)
    assert process.returncode == 0
    assert original.read_bytes() == data


def test_output_cannot_modify_other_worktree(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    base = _fixture(root)
    other = tmp_path / "baseline"
    other.mkdir()
    _fixture(other)
    output = other / "artifacts/registry.txt"
    original = output.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--baseline",
            base,
            "--json-out",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert output.read_bytes() == original


@pytest.mark.parametrize("layout", ["normal", "bare"])
def test_output_cannot_overwrite_other_git_metadata(tmp_path: Path, layout: str) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    base = _fixture(root)

    if layout == "normal":
        other = tmp_path / "other"
        other.mkdir()
        _fixture(other)
        output = other / ".git/config"
    else:
        bare = tmp_path / "other.git"
        subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
        output = bare / "config"

    original = output.read_bytes()
    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--baseline",
            base,
            "--json-out",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 1
    assert "outside Git worktrees and Git metadata" in process.stdout
    assert output.read_bytes() == original
