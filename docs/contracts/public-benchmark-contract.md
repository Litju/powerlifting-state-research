# Public benchmark contract

A benchmark is identifiable only when its scientific system, data, model-facing information, prediction target, evaluation, and claim boundary can be distinguished.

The public contract separates four records:

1. **Benchmark specification** — semantic identity and references to its world, population, intervention regime, observation model, dataset specification, task, quantity of interest, representation, evaluation, and claim scope.
2. **Dataset realization manifest** — one concrete generated or collected dataset, its provenance, replicate/seed information, split identities, row/entity counts, schema, coverage, and artifact hashes.
3. **Prediction record** — the information cutoff, any declared future plan visible at that origin, excluded future realized information, output quantities, entity/query identity, and missing/non-finite behavior.
4. **Evaluation result** — the benchmark and realization, prediction source, evaluation protocol, metrics, support, and claim scope.

A benchmark specification is independent of a random seed, one dataset realization, and any model checkpoint. The typed Python declarations in this repository are authoritative; JSON Schema files are generated interchange descriptions.
