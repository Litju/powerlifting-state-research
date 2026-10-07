# Synthetic

## Scope

Newly authored public synthetic realizations only.

## Data rules

Only newly generated public-safe synthetic realizations belong here. The public-native IID latent-capacity benchmark can be regenerated from a fresh public clone with `uv run --locked python scripts/verify_public_iid_production.py --check`. The verifier writes train and validation JSONL to a fresh temporary destination and checks the generated manifest against `data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json`.

The train and validation JSONL are Git-ignored and are not checked in. Their tracked manifest records the public-native DatasetSpec, package version, source and configuration digests, seed streams, schema, splits, checksums, origin, and CC BY 4.0 terms. This IID sampling design is distinct from the historical scrambled-Sobol design.

No historical private dataset is included. Every data artifact receives a per-artifact rights and provenance decision.
