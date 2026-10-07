# Reproducibility

Keep benchmark semantics, dataset realizations, models, predictions, and evaluations as separately identified objects.

A reproducible report records the package version, benchmark specification, generator and configuration identity, seed or replicate, data schema and checksums, split and temporal coverage, model and training protocol, prediction artifact, evaluation protocol, software environment, and result files. Regeneration should reproduce both the artifact and its declared identity.

Typed Python is the semantic source of truth. The benchmark registry JSON and JSON Schemas are generated exports. Large datasets and checkpoints are distributed or tracked only after their rights and storage policy are explicit. A historical realization is not regenerated or copied by the initial bootstrap.

Regenerate the public latent-capacity train/validation realization and its `DatasetRealizationManifest` from the repository root with `python -m powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting`. The command writes deterministic JSONL under `data/synthetic/` and updates the tracked manifest under `data/manifests/realizations/`. Population, intervention/history and plan-horizon allocation, split membership, observation noise, and serialization order each have explicit seed ownership. State transitions have no process-noise stream.
