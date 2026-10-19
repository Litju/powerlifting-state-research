# Reproducibility

Benchmark semantics, dataset realizations, fitted models, predictions, and evaluations have separate identities. A synthetic study is reproducible only within its specified data, information boundary, software environment, and evaluation. Artifact preservation and a numerical study replay establish different facts.

The [RES-299 verification record](res299-validation.md) lists commands actually executed for this documentation change. Commands below include optional numerical verification; their presence is not a claim they were run. The current [CI workflow](../.github/workflows/ci.yml) and [local-parity guide](../.github/workflows/README.md#local-parity) define ordinary engineering checks.

## Clean locked setup and ordinary checks

Use a full Git clone, including historical commits needed by preservation/replay checks. From the repository root:

```sh
uv sync --locked --all-groups --python 3.12
uv run --locked --no-sync ruff check .
uv run --locked --no-sync ruff format --check .
uv run --locked --no-sync mypy
uv run --locked --no-sync pytest
uv run --locked --no-sync python -m powerlifting_state_research.exports --check
uv run --locked --no-sync python scripts/check_repository_integrity.py
uv run --locked --no-sync python scripts/verify_release_freeze.py
uv run --locked --no-sync python scripts/verify_res284_execution.py
```

For an isolated clean dependency installation, set `UV_PROJECT_ENVIRONMENT` to an empty directory outside the checkout before the sync, and retain that variable for subsequent `uv run --no-sync` commands. The locked research group contains version-conditioned SciPy and scipy-stubs for Python 3.11 and 3.12/3.13; do not supplement the lock with ad-hoc installs. RES-289's original environment/source hashes remain execution-era identities, not hashes of today's environment.

The export check verifies generated registries/schemas against typed Python without writing. Integrity checks validate registry, public origin/rights ledger, artifact bindings, hashes, and public-file rules. Gitleaks and isolated wheel parity are in the CI guide. Ordinary tests exercise small synthetic fixtures; they skip the opt-in full IID production test.

## Public IID verification

```sh
uv run --locked --no-sync python scripts/verify_public_iid_production.py --check
```

This command **generates full train/validation JSONL in a fresh temporary directory**, compares its manifest byte-for-byte with the [tracked IID manifest](../data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json), and removes the temporary output. It is numerical data regeneration, not a read-only hash check of tracked rows. Use `--output-dir` only with a new isolated untracked destination if output retention is desired. It does not reconstruct historical scrambled-Sobol data.

The opt-in two-generation gate is:

```sh
PSR_FULL_PRODUCTION=1 uv run --locked --no-sync pytest tests/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/test_full_production.py
```

It compares both full generations and manifests with the canonical expectation. This heavier check is excluded from ordinary PR CI and was not run for RES-299's no-regeneration scope. The [RES-281 reproduction receipt](../results/audits/res281/reproducibility-execution.json) records an earlier two-generation execution; it is not a fresh RES-299 result.

## Historical RES-284 publication replay

```sh
uv run --locked --no-sync python scripts/verify_res284_execution.py
```

The verifier retrieves original full-file source hashes and the builder from Git commit `b2b664de6bba6372e61afc1a147255a7daecb8a1`. It verifies 184 historical source files and 41 builder outputs, then checks the current 42-file publication separately. It rebuilds publication documents from existing tables; it does not generate datasets, train, rescore, or bootstrap. Later source/ledger changes are reported as current-source drift, without editing historical bytes or substituting hashes. Do not use the frozen report's direct current-builder instructions as a claim that its execution-era source tree has replayed.

## Frozen-source preservation

```sh
uv run --locked --no-sync python scripts/verify_release_freeze.py
```

Despite its legacy name, this is a read-only preservation check, not scientific release approval. It compares the G4-bound upstream evidence, G4 sources, and G1–G4/RES-284 publication files with the pinned execution baseline `de014231569442c7e83d1774877a8b92a9abc314`. It does not rerun original studies. Correction evidence remains outside the frozen study directories. [RES-510](../studies/corrections/RES-510-v1/interpretation.md), [RES-511](../studies/corrections/RES-511-v1/interpretation.md), and the [current G4 reader notice](studies/g4-reader-corrections-v1.md) must accompany interpretation of the preserved original findings.

## Study verification and fresh generation

For an already populated checkout, the G3/G4 verification entrypoints are:

```sh
uv run --locked --no-sync python -m powerlifting_state_research.studies.public_surrogate_reconstruction --check
uv run --locked --no-sync python -m powerlifting_state_research.studies.synthetic_pretraining_transfer --check
```

These verify existing manifests/checksums **and rebuild numerical results in memory for comparison**. They do not overwrite frozen evidence, but are numerical replays and were not run for this documentation task. G4 `--check-report` aliases the full check; it is not a lightweight alternative. G3 has a separate `--check-report` publication check. No-argument G3/G4 entrypoints create outputs and reject an existing immutable result directory. Frozen reports showing no-argument commands describe initial generation, not the correct command for a populated checkout.

Fresh study generation, if separately authorized, must use an isolated untracked full repository copy and its own locked environment, outside the canonical checkout. The runner resolves its output relative to its imported source tree: changing only the shell working directory is insufficient. Retain Git history and frozen source evidence there, and make only that disposable copy's intended output destination absent. Never delete, replace, redirect, or regenerate evidence inside the canonical study/result homes. New experiments require new scientific identities rather than replacement of these frozen records. No fresh-generation command is part of this portfolio task.

RES-510's standalone verifier recomputes its bootstrap campaign; it is not a hash-only preservation command. The RES-299 verification record distinguishes stored-artifact checks from any numerical replay.

## Rights and interpretation

Preserve source identities, per-artifact notices, and the public origin ledger. Code and explicitly authorized machine-readable outputs are MIT; authored Markdown and the public-native IID dataset are CC BY 4.0. See the [RES-297 provenance clarification](../provenance/RES-297-prediction-provenance-clarification.md) for prediction-byte authorization and dataset attribution. Checkpoint bytes remain private. Passing engineering checks does not constitute independent scientific approval, real-athlete validity, or formal archival qualification.
