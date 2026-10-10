# Latent-Origin Capacity-Change Forecasting

Benchmark version: latent_origin_capacity_change_forecasting@1.0.0

## Task, targets, and information boundary

Research question: At the forecast origin, using noisy pre-origin observations and the participant-visible declared dose/intensity plan, how accurately can a model forecast latent capacity change for three lifts at horizons 14, 28, and 56 days while keeping measurement noise in the inputs and out of target truth? This is conditional synthetic prediction, not a causal effect, latent-coordinate recovery, or human validity.

Task: LATENT_CAPACITY_CHANGE_FORECAST (latent_capacity_change_forecast). QOI: LATENT_CAPACITY_CHANGE (latent_capacity_change).

World: training_dose_history_capacity_dynamics. Synthetic capacity dynamics depend on training-dose history.

Sampling design: latent_origin_capacity_change_forecasting_sampling_design (DIRECT_HISTORICAL_IDENTITY).

Participant-visible boundary: Origin 224; dose-history observations through origin and complete declared future dose/intensity plan; future realized outcomes unavailable.

## Historical and identity context

Identity authority: HISTORICAL_PROJECTION; historical specimen: PARTIALLY_RECONSTRUCTED; qualification: NOT_QUALIFIED_OR_UNRESOLVED; completeness: PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS; public implementation: PUBLIC_IMPLEMENTATION_PENDING.

Benchmark identity: not minted; semantic digest: not minted.

Design context (descriptive only): One-axis estimand/label migration; same WORLD/observation/2,048 inputs/representation; TASK/QOI, labels, realization, and evaluation identity changed.

Historical lineage fields: parent specimen pl_response_v1_t0_public_2048; parentage status DIRECT_TARGET_MIGRATION; STRONG_ISOLATION.

Source version document: docs/benchmarks/latent-origin-capacity-change-forecasting.md

## Axis profile and applicability

The state shown here is the RES-277 profile snapshot before RES-281. Direct RES-281 axis findings and attack states remain in separate columns/tables; no axis score is computed.

| Axis | Applicable in profile | RES-277 profile state | RES-281 direct states | Missing evidence |
| --- | --- | --- | --- | --- |
| domain_faithfulness | Yes | UNSUPPORTED_BY_EVIDENCE | {} | ["Public row-level realization, executable audit adapter, and matching model/evaluation artifacts are not available for this historical version."] |
| reproducibility | Yes | UNSUPPORTED_BY_EVIDENCE | {} | ["Public row-level realization, executable audit adapter, and matching model/evaluation artifacts are not available for this historical version."] |
| leakage_shortcut_susceptibility | Yes | UNSUPPORTED_BY_EVIDENCE | {} | ["Public row-level realization, executable audit adapter, and matching model/evaluation artifacts are not available for this historical version.","Rights-cleared historical participant rows and split identities.","Version-specific runnable adapter and fitted model/evaluation artifacts."] |
| reconstructability | Yes | UNSUPPORTED_BY_EVIDENCE | {} | ["Public row-level realization, executable audit adapter, and matching model/evaluation artifacts are not available for this historical version."] |
| simple_model_frontier | Yes | UNSUPPORTED_BY_EVIDENCE | {} | ["Public row-level realization, executable audit adapter, and matching model/evaluation artifacts are not available for this historical version."] |
| ml_load_bearing_contribution | Yes | UNSUPPORTED_BY_EVIDENCE | {} | ["Public row-level realization, executable audit adapter, and matching model/evaluation artifacts are not available for this historical version."] |
| out_of_distribution_robustness | Yes | UNSUPPORTED_BY_EVIDENCE | {} | ["Public row-level realization, executable audit adapter, and matching model/evaluation artifacts are not available for this historical version.","Rights-cleared historical participant rows and split identities.","Version-specific runnable adapter and fitted model/evaluation artifacts."] |
| seed_stability | Yes | UNSUPPORTED_BY_EVIDENCE | {} | ["Public row-level realization, executable audit adapter, and matching model/evaluation artifacts are not available for this historical version."] |
| hidden_test_fairness | Yes | UNSUPPORTED_BY_EVIDENCE | {} | ["Public evidence does not establish whether a hidden/access-controlled test exists or document its split identity and access controls.","Rights-cleared historical participant rows and split identities.","Version-specific runnable adapter and fitted model/evaluation artifacts."] |
| audit_coverage | Yes | NOT_RUN | {} | [] |

## Executed audits and findings

Both frozen run bundles are listed without merging their result identities. Full diagnostics, missing-evidence lists, evidence references, and run IDs are in tables/attack-evidence-states.csv.

