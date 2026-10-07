from __future__ import annotations

import filecmp
import os
from pathlib import Path

import pytest

from powerlifting_state_research.benchmarks import (
    latent_capacity_change_with_transient_expression_forecasting as benchmark,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("PSR_FULL_PRODUCTION") != "1",
    reason="full production regeneration is a release qualification gate",
)


def test_repeated_full_production_matches_the_checked_in_manifest(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    expected_manifest = (
        root
        / "data"
        / "manifests"
        / "realizations"
        / "latent_capacity_change_with_transient_expression_forecasting"
        / "iid-production.json"
    )
    first = benchmark.write_public_realization(tmp_path / "first", benchmark.DEFAULT_CONFIG)
    second = benchmark.write_public_realization(tmp_path / "second", benchmark.DEFAULT_CONFIG)

    for split in ("train", "validation"):
        assert filecmp.cmp(
            first.output_directory / f"{split}.jsonl",
            second.output_directory / f"{split}.jsonl",
            shallow=False,
        )
    assert (first.output_directory / "manifest.json").read_bytes() == expected_manifest.read_bytes()
    assert (
        second.output_directory / "manifest.json"
    ).read_bytes() == expected_manifest.read_bytes()
