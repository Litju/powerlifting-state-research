# Reproducibility

Keep benchmark semantics, dataset realizations, models, predictions, and evaluations as separately identified objects.

A reproducible report records the package version, benchmark specification, generator and configuration identity, seed or replicate, data schema and checksums, split and temporal coverage, model and training protocol, prediction artifact, evaluation protocol, software environment, and result files. Regeneration should reproduce both the artifact and its declared identity.

Typed Python is the semantic source of truth. The benchmark registry JSON and JSON Schemas are generated exports. Large datasets and checkpoints are distributed or tracked only after their rights and storage policy are explicit. A historical realization is not regenerated or copied by the initial bootstrap.
