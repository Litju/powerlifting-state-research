"""Independent verifier checks, including wrong-pair and false-PASS adversaries."""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import numpy as np
import pytest


def verifier() -> types.ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/verify_res510_correction.py"
    spec = importlib.util.spec_from_file_location("res510_verifier", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shared_identical_fits_keep_entity_uncertainty() -> None:
    module = verifier()
    control = np.zeros((5, 8))
    treatment = np.tile(np.arange(1.0, 9.0), (5, 1))
    strata = [np.array([i, i + 1]) for i in (0, 2, 4, 6)]
    crossed, conditional, draw_hash = module.bootstrap(treatment, control, strata, 42, 1000)
    assert np.array_equal(crossed, conditional)
    assert np.std(crossed) > 0.1
    second = module.bootstrap(treatment, control, strata, 42, 1000)
    assert np.array_equal(crossed, second[0]) and draw_hash == second[2]
    assert draw_hash != module.bootstrap(treatment, control, strata, 43, 1000)[2]


def test_pair_reversal_reverses_delta() -> None:
    module = verifier()
    rng = np.random.default_rng(5)
    treatment, control = rng.normal(size=(5, 8)), rng.normal(size=(5, 8))
    strata = [np.array([i, i + 1]) for i in (0, 2, 4, 6)]
    forward = module.bootstrap(treatment, control, strata, 4, 500)
    reverse = module.bootstrap(control, treatment, strata, 4, 500)
    assert np.allclose(forward[0], -reverse[0], atol=1e-15)
    assert np.allclose(forward[1], -reverse[1], atol=1e-15)


@pytest.mark.parametrize("size", [7, 31, 1000, 50000])
def test_dkw_order_bounds_cover_generalized_inverse(size: int) -> None:
    module = verifier()
    values = np.arange(float(size))
    _, _, lower, upper = module.interval(values, 0.01)
    inverse_lower = values[int(np.ceil(size * 0.015)) - 1]
    inverse_upper = values[int(np.ceil(size * 0.985)) - 1]
    assert lower <= inverse_lower and upper >= inverse_upper


@pytest.mark.parametrize(
    ("lower", "upper", "expected"),
    [
        (-3, -1.0001, "PRACTICAL_BENEFIT"),
        (1.0001, 3, "PRACTICAL_HARM"),
        (-1, 1, "PRACTICAL_EQUIVALENCE"),
        (-2, -1, "INCONCLUSIVE"),
        (1, 2, "INCONCLUSIVE"),
    ],
)
def test_boundaries(lower: float, upper: float, expected: str) -> None:
    assert verifier().classify(lower, upper) == expected


@pytest.mark.parametrize(("lower", "upper"), [(np.nan, 1), (0, np.inf), (2, 1)])
def test_invalid_intervals_fail(lower: float, upper: float) -> None:
    with pytest.raises(ValueError):
        verifier().classify(lower, upper)


def test_duplicate_cells_and_numerical_tampering_fail() -> None:
    module = verifier()
    with pytest.raises(ValueError, match="duplicate"):
        module.unique([{}, {}], ["same", "same"], "cells")
    with pytest.raises(ValueError, match="disagreement"):
        module.close(1.1, 1.0, "endpoint")
    with pytest.raises(ValueError, match="nonfinite"):
        module.close("nan", 1.0, "endpoint")


def test_instability_is_inconclusive() -> None:
    module = verifier()
    records = [
        {
            "corrected_percentile_status": "PRACTICAL_BENEFIT",
            "corrected_mc_status": "PRACTICAL_BENEFIT",
        }
        for _ in range(3)
    ]
    assert module.stable_status(records, "corrected") == "PRACTICAL_BENEFIT"
    records[-1]["corrected_mc_status"] = "INCONCLUSIVE"
    assert module.stable_status(records, "corrected") == "INCONCLUSIVE"


def test_missing_or_tampered_specification_cannot_pass(tmp_path: Path) -> None:
    module = verifier()
    with pytest.raises(ValueError, match="missing/unsafe"):
        module.verify(tmp_path)
    spec = tmp_path / module.SPEC_PATH
    spec.parent.mkdir(parents=True)
    spec.write_text("{}")
    with pytest.raises(ValueError, match="frozen specification changed"):
        module.verify(tmp_path)


def test_manifest_path_escape_and_symlink_fail(tmp_path: Path) -> None:
    module = verifier()
    with pytest.raises(ValueError, match="unsafe manifest"):
        module.safe_file(tmp_path, "../private")
    target = tmp_path / "target"
    target.write_text("test")
    (tmp_path / "link").symlink_to(target)
    with pytest.raises(ValueError, match="missing/unsafe"):
        module.safe_file(tmp_path, "link")


def test_original_nested_interval_loses_shared_variance() -> None:
    module = verifier()
    control = np.zeros((5, 8))
    treatment = np.tile(np.arange(1.0, 9.0), (5, 1))
    strata = [np.array([i, i + 1]) for i in (0, 2, 4, 6)]
    key = ("test_population_a", "deadlift", 56, "SYNTHETIC_ONLY_BOOTSTRAP", "PUBLIC_ONLY")
    nested = module.original_interval(treatment, control, strata, key)
    shared = module.original_interval(treatment, control, strata, key, shared=True)
    assert shared[1] - shared[0] > 1.5 * (nested[1] - nested[0])
    assert nested == module.original_interval(treatment, control, strata, key)


def test_receipt_rejects_separate_git_worktree(tmp_path: Path) -> None:
    import subprocess

    module = verifier()
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    with pytest.raises(ValueError, match="outside all Git worktrees"):
        module.safe_receipt_path(other / "not-yet-created" / "receipt.json", tmp_path / "root")
    module.safe_receipt_path(tmp_path / "evidence" / "receipt.json", tmp_path / "root")


def test_malformed_csv_cannot_pass(tmp_path: Path) -> None:
    module = verifier()
    path = tmp_path / "table.csv"
    for content in ("a,a\n1,2\n", "a,b\n1\n", "a,b\n1,2,3\n"):
        path.write_text(content)
        with pytest.raises(ValueError, match="malformed CSV"):
            module.rows(path)


def test_verifier_requires_exact_artifact_set(tmp_path: Path) -> None:
    module = verifier()
    directory = tmp_path / "correction"
    directory.mkdir()
    required = {
        "comparison.csv",
        "bootstrap-runs.csv",
        "changed-classifications.csv",
        "manifest.json",
        "SHA256SUMS.txt",
    }
    for name in sorted(required):
        (directory / name).write_text(name)
    module.require_exact_output_set(directory, required)
    (directory / "extra-metadata.json").write_text("{}")
    with pytest.raises(ValueError, match="extra="):
        module.require_exact_output_set(directory, required)
    (directory / "extra-metadata.json").unlink()
    (directory / "SHA256SUMS.txt").unlink()
    with pytest.raises(ValueError, match="missing="):
        module.require_exact_output_set(directory, required)
    (directory / "SHA256SUMS.txt").write_text("SHA256SUMS.txt")
    (directory / "empty-directory").mkdir()
    with pytest.raises(ValueError, match="extra="):
        module.require_exact_output_set(directory, required)
