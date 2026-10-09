# Reproducibility scripts

`export_benchmark_registry.py` regenerates the machine-readable benchmark registry and both schema exports from the Python authority. The schemas describe structure only; semantic and cross-field rules remain in the Python contract validator. Run `python -m powerlifting_state_research.exports --check` to detect drift in the checked-in registry and package schemas.

`export_public_native_training_protocol.py` writes/checks the typed temporal-expert protocol manifest. `build_res274_colab_notebook.py` writes/checks the output-free Colab driver, and `validate_res274_colab_notebook.py` verifies its 16-cell order, exact-source checkout, GPU bootstrap, runner use, output state, and public-safe contents.

`export_standardized_comparator_protocol.py` writes/checks the typed RES-275 comparator protocol before training.

To regenerate and verify the frozen IID files, run `uv run --locked python scripts/verify_public_iid_production.py --output-dir data/synthetic/latent_capacity_change_with_transient_expression_forecasting/iid-production --check`. After the protocol, comparator code, and tests are committed, `uv run --locked python -m powerlifting_state_research.models.comparators` fits the six declared methods, seals all fitted states before opening canonical validation, evaluates them through RES-271, and refuses to overwrite existing result artifacts.

`python -m powerlifting_state_research.models.train_temporal_expert verify-existing` checks the preserved RES-274 Gate-B run against regenerated IID data. It requires separate artifact and verifier commit SHAs and writes its PASS receipt under the Drive `res274/verifications/<RUN_ID>/` directory, outside the run and ZIP.

This directory intentionally has no general command-line framework. Build, test, type-check, and lint commands are provided by the development toolchain in pyproject.toml.
