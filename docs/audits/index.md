# Benchmark validity audit contracts

RES-277 defines a versioned benchmark-of-benchmarks methodology. It separates validity questions from the benchmark's own prediction metrics and from the results of any future audit run. Each benchmark version gets its own axis and attack states. The suite has no overall validity score.

## Machine-readable contracts

The typed Python declarations are authoritative. Generated exports are:

- [Validity-axis registry](../../artifacts/registries/validity-axis-registry.json)
- [Attack-contract registry](../../artifacts/registries/attack-contract-registry.json)
- [Version-validity profiles](../../artifacts/registries/version-validity-profiles.json)
- [Audit schemas](../../artifacts/schemas/audit-spec.schema.json), [axis](../../artifacts/schemas/validity-axis.schema.json), [attack](../../artifacts/schemas/attack-spec.schema.json), [result](../../artifacts/schemas/audit-result.schema.json), [execution](../../artifacts/schemas/audit-execution.schema.json), [evidence artifact](../../artifacts/schemas/evidence-artifact-reference.schema.json), and [profile](../../artifacts/schemas/version-validity-profile.schema.json)

An `AuditSpec` is a versioned protocol nested under a `ValidityAxis`; it defines evidence, admissibility, method, input/output fields, diagnostics, decision criteria, limits, and missing-evidence handling. `AttackSpec` adds the attack's estimand, failure mode, benchmark-version scope, world/task semantics, permitted changes, and expected result schema. `AuditResult` records the six-state outcome. `AuditExecutionRecord` adds run configuration, hashed inputs and rights, audit-realization identity, and a detached result identity/hash. `VersionValidityProfile` remains a coverage snapshot bound to the benchmark selector and, where already minted, its existing benchmark ID and digest.

The profile selector `<benchmark_slug>@<version>` is a lookup key, not a replacement scientific identity. Six historical records do not have minted benchmark IDs; these contracts do not create any. Existing benchmark IDs, dataset realizations, evaluation definitions, and model identities remain unchanged.

## Validity axes

All ten axes can be considered for each registered version. An axis result may still be `NOT_APPLICABLE` when that version's semantics do not support the question. The exact questions, inputs, diagnostics, criteria, limits, and missing-evidence rules live in the axis registry.

| Axis | Scientific question and intended claim | Diagnostic and interpretation boundary |
|---|---|---|
| `domain_faithfulness` | Do the declared targets, observations, population, and interventions represent the stated benchmark domain? | Trace each construct through generation and evaluation. This does not establish real-athlete validity or physiological realism. |
| `reproducibility` | Can this exact version and its audit inputs be regenerated with identity-preserving provenance? | Repeat the declared generation and verify identities/hashes within a recorded environment. A different DatasetSpec or sampling design is not a reproduction. |
| `leakage_shortcut_susceptibility` | Can forbidden targets, identity, future information, or accidental proxies influence inputs or predictions? | Inspect dataflow and split grain; run paired key, history, and feature interventions. A schema review alone cannot establish row-level leakage absence. |
| `reconstructability` | Can the stated target/world behavior be rebuilt from evidence actually available to participants or auditors? | Keep participant-input reconstruction separate from structural access to a generator or hidden state. Reconstruction does not identify latent states or causal mechanisms. |
| `simple_model_frontier` | Has the claim been compared with credible simple, mechanistic, and reference models on the same evaluation surface? | Report target-wise Pareto dominance and trade-offs. A finite comparator set is not a universal optimum. |
| `ml_load_bearing_contribution` | Does a learned component add a predeclared contribution beyond matched simpler alternatives? | Use paired target-wise differences, uncertainty, and justified practical margins. Model size and predictive fit do not establish causal or physiological claims. |
| `out_of_distribution_robustness` | How do results change under named, admissible shifts from this version's distribution? | Pre-register each shift and report it separately. Named synthetic shifts do not establish broad or real-world robustness. |
| `seed_stability` | Do conclusions persist across declared data, split, fit, and initialization seeds? | Separate seed sources and report per-target spread and rank reversals. A small seed set cannot establish stability outside its protocol. |
| `hidden_test_fairness` | If a hidden/access-controlled test is claimed, are its identity, access, independence, and scoring fair under its declared population? | First establish that a hidden test exists. A public validation set is not a hidden-test claim; unknown access evidence is unsupported, not a pass. |
| `audit_coverage` | Does every applicable attack have an explicit state, evidence, and limitation? | Count states by version and axis. Coverage is process metadata, not benchmark validity. |

