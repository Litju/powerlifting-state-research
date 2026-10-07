#!/usr/bin/env python3
"""Regenerate and optionally verify the full public IID production realization."""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from powerlifting_state_research.benchmarks import (  # noqa: E402
    latent_capacity_change_with_transient_expression_forecasting as benchmark,
)

EXPECTED_MANIFEST = (
    ROOT
    / "data"
    / "manifests"
    / "realizations"
    / "latent_capacity_change_with_transient_expression_forecasting"
    / "iid-production.json"
)


def verify(output_directory: Path, expected_manifest: Path, compare: bool) -> int:
    realization = benchmark.write_public_realization(output_directory, benchmark.DEFAULT_CONFIG)
    generated_manifest = realization.output_directory / "manifest.json"
    print(f"output_directory={realization.output_directory}")
    print(f"train_sha256={realization.train_sha256}")
    print(f"validation_sha256={realization.validation_sha256}")
    print(f"realization_id={realization.manifest.identity_id}")
    print(f"realization_digest={realization.manifest.realization_digest}")
    print(f"manifest_digest={realization.manifest.manifest_digest}")
    if compare:
        if generated_manifest.read_bytes() != expected_manifest.read_bytes():
            print(f"FAIL: generated manifest differs from {expected_manifest}", file=sys.stderr)
            return 1
        print(f"PASS: generated manifest matches {expected_manifest}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="new output directory (default: temporary fresh directory)",
    )
    parser.add_argument(
        "--expected-manifest",
        type=Path,
        default=EXPECTED_MANIFEST,
        help="checked-in public manifest used by --check",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail unless generated manifest bytes match the expected manifest",
    )
    args = parser.parse_args(argv)
    if args.output_dir is not None:
        return verify(args.output_dir, args.expected_manifest, args.check)
    with tempfile.TemporaryDirectory(prefix="psr-iid-production-") as temporary:
        return verify(Path(temporary) / "realization", args.expected_manifest, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