| Attack | RES-277 profile state | RES-278 state | RES-281 state | RES-281 finding |
| --- | --- | --- | --- | --- |
| audit_coverage_accounting@1.0.0 | NOT_RUN | PASS | PASS | Every registered attack has exactly one version-specific state, and the count reconciles to the typed contract and profile. Diagnostics: see run res281-audit_coverage_accounting-895a0af6733c and its result identity psr:audit-result:latent_origin_capacity_change_forecasting-audit_coverage_accounting@1.0.0~abdd2ad8b1b0. |
| baseline_domination@1.0.0 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | This benchmark version is outside the attack contract's declared semantic scope. |
| distributional_shift_sensitivity@1.0.0 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | This benchmark version is outside the attack contract's declared semantic scope. |
| hidden_test_fairness@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |
| model_ranking_instability@1.0.0 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | This benchmark version is outside the attack contract's declared semantic scope. |
| observation_noise_perturbation@1.0.0 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | This benchmark version is outside the attack contract's declared semantic scope. |
| parameter_seed_sensitivity@1.0.0 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | This benchmark version is outside the attack contract's declared semantic scope. |
| participant_input_leakage@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |
| reconstruction_provenance_gaps@1.0.0 | NOT_RUN | UNSUPPORTED_BY_EVIDENCE | INCONCLUSIVE | Public historical provenance metadata was audited. Unresolved identity links and unavailable original realization/model/evaluation artifacts prevent a full reconstruction decision. Diagnostics: see run res281-reconstruction_provenance_gaps-be16ebee0106 and its result identity psr:audit-result:latent_origin_capacity_change_forecasting-reconstruction_provenance_gaps@1.0.0~2285e293cd11. |
| shortcut_feature_dependence@1.0.0 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | This benchmark version is outside the attack contract's declared semantic scope. |
| sparse_missing_history_sensitivity@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |
| target_identity_contamination@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |
| temporal_history_disruption@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |
| training_plan_counterfactual_sensitivity@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |

## Available evidence and provenance

RES-281 evidence references: artifacts/registries/attack-contract-registry.json; artifacts/registries/benchmark-registry.json; artifacts/registries/validity-axis-registry.json; artifacts/registries/version-validity-profiles.json; docs/benchmarks/latent-origin-capacity-change-forecasting.md; src/powerlifting_state_research/provenance/historical_sources.py.

RES-283 model/evaluation evidence status: UNSUPPORTED_BY_EVIDENCE.

| Model family | Evidence status | Candidate count | Matched evidence | Source prediction-rights constraints |
| --- | --- | ---: | --- | --- |
| public-native-temporal-expert | UNSUPPORTED_BY_EVIDENCE | 0 | UNSUPPORTED_BY_EVIDENCE: no public historical rows, splits, fitted models, or predictions | Historical raw rows/checkpoints/outputs are not publicly redistributed; access and row-level rights evidence unavailable |
| compact_neural | UNSUPPORTED_BY_EVIDENCE | 0 | UNSUPPORTED_BY_EVIDENCE: no public historical rows, splits, fitted models, or predictions | Historical raw rows/checkpoints/outputs are not publicly redistributed; access and row-level rights evidence unavailable |
| mechanistic_midpoint | UNSUPPORTED_BY_EVIDENCE | 0 | UNSUPPORTED_BY_EVIDENCE: no public historical rows, splits, fitted models, or predictions | Historical raw rows/checkpoints/outputs are not publicly redistributed; access and row-level rights evidence unavailable |
| mechanistic_ridge_residual | UNSUPPORTED_BY_EVIDENCE | 0 | UNSUPPORTED_BY_EVIDENCE: no public historical rows, splits, fitted models, or predictions | Historical raw rows/checkpoints/outputs are not publicly redistributed; access and row-level rights evidence unavailable |
| context_mean | UNSUPPORTED_BY_EVIDENCE | 0 | UNSUPPORTED_BY_EVIDENCE: no public historical rows, splits, fitted models, or predictions | Historical raw rows/checkpoints/outputs are not publicly redistributed; access and row-level rights evidence unavailable |
| ridge | UNSUPPORTED_BY_EVIDENCE | 0 | UNSUPPORTED_BY_EVIDENCE: no public historical rows, splits, fitted models, or predictions | Historical raw rows/checkpoints/outputs are not publicly redistributed; access and row-level rights evidence unavailable |
| histogram_boosted_stumps | UNSUPPORTED_BY_EVIDENCE | 0 | UNSUPPORTED_BY_EVIDENCE: no public historical rows, splits, fitted models, or predictions | Historical raw rows/checkpoints/outputs are not publicly redistributed; access and row-level rights evidence unavailable |

RES-277 reproducibility profile state: UNSUPPORTED_BY_EVIDENCE. RES-281 direct reproduction: No direct RES-281 reproduction execution was recorded for this version.

RES-278 provenance-review state: UNSUPPORTED_BY_EVIDENCE (no run); RES-281 provenance-review state: INCONCLUSIVE (res281-reconstruction_provenance_gaps-be16ebee0106). These provenance-review states do not establish historical row-level reconstructability.

Reproducibility state and provenance are recorded independently. Public implementation status is PUBLIC_IMPLEMENTATION_PENDING; the presence of a specification or audit record does not assert reconstruction of unavailable private rows, model outputs, or checkpoints.

## Interpretation boundary

The audit state is bounded by the named version and evidence listed above. Missing, unsupported, not-run, and not-applicable results are not converted to favorable or unfavorable validity scores.
