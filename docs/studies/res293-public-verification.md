# RES-293 clean-clone verification

From a clean clone, run:

```sh
git clone https://github.com/Litju/powerlifting-state-research.git
cd powerlifting-state-research
uv sync --locked --no-default-groups
uv run --locked --no-sync python scripts/verify_res293_public.py
```

Success exits with status `0` and prints `RES-293 public verification: PASS` with 102 verified published files, 90 canonical validation metric rows, and all 21 primary contrasts (also checked at 105 per-seed values). Any missing, altered, or identity-mismatched published artifact fails with status `1`.

The verifier checks the published report, receipts, fit summaries, 60 development/validation prediction files, analysis outputs, and their protocol, realization, split, fit, and prediction identities. If the ignored canonical IID data directory is absent, it reconstructs the same realization with the repository's deterministic public generator in a temporary directory and verifies the frozen manifest and train/validation hashes. A partial local data directory fails closed. The repository and published results are not written by verification.

The default command fits no model, uses no GPU, and does not read the 30 released model states. To replay the original 60 development/validation prediction files from the released states, run the separate optional replay:

```sh
uv run --locked --no-sync python scripts/verify_published_model_artifacts.py --replay-res293
```

It rebuilds the frozen fit-only feature inputs in a temporary directory, strictly loads each original state with `allow_pickle=False`, and requires byte-identical predictions. It does not fit, use development/validation labels as features, or write to results. The default verifier recomputes canonical validation metrics and point contrasts from saved predictions; neither command reruns the 20,000-draw descriptive uncertainty calculation, qualifies its coverage, or independently validates the scientific claims.
