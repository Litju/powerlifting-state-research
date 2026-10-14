"""Crossed-inference sampling and trust-boundary regression checks."""

from __future__ import annotations

import runpy
from pathlib import Path

import numpy as np
import pytest

MODULE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/res510_correct_inference.py")
)


@pytest.mark.parametrize(
    "lower,upper,expected",
    [
        (-2.0, -1.0001, "PRACTICAL_BENEFIT"),
        (-2.0, -1.0, "INCONCLUSIVE"),
        (1.0001, 2.0, "PRACTICAL_HARM"),
        (1.0, 2.0, "INCONCLUSIVE"),
        (-1.0, 1.0, "PRACTICAL_EQUIVALENCE"),
        (-1.1, 0.0, "INCONCLUSIVE"),
    ],
)
def test_practical_rule(lower: float, upper: float, expected: str) -> None:
    assert MODULE["decision"](lower, upper) == expected


@pytest.mark.parametrize("lower,upper", [(float("nan"), 1.0), (0.0, float("inf")), (2.0, 1.0)])
def test_invalid_interval_is_rejected(lower: float, upper: float) -> None:
    with pytest.raises(ValueError):
        MODULE["decision"](lower, upper)


def test_shared_entities_and_paired_seeds_match_explicit_reduction() -> None:
    treatment = np.arange(1, 21, dtype=np.float64).reshape(5, 4)
    control = treatment / 2
    seeds = np.array([[0, 0, 2, 4, 4], [1, 3, 0, 2, 2]])
    entities = np.array([[0, 1, 1, 3], [2, 2, 0, 3]])
    crossed, conditional = MODULE["distribution"](treatment, control, seeds, entities)
    expected = [
        [
            np.sqrt(np.mean(treatment[s, entities[b]] ** 2))
            - np.sqrt(np.mean(control[s, entities[b]] ** 2))
            for s in range(5)
        ]
        for b in range(2)
    ]
    assert np.allclose(
        crossed, [np.mean([expected[b][s] for s in seeds[b]]) for b in range(2)], atol=1e-14
    )
    assert np.allclose(conditional, np.mean(expected, axis=1), atol=1e-14)
    assert not np.isclose(crossed[0], conditional[0])


def test_identical_fits_do_not_average_away_entity_uncertainty() -> None:
    treatment = np.tile(np.array([1.0, 2.0, 3.0, 4.0]), (5, 1))
    control = treatment / 2
    seeds = np.array([[0, 1, 2, 3, 4], [4, 4, 4, 4, 4]])
    entities = np.array([[0, 0, 1, 1], [2, 2, 3, 3]])
    crossed, conditional = MODULE["distribution"](treatment, control, seeds, entities)
    assert np.array_equal(crossed, conditional)
    assert crossed[0] != crossed[1]


def test_mean_of_rmse_differences_is_not_pooled_rmse() -> None:
    treatment = np.repeat(np.arange(1.0, 6.0)[:, None], 4, axis=1)
    control = np.ones_like(treatment)
    seeds = np.tile(np.arange(5), (1, 1))
    entities = np.arange(4).reshape(1, -1)
    crossed, _ = MODULE["distribution"](treatment, control, seeds, entities)
    assert crossed[0] == 2.0
    assert crossed[0] != np.sqrt(np.mean(treatment**2)) - 1.0


def test_sampling_reproducible_stratified_and_seed_paired() -> None:
    plans = ["a", "b", "a", "b"]
    first = MODULE["draw"](plans, 20, 42, ["a", "b"])
    second = MODULE["draw"](plans, 20, 42, ["a", "b"])
    assert all(np.array_equal(a, b) for a, b in zip(first, second, strict=True))
    assert first[0].shape == (20, 5)
    assert np.isin(first[1][:, :2], [0, 2]).all()
    assert np.isin(first[1][:, 2:], [1, 3]).all()


def test_monte_carlo_boundary_disagreement_is_inconclusive() -> None:
    rows = [
        {
            "corrected_percentile_status": "PRACTICAL_EQUIVALENCE",
            "corrected_mc_status": "PRACTICAL_EQUIVALENCE",
        }
        for _ in range(3)
    ]
    assert MODULE["final_status"](rows, "corrected_") == "PRACTICAL_EQUIVALENCE"
    rows[-1]["corrected_mc_status"] = "INCONCLUSIVE"
    assert MODULE["final_status"](rows, "corrected_") == "INCONCLUSIVE"


def test_outer_order_statistics_enclose_linear_percentiles() -> None:
    sample = np.arange(100, dtype=np.float64)
    result = MODULE["interval"](sample, 0.01)
    assert result["mc_lower_kg"] <= result["ci95_lower_kg"]
    assert result["mc_upper_kg"] >= result["ci95_upper_kg"]


def test_duplicate_and_missing_data_do_not_pass() -> None:
    with pytest.raises(ValueError):
        MODULE["unique_rows"]([{"row_id": "same"}, {"row_id": "same"}])
    with pytest.raises(ValueError):
        MODULE["distribution"](
            np.ones((4, 4)),
            np.ones((4, 4)),
            np.zeros((2, 5), dtype=int),
            np.zeros((2, 4), dtype=int),
        )


def test_original_inputs_and_all_cells_are_qualified() -> None:
    root = Path(__file__).resolve().parents[1]
    spec, _, original, _ = MODULE["load"](root)
    assert spec["replicates"] == 50000
    assert len(original) == 108