Quantitative diagnostics are target-wise and use a benchmark's existing evaluation identities where those metrics apply. Thresholds, equivalence margins, shifts, and relevant targets must be declared before looking at the audit outcomes. If no defensible threshold or uncertainty method exists, report `INCONCLUSIVE`; do not make one up after seeing the results.

The earlier audit taxonomy's `observability`, `structural_reconstructability`, and `public_surrogate_reconstructability` remain distinct subquestions under the new domain/reconstructability protocols. `representation_dependence` is covered by leakage/shortcut and load-bearing diagnostics; history cadence and intervention robustness are scoped under leakage and OOD robustness; model-ranking stability is part of seed stability. These concepts remain available as diagnostics without becoming extra top-level axes.

## Attack contracts and applicability

Every attack contract is marked `VALIDITY_ATTACK` and emits the `PSR_AUDIT_RESULT_V1` structure. It tests a stated failure mode. It does not replace, amend, or become a performance benchmark. A changed input or intervention is recorded against that version's native task, target, information boundary, and support.

The applicability sets below use `ALL-9`, `PLAN-4`, `OBSERVATION-2`, and `NATIVE-1`. Exact selectors are in the generated attack registry.

| Attack contract | Axis | Scope | Diagnostic |
|---|---|---|---|
| `participant_input_leakage` | Leakage/shortcut | ALL-9 | Remove/permute participant and row keys; inspect feature lineage and paired output invariance. |
| `target_identity_contamination` | Leakage/shortcut | ALL-9 | Trace target/future fields, verify split-grain separation, and use copied canary rows to test forbidden-field dependence. |
| `shortcut_feature_dependence` | Leakage/shortcut | NATIVE-1 | Ablate or conditionally perturb a pre-identified suspect feature on paired rows. |
| `temporal_history_disruption` | Leakage/shortcut | ALL-9 | Check cutoff adherence and predeclared truncation/cadence/chronology interventions. |
| `training_plan_counterfactual_sensitivity` | OOD robustness | PLAN-4 | Change only a supported declared plan, regenerate its target under the same native world, and compare paired responses. |
| `observation_noise_perturbation` | OOD robustness | OBSERVATION-2 | Hold latent target/history/plan fixed and compare fresh draws under the same declared observation law. |
| `sparse_missing_history_sensitivity` | OOD robustness | ALL-9 | Apply predeclared history thinning or masks; distinguish in-support missingness from stress extensions. |
| `distributional_shift_sensitivity` | OOD robustness | NATIVE-1 | Apply one predeclared, supported native-generator shift at a time and report each shift separately. |
| `parameter_seed_sensitivity` | Seed stability | NATIVE-1 | Separate predeclared fit seeds/settings on fixed data and split; do not tune on final evaluation. |
| `baseline_domination` | Simple-model frontier | NATIVE-1 | Compare existing matched results target-wise and retain Pareto trade-offs; do not train or rescore for RES-277. |
| `model_ranking_instability` | Seed stability | NATIVE-1 | Estimate within-version paired ranking variation from eligible per-row or per-seed outputs. |
| `reconstruction_provenance_gaps` | Reconstructability | ALL-9 | Verify provenance edges, identities, rights, and artifact hashes; report missing links. |
| `hidden_test_fairness` | Hidden-test fairness | ALL-9, conditional | Check split identity, access chronology, group separation, model sealing, and score coverage only if a hidden test is claimed. |
| `audit_coverage_accounting` | Audit coverage | ALL-9 | Reconcile every registered attack to exactly one state and report counts without weighting them into a score. |

`PLAN-4` is the IID public-native capacity-change version plus the historical capacity-change, latent-origin, and observed-origin formulations, all of which declare a future plan visible. `OBSERVATION-2` is the public-native and historical capacity-change version for which this repository has the matching public observation/generator adapters. `NATIVE-1` is `iid_latent_capacity_change_with_transient_expression_forecasting@1.0.0`, where public model/prediction artifacts exist. Other attacks are not presumed executable on all historical versions merely because their scientific question is relevant.

## Result states

