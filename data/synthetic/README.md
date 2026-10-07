# Synthetic

## Scope

Newly authored public synthetic realizations only.

## Data rules

Only newly generated public-safe synthetic realizations belong here. The public-native IID latent-capacity benchmark can be regenerated from the repository root with `python -m powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting`. It writes JSONL data here and a typed `DatasetRealizationManifest` to `data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json`.

The default train and validation bytes are not checked into Git. Their manifest records the public-native DatasetSpec, generator, fixed configuration and seed streams, schema, splits, checksums, and CC BY 4.0 terms. This IID sampling design is distinct from the historical scrambled-Sobol design.

No historical private dataset is included. Every data artifact receives a per-artifact rights and provenance decision.
