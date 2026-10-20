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

No model is fitted and no GPU is used. The private 30 checkpoint files are not required or read; their recorded hashes are cross-checked among the public receipts, but the checkpoint bytes themselves cannot be independently checked from a clean clone. The verifier recomputes canonical validation metrics and point contrasts from saved predictions. It does not rerun the 20,000-draw descriptive uncertainty calculation, qualify its coverage, or independently validate the scientific claims.
