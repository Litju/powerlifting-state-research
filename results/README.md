# Results

## Scope

Output status and generated/committed policy.

## Output record

Commit generated outputs only when they are small, inspectable, reproducible, and have a documented source and license.

## PUBLIC_NATIVE temporal expert

The verified three-seed IID predictions and EvaluationResults are in [the PUBLIC_NATIVE result package](benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/public-native-temporal-expert/). Its run manifest, verification receipt, source inventory, and checksums are under [manifests](manifests/).

This evidence is separate from the historical scrambled-Sobol track. Do not rank their raw scores against each other. Preserve null, negative, and failed runs with their provenance.

## RES-275 standardized comparators

`results/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/public-native-comparator-suite/` contains the fit seal, internal split identity, canonical predictions, and RES-271 EvaluationResults for six newly trained comparators. `results/tables/public-native-comparator-frontier.csv` preserves per-seed and target-wise metrics, model complexity, and measured runtime. The checked-in RES-274 temporal-expert files remain immutable and are referenced by the comparator registry and checksum index.
