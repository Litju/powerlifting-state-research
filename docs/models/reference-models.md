# Models and comparator evidence

Historical model descriptions and independently fitted public-native comparators have different provenance. The [historical evidence lineage](../../artifacts/model-cards/historical-model-evidence-lineage.md) records what was recovered and what remains unavailable. No historical weights or private training rows are published.

## Frozen public-native IID panel

The [comparator card](../../artifacts/model-cards/public-native-comparator-suite.md) documents six new standardized families: plan-by-horizon context mean, Ridge on visible summaries, histogram boosted stumps, mechanistic midpoint, compact neural, and mechanistic midpoint plus Ridge residual. The [temporal-expert card](../../artifacts/model-cards/public-native-temporal-capacity-change.md) describes the separately trained lift-shared GRU, its three fitting seeds, and ensemble. These seven families have 22 candidate fitted-instance/ensemble identities; deterministic runs repeated under seed labels are not independent fits.

All use the same canonical IID validation rows and the canonical four-metric evaluation, but their representations, budgets, and hardware differ. The new comparators use an entity-disjoint internal split of TRAIN for fitting and allowed selection, with a fit seal before canonical validation. Participant inputs exclude target values, latent coordinates, IDs as features, and future realized information. The mechanistic comparator has declared generator knowledge; it is not a participant-only discovery of the world.

| Evidence | Canonical path |
| --- | --- |
| Comparator training contract | [Protocol](../../artifacts/training-protocols/public-native-comparator-suite.json) |
| Expert training contract | [Protocol](../../artifacts/training-protocols/public-native-temporal-expert.json) |
| Models, fits, prediction hashes, evaluations | [Comparator registry](../../artifacts/registries/public-native-comparator-registry.json), [comparator run](../../results/manifests/public-native-comparator-suite.json), [expert run](../../results/manifests/public-native-temporal-expert.json) |
| Per-seed, per-target metrics | [Frontier table](../../results/tables/public-native-comparator-frontier.csv) |
| Ranking, metric sensitivity, and Pareto comparisons | [Ranking-sensitivity report](../../results/audits/res283-analysis/res283-model-ranking-stability.md) |
| Publication and limitations | [Audit synthesis report](../../results/audits/res284-publication/report.md), [methods](../../results/audits/res284-publication/methods-limitations.md) |

The expert ensemble leads 11 of 12 target/metric point comparisons, with expert seed 383003 leading squat MAE. These are descriptive comparisons within one frozen realization. RMSE/MAE are in kg; R² and SRE(ddof=0) are unitless. On a fixed target population, R² and SRE are monotone transforms of RMSE, so these three metric orderings are not independent evidence. All 264 paired-uncertainty cells are unsupported because the ranking inputs lack validation truth and row-to-entity mapping. No universal ranking, statistical superiority, or real-athlete validity is established.

G1–G4 estimators have separate protocols and evaluation surfaces; see the [study overview](../studies/index.md). Their scores cannot be inserted into this IID panel.

## Availability and rights

Saved predictions, fitted comparator states, model identities, and aggregate evaluations are linked above. The [current artifact release](../../models/published/CURRENT_RELEASE.md) includes three public-native GRU checkpoints and all 30 representation-study fitted states; the [public verifier](../../scripts/verify_published_model_artifacts.py) checks their hashes and identities. CPU inference differs numerically from the original GPU temporal-model run within the recorded tolerance. The [prediction provenance clarification](../../provenance/RES-297-prediction-provenance-clarification.md) records authorization for the four already-public expert prediction files and explains their frozen `NOASSERTION` fallback. Dataset attribution and per-artifact notices remain applicable; historical World-V2 checkpoints and other private task artifacts remain excluded.

## Probabilistic forecasting studies

[Conditional scale, group calibration, support restriction and controlled shifts](../studies/probabilistic-capacity-forecasting.md) describe the completed later synthetic program, including both failed point corrections, small score gains, absolute shift degradation and conditional undercoverage. Methods are public; private scoring adapters, fitted uncertainty parameters and test evidence remain restricted.

The [normalization clarification](../../provenance/normalization-and-rights-clarification.md) records the known frozen metadata discrepancy. [Research positioning](../science/research-positioning.md) distinguishes mechanistic components from the data-driven GRU: the three-seed average is the demonstrated ensemble, and no trained cross-family stacking model is available.
