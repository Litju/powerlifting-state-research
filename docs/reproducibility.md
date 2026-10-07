# Reproducibility

Keep benchmark semantics, dataset realizations, models, predictions, and evaluations as separately identified objects.

A reproducible report records the package version, benchmark specification, generator and configuration identity, seed or replicate, data schema and checksums, split and temporal coverage, model and training protocol, prediction artifact, evaluation protocol, software environment, and result files. Regeneration should reproduce both the artifact and its declared identity.

Typed Python is the semantic source of truth. The benchmark registry JSON and JSON Schemas are generated exports. Large datasets and checkpoints are distributed or tracked only after their rights and storage policy are explicit. A historical realization is not regenerated or copied by the initial bootstrap.

Regenerate the public-native IID train/validation realization and its `DatasetRealizationManifest` from a fresh public clone with:

```sh
uv sync --locked --all-groups --python 3.12
uv run --locked python scripts/verify_public_iid_production.py --check
```

The verifier writes deterministic JSONL to a fresh temporary destination and fails unless its manifest matches the tracked canonical manifest. The source identity hashes the fixed public executable source set and generation configuration; documentation and tests do not participate. Population, intervention/history allocation, split membership, observation noise, and serialization order each have explicit seed ownership. The serialization seed cannot alter scientific row content.

The opt-in full-production pytest gate performs two complete generations and compares train and validation bytes and both manifests with the checked-in expectation. Full generation is intentionally excluded from ordinary PR CI.
