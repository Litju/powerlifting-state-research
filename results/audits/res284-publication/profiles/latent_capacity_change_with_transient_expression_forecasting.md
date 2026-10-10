# Latent Capacity-Change Forecasting with Transient Performance Expression

Benchmark version: latent_capacity_change_with_transient_expression_forecasting@1.0.0

## Task, targets, and information boundary

Research question: At day 224, given 32 weekly performance observations per lift through day 223, the declared future plan, and task-allowed context, can a model predict latent capacity change for three lifts at horizons 14, 28, and 56 days in a synthetic system that separates latent capacity from transient performance expression? This is conditional synthetic prediction, not human response, biological identification, intervention efficacy, or broad out-of-domain generalization.

Task: LATENT_CAPACITY_CHANGE_FORECAST (latent_capacity_change_forecast). QOI: LATENT_CAPACITY_CHANGE (latent_capacity_change).

World: latent_capacity_transient_performance_expression_dynamics. Separates chronic adaptation, latent capacity, and transient performance expression.

Sampling design: latent_capacity_change_with_transient_expression_forecasting_sampling_design (DIRECT_HISTORICAL_IDENTITY).

Participant-visible boundary: Cutoff day 224; 32 weekly observations/lift through day223 plus declared plan/context visible; latent coordinates, targets, future realized outcomes/observations hidden.

## Historical and identity context

Identity authority: HISTORICAL_PROJECTION; historical specimen: REPRODUCIBLE_SPEC; qualification: QUALIFIED_HISTORICAL; completeness: FULL_FROM_EXISTING_EVIDENCE; public implementation: PUBLIC_IMPLEMENTATION_PENDING.

Benchmark identity: psr:benchmark-spec:latent-capacity-change-with-transient-expression-forecasting@1.0.0~fbfbe59eb0a8; semantic digest: sha256:fbfbe59eb0a8e94b12b424c6d6837dfd455a6c5a55084bb2898b53f741cc6472.

Design context (descriptive only): New WORLD/system, composed population/intervention, observation, dataset and JSON representation; preserve QOI/TASK family, lifts/units/origin/horizons and SRE family.

Historical lineage fields: parent specimen pl_response_v1_t1_capacity_change; parentage status DIRECT_SCIENTIFIC_SUCCESSOR; MULTI_AXIS_CHANGE.

Source version document: docs/benchmarks/latent-capacity-change-with-transient-expression-forecasting.md

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
| audit_coverage_accounting@1.0.0 | NOT_RUN | PASS | PASS | Every registered attack has exactly one version-specific state, and the count reconciles to the typed contract and profile. Diagnostics: see run res281-audit_coverage_accounting-0a4eecc859ad and its result identity psr:audit-result:latent_capacity_change_with_transient_expression_forecasting-audit_coverage_accounting@1.0.0~e02dd4e11560. |
| baseline_domination@1.0.0 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | This benchmark version is outside the attack contract's declared semantic scope. |
| distributional_shift_sensitivity@1.0.0 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | This benchmark version is outside the attack contract's declared semantic scope. |
| hidden_test_fairness@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |
| model_ranking_instability@1.0.0 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | This benchmark version is outside the attack contract's declared semantic scope. |
| observation_noise_perturbation@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |
| parameter_seed_sensitivity@1.0.0 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | This benchmark version is outside the attack contract's declared semantic scope. |
| participant_input_leakage@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |
| reconstruction_provenance_gaps@1.0.0 | NOT_RUN | UNSUPPORTED_BY_EVIDENCE | INCONCLUSIVE | Public historical provenance metadata was audited. Unresolved identity links and unavailable original realization/model/evaluation artifacts prevent a full reconstruction decision. Diagnostics: see run res281-reconstruction_provenance_gaps-247bb0129556 and its result identity psr:audit-result:latent_capacity_change_with_transient_expression_forecasting-reconstruction_provenance_gaps@1.0.0~4d0f4bd2762c. |
| shortcut_feature_dependence@1.0.0 | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | This benchmark version is outside the attack contract's declared semantic scope. |
| sparse_missing_history_sensitivity@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |
| target_identity_contamination@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |
| temporal_history_disruption@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |
| training_plan_counterfactual_sensitivity@1.0.0 | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | UNSUPPORTED_BY_EVIDENCE | The question applies, but this historical version has no rights-cleared row-level realization and matching executable model/evaluation evidence. Missing: Rights-cleared historical participant rows and split identities.; Version-specific runnable adapter and fitted model/evaluation artifacts. |

## Available evidence and provenance

RES-281 evidence references: artifacts/registries/attack-contract-registry.json; artifacts/registries/benchmark-registry.json; artifacts/registries/validity-axis-registry.json; artifacts/registries/version-validity-profiles.json; docs/benchmarks/latent-capacity-change-with-transient-expression-forecasting.md; src/powerlifting_state_research/provenance/historical_sources.py.

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

RES-278 provenance-review state: UNSUPPORTED_BY_EVIDENCE (no run); RES-281 provenance-review state: INCONCLUSIVE (res281-reconstruction_provenance_gaps-247bb0129556). These provenance-review states do not establish historical row-level reconstructability.

Reproducibility state and provenance are recorded independently. Public implementation status is PUBLIC_IMPLEMENTATION_PENDING; the presence of a specification or audit record does not assert reconstruction of unavailable private rows, model outputs, or checkpoints.

## Interpretation boundary

The audit state is bounded by the named version and evidence listed above. Missing, unsupported, not-run, and not-applicable results are not converted to favorable or unfavorable validity scores.
