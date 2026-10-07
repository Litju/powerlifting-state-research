# Reproducibility

Keep benchmark semantics, dataset realizations, models, predictions, and evaluations as separately identified objects.

A reproducible report records the package version, benchmark specification, generator and configuration identity, seed or replicate, data schema and checksums, split and temporal coverage, model and training protocol, prediction artifact, evaluation protocol, software environment, and result files. Regeneration should reproduce both the artifact and its declared identity.

Typed Python is the semantic source of truth. The benchmark registry JSON and JSON Schemas are generated exports. Large datasets and checkpoints are distributed or tracked only after their rights and storage policy are explicit. A historical realization is not regenerated or copied by the initial bootstrap.

Regenerate the public-native IID train/validation realization and its `DatasetRealizationManifest` from the repository root with `python -m powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting`. The command writes deterministic JSONL under `data/synthetic/` and updates `data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json`. Population, intervention/history allocation, split membership, observation noise, and serialization order each have explicit seed ownership; serialization shuffles only completed rows. State transitions have no process-noise stream.

The full production release verifier is `uv run --locked python scripts/verify_public_iid_production.py --check`. It creates a fresh output directory, computes hashes, and compares the generated manifest with the checked-in expectation. Full generation is intentionally excluded from ordinary PR CI; the opt-in pytest gate repeats production generation and compares train, validation, and manifest bytes.
