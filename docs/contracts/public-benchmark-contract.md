# Public benchmark contract

A benchmark is identifiable only when its scientific system, data, model-facing information, prediction target, evaluation, and claim boundary can be distinguished.

The public contract separates four records:

1. **Benchmark specification** — semantic identity and references to its world, population, intervention regime, observation model, dataset specification, task, quantity of interest, representation, evaluation, and claim scope.
2. **Dataset realization manifest** — one concrete generated or collected dataset, its provenance, replicate/seed information, split identities, row/entity counts, schema, coverage, and artifact hashes.
3. **Prediction record** — the information cutoff, any declared future plan visible at that origin, excluded future realized information, output quantities, entity/query identity, and missing/non-finite behavior.
4. **Evaluation result** — the benchmark and realization, prediction source, evaluation protocol, metrics, support, and claim scope.

A benchmark specification is independent of a random seed, one dataset realization, and any model checkpoint. The typed Python declarations in this repository are authoritative; JSON Schema files describe record structure only. Semantic and cross-field invariants require the Python contract validator.

## Identity and generated schemas

The semantic digest binds the scientific-system configuration and member identities, dataset specification, task/QOIs, prediction-time information boundary, optional benchmark-defined representation, evaluation, declared shifts, and claim scope. It uses NFC-normalized compact UTF-8 JSON and SHA-256. Display names, aliases, paths, prose, realization seeds/content, models, training, checkpoints, results, environment, and hardware are excluded.

Incomplete historical mappings remain inspectable but have no mintable benchmark ID. The complete latent-capacity/transient-expression contract reproduces the frozen RES-268 digest: sha256:fbfbe59eb0a8e94b12b424c6d6837dfd455a6c5a55084bb2898b53f741cc6472. Dataset realization manifests have their own content-based identity.

Benchmark declarations state an identity authority. `HISTORICAL_PROJECTION` may retain `COMMITTED_BY_SYSTEM_CONFIG` where historical evidence lacks separately recovered component IDs. `PUBLIC_NATIVE` requires direct WORLD, POPULATION, INTERVENTION_REGIME, and OBSERVATION_MODEL identities. Authority metadata is not part of the semantic identity payload, preserving the frozen historical digest.

For `DatasetRealizationManifest`, `realization_digest` and `identity_id` cover the dataset-spec reference, realization slug, generator/source identity, seeds and replicates, counts, splits, content hashes, schema, temporal coverage, realized support, and observation availability. Free-text provenance and rights/license metadata do not change this scientific/content digest. They are included in `manifest_digest`, which hashes the complete manifest; changes to any manifest field change that full digest.

## Prediction and evaluation

Prediction inputs classify historical observations, static/context fields, and declared future plans. Future plans are allowed only when the task opts in. Future realized performance, observations, process disturbances, unknown intervention deviations, target-derived fields, and evaluation truth fail contract validation.

`contract-level information firewall != row-level temporal leakage validation`. The contract validates declared input kinds and cutoffs; checking actual row timestamps against them belongs with real dataset implementations in M3.

Evaluation reports RMSE, MAE, R², and SRE with population standard deviation (ddof=0) per target and original target units where applicable. Empty targets and constant-truth undefined metrics carry explicit statuses. Missing predictions and non-finite values follow declared reject-or-undefined policies; they are never dropped or imputed. Evaluation records keep aggregation, stratification, exclusions, uncertainty, and result status separate from metric calculation. There is no universal scalar leaderboard.

Metric result records distinguish historical-reported values, canonical research metrics, recomputed canonical values, and non-comparable values; a historical metric is never silently relabeled.

Shift records name changed and invariant axes, source and target, support relation, task/QOI, evaluation, hypothesis, and evidence. OOD alone is invalid. Direct comparison requires compatible QOIs, outputs, metrics/evaluation, and any required matched or stratified support. Observed-origin and latent-origin estimands cannot be ranked directly. A supplied common evaluation ID is checked for syntax and class only; verifying that it exists and was applied to both result sets belongs to the Benchmark Audit Suite or experiment orchestration layer.

Run python -m powerlifting_state_research.exports to regenerate the registry and schemas; add --check to detect drift.
