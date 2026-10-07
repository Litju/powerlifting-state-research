"""Executable public implementation of the frozen latent-capacity task."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from ...contracts.benchmark import ImplementationStatus
from .dataset import DEFAULT_CONFIG, GenerationConfig, write_manifest_copy, write_public_realization

IMPLEMENTATION_STATUS = ImplementationStatus.PUBLIC_IMPLEMENTED
PUBLIC_IMPLEMENTATION = "latent_capacity_transient_performance_expression_dynamics/public-v4"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/synthetic/latent_capacity_change_with_transient_expression_forecasting/public-v4"
        ),
        help="new directory for train.jsonl, validation.jsonl, and manifest.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "data/manifests/realizations/"
            "latent_capacity_change_with_transient_expression_forecasting/public-v4.json"
        ),
        help="tracked copy of the DatasetRealizationManifest",
    )
    parser.add_argument("--train-rows", type=int, default=DEFAULT_CONFIG.train_rows)
    parser.add_argument("--validation-rows", type=int, default=DEFAULT_CONFIG.validation_rows)
    parser.add_argument("--population-seed", type=int, default=DEFAULT_CONFIG.population_seed)
    parser.add_argument("--intervention-seed", type=int, default=DEFAULT_CONFIG.intervention_seed)
    parser.add_argument("--observation-seed", type=int, default=DEFAULT_CONFIG.observation_seed)
    parser.add_argument("--split-seed", type=int, default=DEFAULT_CONFIG.split_seed)
    parser.add_argument("--serialization-seed", type=int, default=DEFAULT_CONFIG.serialization_seed)
    args = parser.parse_args(argv)
    config = GenerationConfig(
        train_rows=args.train_rows,
        validation_rows=args.validation_rows,
        population_seed=args.population_seed,
        intervention_seed=args.intervention_seed,
        observation_seed=args.observation_seed,
        split_seed=args.split_seed,
        serialization_seed=args.serialization_seed,
    )
    realization = write_public_realization(args.output, config)
    write_manifest_copy(realization.manifest, args.manifest)
    print(
        f"Generated {config.train_rows} train and {config.validation_rows} validation rows; "
        f"realization={realization.manifest.identity_id}; "
        f"train_sha256={realization.train_sha256}; "
        f"validation_sha256={realization.validation_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