| State | Meaning | Required interpretation |
|---|---|---|
| `PASS` | An admissible audit run meets all predeclared criteria for its bounded claim. | Cite evidence, run ID, source commit, and diagnostics. Does not generalize beyond the claim. |
| `FAIL` | An admissible run demonstrates that the bounded claim fails a predeclared criterion. | Preserve negative evidence and scope; it does not invalidate unrelated claims or the benchmark's task definition. |
| `INCONCLUSIVE` | The attack ran, but evidence, precision, uncertainty, or competing outcomes do not resolve the criterion. | Preserve the run and state what would resolve it. |
| `NOT_APPLICABLE` | The attack's semantic precondition is false for this version by design. | Cite the version evidence that makes the question inapplicable. |
| `NOT_RUN` | The attack applies and its evidence is available or planned, but no audit run occurred. | Do not describe as a negative result or as evidence of validity. |
| `UNSUPPORTED_BY_EVIDENCE` | The question applies, but required data, adapter, access, permission, or provenance is unavailable. | Cite the evidence reviewed and name each gap; do not convert a gap into a pass. |

Executed `PASS`, `FAIL`, and `INCONCLUSIVE` records require evidence references, a run ID, and the source commit. `PASS`/`FAIL` also require diagnostics. `NOT_RUN`, `NOT_APPLICABLE`, and `UNSUPPORTED_BY_EVIDENCE` cannot carry measured diagnostics; unsupported records must name missing evidence. A profile is a coverage snapshot, not a bundle of executed results.

No state is averaged, ranked, weighted, or converted to a universal scalar validity score. Coverage fractions may describe the audit process only.

## Current profiles and public-safe evidence examples

The checked-in [version-validity profiles](../../artifacts/registries/version-validity-profiles.json) contain no invented audit measurements or `PASS`/`FAIL` findings:

- The public-native version is `NOT_RUN` on its applicable axes and attacks. Its hidden-test fairness state is `NOT_APPLICABLE` because it makes no hidden-test claim. The profile links the frozen [IID realization manifest](../../data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json), [public-native comparator registry](../../artifacts/registries/public-native-comparator-registry.json), and [per-seed target-wise table](../../results/tables/public-native-comparator-frontier.csv) as possible inputs. Those M3/M4 artifacts are not RES-277 findings.
- Each historical version records `UNSUPPORTED_BY_EVIDENCE` for applicable attacks that need unavailable public rows, adapters, model outputs, or access records. The metadata-only provenance and coverage attacks are `NOT_RUN`; attacks outside their declared scope are `NOT_APPLICABLE`. No private historical data or checkpoints are copied into the repository.
- The historical scrambled-Sobol and public-native IID sampling designs retain their separate DatasetSpec and evaluation semantics. Their raw scores are never used as a direct shift or ranking comparison.

The profile records the existing `benchmark_id` and semantic digest when one is already minted. It leaves both null for unresolved historical records; no scientific identity is inferred from a slug.

## RES-278 executor

Run `uv run --locked python -m powerlifting_state_research.audits.runner --check` to reconcile the typed contracts, checked-in registries, profile selectors, cited files, public rights ledger, and M4 comparator artifacts without writing. Run `uv run --locked python -m powerlifting_state_research.audits.runner` to execute the supported subset and write a deterministic bundle under `results/audits/res278/`. The output directory must be new; the writer is restricted to `results/audits/`.

The first executed ledger is [audit-results.json](../../results/audits/res278/audit-results.json); its detached [artifact index](../../results/audits/res278/audit-results.manifest.json) binds the result and realization file hashes.

The execution bundle uses the six RES-277 states and records one attack state for each registered attack and benchmark version. Executed records bind the AttackSpec and AuditSpec versions, benchmark and available task/QOI/evaluation identities, DatasetSpec/realization identities, source commit, configuration and seed, hashed inputs, permitted intervention, audit-realization identity/hash, diagnostics, decision criteria, limitations, and a detached result identity/hash. The sidecar index binds the bundle and realization file bytes.

The public-native adapter reads the frozen M4 comparator registry, checksums, fit seal, fitted states, prediction JSONL, and RES-271 EvaluationResults. It runs copied-row key and target-canary checks, chronology disruption, supported plan counterfactuals, and fresh observation-noise draws through the saved comparator inference code. It uses existing per-seed artifacts for target-wise frontier and ranking diagnostics. It does not fit models or rewrite canonical artifacts. Historical versions remain metadata-only and unsupported when rights-cleared rows, adapters, or matched model/evaluation artifacts are absent. Sparse-history and distribution-shift runs also remain unsupported where the native schema or declarations provide no admissible adapter.

Generated stress rows use fresh seeds and separate DatasetRealization manifests. Their outputs and audit results live under `results/audits/`; canonical M3/M4 data, predictions, fitted states, evaluations, and identities are read-only inputs. Frontier, seed, and rank observations are descriptive and inconclusive without predeclared practical margins or uncertainty methods. Historical scrambled-Sobol and public-native IID scores remain non-comparable unless the existing comparability contract proves otherwise.
