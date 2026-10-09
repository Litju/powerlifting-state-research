"""Versioned scientific contracts for cross-benchmark validity audits."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from ..contracts.serialization import require_benchmark_digest_match
from ..registry import BENCHMARKS

CONTRACT_VERSION = "1.0.0"
RESULT_SCHEMA_VERSION: Literal["PSR_AUDIT_RESULT_V1"] = "PSR_AUDIT_RESULT_V1"
BENCHMARK_VERSIONS = tuple(f"{item.slug}@{item.version}" for item in BENCHMARKS)
PUBLIC_NATIVE_VERSION = "iid_latent_capacity_change_with_transient_expression_forecasting@1.0.0"
PLAN_VISIBLE_VERSIONS = tuple(
    f"{slug}@1.0.0"
    for slug in (
        "iid_latent_capacity_change_with_transient_expression_forecasting",
        "latent_capacity_change_with_transient_expression_forecasting",
        "latent_origin_capacity_change_forecasting",
        "observed_origin_referenced_capacity_change_forecasting",
    )
)
OBSERVATION_MODEL_VERSIONS = tuple(
    f"{slug}@1.0.0"
    for slug in (
        "iid_latent_capacity_change_with_transient_expression_forecasting",
        "latent_capacity_change_with_transient_expression_forecasting",
    )
)
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class AuditStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_RUN = "NOT_RUN"
    UNSUPPORTED_BY_EVIDENCE = "UNSUPPORTED_BY_EVIDENCE"


DiagnosticValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class AuditSpec:
    """Axis-level protocol, separate from any run or result."""

    version: str
    required_evidence: tuple[str, ...]
    admissibility_conditions: tuple[str, ...]
    methodology: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    quantitative_diagnostics: tuple[str, ...]
    pass_criteria: tuple[str, ...]
    fail_criteria: tuple[str, ...]
    inconclusive_criteria: tuple[str, ...]
    interpretation_boundaries: tuple[str, ...]
    limitations: tuple[str, ...]
    missing_evidence_handling: str
    expected_output_schema: Literal["PSR_AUDIT_RESULT_V1"] = RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.expected_output_schema != RESULT_SCHEMA_VERSION:
            raise ValueError("audit specification uses an unknown output schema")
        if not all(
            (
                self.version,
                self.required_evidence,
                self.admissibility_conditions,
                self.methodology,
                self.inputs,
                self.outputs,
                self.pass_criteria,
                self.fail_criteria,
                self.inconclusive_criteria,
                self.interpretation_boundaries,
                self.limitations,
                self.missing_evidence_handling.strip(),
            )
        ):
            raise ValueError("audit specification is incomplete")


@dataclass(frozen=True, slots=True)
class ValidityAxis:
    slug: str
    version: str
    scientific_question: str
    intended_claim: str
    applicable_benchmark_versions: tuple[str, ...]
    audit_spec: AuditSpec
    attack_spec_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all((self.slug, self.version, self.scientific_question, self.intended_claim)):
            raise ValueError("validity axis is incomplete")
        if not self.applicable_benchmark_versions:
            raise ValueError("validity axis needs explicit benchmark-version applicability")
        if len(set(self.applicable_benchmark_versions)) != len(self.applicable_benchmark_versions):
            raise ValueError("validity axis has duplicate benchmark versions")

    @property
    def purpose(self) -> str:
        """Retain the pre-RES-277 display field for existing audit index consumers."""
        return self.intended_claim


@dataclass(frozen=True, slots=True)
class AttackSpec:
    slug: str
    version: str
    axis_slug: str
    estimand: str
    target_failure_mode: str
    applicable_benchmark_versions: tuple[str, ...]
    world_task_semantics: tuple[str, ...]
    permitted_interventions: tuple[str, ...]
    required_evidence: tuple[str, ...]
    admissibility_conditions: tuple[str, ...]
    methodology: tuple[str, ...]
    inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    quantitative_diagnostics: tuple[str, ...]
    interpretation_boundaries: tuple[str, ...]
    limitations: tuple[str, ...]
    missing_evidence_handling: str
    expected_output_schema: Literal["PSR_AUDIT_RESULT_V1"] = RESULT_SCHEMA_VERSION
    study_kind: Literal["VALIDITY_ATTACK"] = "VALIDITY_ATTACK"

    def __post_init__(self) -> None:
        if (
            self.expected_output_schema != RESULT_SCHEMA_VERSION
            or self.study_kind != "VALIDITY_ATTACK"
        ):
            raise ValueError("attack specification must emit the validity-audit result schema")
        if not all(
            (
                self.slug,
                self.version,
                self.axis_slug,
                self.estimand.strip(),
                self.target_failure_mode.strip(),
                self.applicable_benchmark_versions,
                self.world_task_semantics,
                self.required_evidence,
                self.admissibility_conditions,
                self.methodology,
                self.inputs,
                self.expected_outputs,
                self.interpretation_boundaries,
                self.limitations,
                self.missing_evidence_handling.strip(),
            )
        ):
            raise ValueError("attack specification is incomplete")
        if len(set(self.applicable_benchmark_versions)) != len(self.applicable_benchmark_versions):
            raise ValueError("attack specification has duplicate benchmark versions")

    @property
    def reference(self) -> str:
        return f"{self.slug}@{self.version}"


@dataclass(frozen=True, slots=True)
class AuditResult:
    """A machine-readable execution or explicit non-execution record."""

    benchmark_version: str
    axis_slug: str
    axis_spec_version: str
    status: AuditStatus
    status_reason: str
    benchmark_id: str | None = None
    semantic_digest: str | None = None
    attack_spec_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    diagnostics: dict[str, DiagnosticValue] = field(default_factory=dict)
    missing_evidence: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    run_id: str | None = None
    source_commit: str | None = None
    result_artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, AuditStatus):
            raise ValueError("audit result uses an unknown status")
        if not all((self.benchmark_version, self.axis_slug, self.axis_spec_version)):
            raise ValueError("audit result needs benchmark, axis, and specification versions")
        if not self.status_reason.strip():
            raise ValueError("audit result needs a reason")
        if (self.benchmark_id is None) != (self.semantic_digest is None):
            raise ValueError("audit result benchmark ID and digest must be present together")
        if self.benchmark_id is not None and self.semantic_digest is not None:
            require_benchmark_digest_match(
                self.benchmark_id, self.semantic_digest, "audit result benchmark"
            )
        for name, value in self.diagnostics.items():
            if not name:
                raise ValueError("diagnostic names must be non-empty")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("audit diagnostics must be finite or null")

        executed = self.status in (AuditStatus.PASS, AuditStatus.FAIL, AuditStatus.INCONCLUSIVE)
        has_execution_provenance = self.run_id is not None and self.source_commit is not None
        if (self.run_id is None) != (self.source_commit is None):
            raise ValueError("audit run ID and source commit must be recorded together")
        if executed and (
            not self.evidence_refs
            or not has_execution_provenance
            or not _COMMIT.fullmatch(self.source_commit or "")
        ):
            raise ValueError("executed audit results need evidence, run ID, and source commit")
        if not executed and has_execution_provenance:
            raise ValueError("non-execution states cannot claim run provenance")
        if self.result_artifact_sha256 is not None and not _SHA256.fullmatch(
            self.result_artifact_sha256
        ):
            raise ValueError("audit result artifact hash must be a full SHA-256 digest")
        if self.status is AuditStatus.UNSUPPORTED_BY_EVIDENCE and (
            not self.missing_evidence or not self.evidence_refs
        ):
            raise ValueError("unsupported audit result must cite evidence and name the gap")
        if self.status is AuditStatus.NOT_APPLICABLE and not self.evidence_refs:
            raise ValueError("not-applicable audit result must cite the semantic condition")
        if self.status is not AuditStatus.UNSUPPORTED_BY_EVIDENCE and self.missing_evidence:
            raise ValueError("missing evidence belongs in UNSUPPORTED_BY_EVIDENCE")
        if (
            self.status
            in (
                AuditStatus.NOT_APPLICABLE,
                AuditStatus.NOT_RUN,
                AuditStatus.UNSUPPORTED_BY_EVIDENCE,
            )
            and self.diagnostics
        ):
            raise ValueError("non-execution states cannot report measured diagnostics")
        if self.status in (AuditStatus.PASS, AuditStatus.FAIL) and not self.diagnostics:
            raise ValueError("PASS and FAIL require recorded diagnostics")


@dataclass(frozen=True, slots=True)
class VersionValidityProfile:
    profile_version: str
    benchmark_slug: str
    benchmark_version: str
    benchmark_id: str | None
    semantic_digest: str | None
    axis_results: tuple[AuditResult, ...]
    attack_results: tuple[AuditResult, ...]

    def __post_init__(self) -> None:
        if not all((self.profile_version, self.benchmark_slug, self.benchmark_version)):
            raise ValueError("validity profile needs a benchmark version")
        if (self.benchmark_id is None) != (self.semantic_digest is None):
            raise ValueError("benchmark ID and semantic digest must be present together")
        if self.benchmark_id is not None and self.semantic_digest is not None:
            require_benchmark_digest_match(
                self.benchmark_id, self.semantic_digest, "validity profile benchmark"
            )
        axes = tuple(result.axis_slug for result in self.axis_results)
        if len(axes) != len(set(axes)):
            raise ValueError("validity profile has duplicate axis results")
        if any(
            result.benchmark_version != f"{self.benchmark_slug}@{self.benchmark_version}"
            for result in (*self.axis_results, *self.attack_results)
        ):
            raise ValueError("validity profile record references a different benchmark version")
        if any(
            (result.benchmark_id, result.semantic_digest)
            != (self.benchmark_id, self.semantic_digest)
            for result in (*self.axis_results, *self.attack_results)
        ):
            raise ValueError("validity profile and audit result scientific identities differ")
        if any(len(result.attack_spec_refs) != 1 for result in self.attack_results):
            raise ValueError("attack result must reference exactly one attack contract")
        attack_refs = tuple(result.attack_spec_refs[0] for result in self.attack_results)
        if len(attack_refs) != len(set(attack_refs)):
            raise ValueError("validity profile has duplicate attack results")


VALIDITY_AXES: tuple[ValidityAxis, ...] = (
    ValidityAxis(
        "domain_faithfulness",
        CONTRACT_VERSION,
        "Do the declared target, observation process, population, and interventions represent the stated benchmark domain?",
        "The benchmark is faithful to its explicitly bounded synthetic or public-native domain claims.",
        BENCHMARK_VERSIONS,
        AuditSpec(
            CONTRACT_VERSION,
            (
                "Versioned task, target, world, population, observation, intervention, and dataset declarations.",
                "Source-to-code trace for every public implementation claim.",
            ),
            (
                "Use each benchmark's native DatasetSpec and task semantics.",
                "External-athlete claims require independently sourced and rights-cleared external evidence.",
            ),
            (
                "Trace each stated construct through generation, participant-visible fields, target creation, and evaluation.",
                "Compare implementation behavior only with the same version's declaration and support.",
            ),
            (
                "Benchmark version and semantic references.",
                "Public generator, task and observation definitions, and any external domain evidence.",
            ),
            (
                "Construct-to-code/data mapping.",
                "Supported claims, contradictions, and unresolved assumptions.",
            ),
            (
                (
                    "Coverage of declared constructs and target/input mappings, when the mapping is enumerable.",
                )
            ),
            (
                (
                    "Every in-scope claim has an admissible trace and no material contradiction is found.",
                )
            ),
            (("An admissible trace contradicts a declared in-scope construct or target meaning.",)),
            (
                (
                    "Source descriptions are partial, competing, or do not resolve a construct-to-code claim.",
                )
            ),
            (
                (
                    "A synthetic powerlifting world is not evidence of real-athlete validity, causal effects, or physiology.",
                )
            ),
            (
                (
                    "Domain correspondence depends on the declared world and external evidence; fidelity is not a scalar.",
                )
            ),
            "List each missing source, measurement, or external evidence item; never infer real-athlete validity from synthetic performance.",
        ),
        (),
    ),
    ValidityAxis(
        "reproducibility",
        CONTRACT_VERSION,
        "Can the exact benchmark version and its eligible audit inputs be regenerated with identity-preserving provenance?",
        "The declared dataset and evaluation artifacts can be regenerated or independently verified within the stated environment and version.",
        BENCHMARK_VERSIONS,
        AuditSpec(
            CONTRACT_VERSION,
            (
                (
                    "Canonical benchmark, DatasetSpec, realization, evaluation, generator/source, seeds, environment, and artifact hashes.",
                )
            ),
            (
                "Regenerate only the selected version and its own declared sampling design.",
                "Compare the same realization and evaluation identity.",
            ),
            (
                "Repeat the declared generation and evaluation-input export in a clean recorded environment.",
                "Check semantic identities, row/key coverage, split identity, and exact hashes where byte identity is promised.",
            ),
            (
                "Versioned source and dependency lock.",
                "Declared seeds and realization inputs.",
                "Expected public manifest and regenerated artifacts.",
            ),
            (
                (
                    "Reproduction receipt, identity comparisons, hash differences, and environment record.",
                )
            ),
            (
                (
                    "Exact artifact/hash agreement where promised; identity-level agreement for explicitly serialization-different outputs.",
                )
            ),
            (
                (
                    "All required outputs match their declared identity and the reproduction receipt is complete.",
                )
            ),
            (
                (
                    "A repeatable mismatch violates a frozen identity or declared deterministic output.",
                )
            ),
            (
                (
                    "Environment drift, incomplete output, or unexplained variation prevents a decision.",
                )
            ),
            (
                (
                    "Reproducibility is scoped to declared artifacts and environments, not scientific truth.",
                )
            ),
            (
                (
                    "Serialization equality is not required unless declared; historical scrambled-Sobol and public-native IID realizations are distinct.",
                )
            ),
            "Mark a version UNSUPPORTED_BY_EVIDENCE when required source, realization, seed, or provenance inputs are unavailable; do not substitute a related version.",
        ),
        (),
    ),
    ValidityAxis(
        "leakage_shortcut_susceptibility",
        CONTRACT_VERSION,
        "Can prohibited targets, identity fields, future information, or non-scientific shortcuts influence model inputs or predictions?",
        "Participant-visible information respects the versioned prediction boundary and any residual shortcut dependence is disclosed.",
        BENCHMARK_VERSIONS,
        AuditSpec(
            CONTRACT_VERSION,
            (
                (
                    "Versioned input/output schema, prediction-time cutoff, split/group identities, and fitted preprocessing/model artifacts.",
                )
            ),
            (
                "Use copies of public-safe data and fitted artifacts.",
                "Do not open held-out truth for tuning or rewrite a frozen benchmark identity.",
            ),
            (
                "Inspect schemas and feature lineage for forbidden target/future fields.",
                "Test key and suspicious-feature invariance/ablation on paired rows.",
                "Check split overlap at the declared entity/group grain.",
            ),
            (
                (
                    "Permitted participant-visible inputs, targets for final scoring only, split metadata, and a sealed fitted model.",
                )
            ),
            (
                (
                    "Forbidden-field reads, split overlap, invariance/ablation effects, and target-wise paired score changes.",
                )
            ),
            (
                (
                    "Overlap counts, exact invariance violations, and target-wise paired metric deltas with uncertainty.",
                )
            ),
            (
                (
                    "No prohibited information crosses the declared boundary and all required invariance checks meet pre-registered tolerances.",
                )
            ),
            (
                (
                    "Any prohibited target/future access or an admissible material shortcut dependence contradicts the claim.",
                )
            ),
            (
                (
                    "Missing feature lineage, inaccessible preprocessing, or uncertain group identity blocks attribution.",
                )
            ),
            (
                (
                    "A score change after ablation identifies dependence under that intervention, not the causal effect of the feature in athletes.",
                )
            ),
            (
                (
                    "Ablation may create out-of-support inputs; label such results separately and do not interpret them as ordinary test performance.",
                )
            ),
            "Without row-level inputs, split keys, and the sealed model path, report UNSUPPORTED_BY_EVIDENCE; never infer leakage absence from a schema alone.",
        ),
        (
            "participant_input_leakage@1.0.0",
            "target_identity_contamination@1.0.0",
            "shortcut_feature_dependence@1.0.0",
            "temporal_history_disruption@1.0.0",
        ),
    ),
    ValidityAxis(
        "reconstructability",
        CONTRACT_VERSION,
        "Can the declared target, public-facing behavior, or specified world output be reconstructed from the evidence actually available to participants?",
        "A reconstruction claim is reproducible at its declared information level and its remaining unidentifiable components are explicit.",
        BENCHMARK_VERSIONS,
        AuditSpec(
            CONTRACT_VERSION,
            (
                (
                    "Complete source/dependency lineage, public input schema, target definition, realization reference, and reconstruction implementation/output.",
                )
            ),
            (
                "Separate reconstruction from participant-public inputs from structural access to a generator or hidden state.",
                "Compare only on matched inputs, targets, support, and output units.",
            ),
            (
                "Rebuild the smallest declared target/world behavior from its admissible inputs.",
                "Compare exact outputs for deterministic identities, or pre-specified tolerances for numerical implementations.",
                "Record provenance and every unavailable dependency.",
            ),
            (
                (
                    "Source declarations, public input artifacts, reconstruction code, and canonical comparison outputs.",
                )
            ),
            (
                (
                    "Reconstruction method, paired output differences, provenance chain, and unresolved dependencies.",
                )
            ),
            (
                (
                    "Exact-match rate or target-wise absolute/relative error under a predeclared tolerance.",
                )
            ),
            (
                (
                    "The specified reconstruction level is supported by complete provenance and meets its predeclared comparison rule.",
                )
            ),
            (
                (
                    "A reproducible mismatch exceeds the declared tolerance or a required provenance link is false.",
                )
            ),
            (("Partial sources, missing inputs, or no justified tolerance prevent a decision.",)),
            (
                (
                    "Reconstructing a target from its inputs does not identify latent states or validate causal/physiological mechanisms.",
                )
            ),
            (
                (
                    "A sufficiently expressive reconstruction may exploit target-sufficient shortcuts; structural and public-input reconstruction remain distinct.",
                )
            ),
            "Name each missing source, data artifact, or rights-cleared dependency; do not reconstruct historical private data or checkpoints into Git.",
        ),
        ("reconstruction_provenance_gaps@1.0.0",),
    ),
    ValidityAxis(
        "simple_model_frontier",
        CONTRACT_VERSION,
        "Has the benchmark been compared with a credible frontier of simple, mechanistic, and reference predictors on the same evaluation surface?",
        "The reported prediction claim is interpreted relative to declared strong non-ML/reference baselines and target-wise trade-offs.",
        BENCHMARK_VERSIONS,
        AuditSpec(
            CONTRACT_VERSION,
            (
                (
                    "Matched target-wise predictions, common split and evaluation identity, model/input declarations, and fitted-state provenance.",
                )
            ),
            (
                "Compare only models evaluated on the same version, rows, target definitions, information boundary, and metric implementation.",
                "Pre-register reference classes and practical margins.",
            ),
            (
                "Construct a target-wise metric frontier from predeclared constant, context, linear, mechanistic, and other justified simple references.",
                "Report paired uncertainty and Pareto dominance; retain incomparable trade-offs.",
            ),
            (
                (
                    "Existing public-safe predictions/results and their frozen model/protocol registries.",
                )
            ),
            (("Per-target frontier table, dominant models, metric trade-offs, and uncertainty.",)),
            (
                (
                    "Paired target-wise RMSE/MAE/R²/SRE where canonically defined; Pareto dominance and paired intervals.",
                )
            ),
            (
                (
                    "The declared reference set is complete for its claim and no simple reference materially dominates the claimed frontier under preregistered margins.",
                )
            ),
            (
                (
                    "A predeclared simple reference dominates the claimed method on all decision-relevant metrics/targets beyond the declared margin.",
                )
            ),
            (
                (
                    "Targets or metrics cross, uncertainty spans the margin, or baseline coverage is incomplete.",
                )
            ),
            (
                (
                    "A finite comparator set is not a universal optimum; benchmark validity does not depend on a preferred model winning.",
                )
            ),
            (
                (
                    "No cross-version raw-score ranking without a positive comparability determination.",
                )
            ),
            "If matched predictions, metrics, or a model's public provenance are absent, report UNSUPPORTED_BY_EVIDENCE rather than estimating them.",
        ),
        ("baseline_domination@1.0.0",),
    ),
    ValidityAxis(
        "ml_load_bearing_contribution",
        CONTRACT_VERSION,
        "Does the learned component add a predeclared, reproducible prediction contribution beyond strong simpler alternatives?",
        "Any claimed learned-method contribution is incremental to matched baselines under the declared finite benchmark support.",
        BENCHMARK_VERSIONS,
        AuditSpec(
            CONTRACT_VERSION,
            (
                (
                    "Sealed learned and reference predictions, matched training/evaluation protocol, target-wise metrics, and model provenance.",
                )
            ),
            (
                "Do not infer contribution from model size, architecture, or in-sample fit.",
                "Pre-register equivalence/practical margins and comparison targets.",
            ),
            (
                "Use paired target-wise differences against the strongest admissible simple/reference method.",
                "Use ablation or controlled fit comparisons only when fit protocol and inputs remain matched.",
            ),
            (
                (
                    "Existing evaluation artifacts, fit seals, model specifications, and per-seed results.",
                )
            ),
            (
                (
                    "Incremental target-wise contribution, uncertainty, selected targets, and limitations.",
                )
            ),
            (
                (
                    "Paired metric deltas, confidence intervals, seed-level replication, and Pareto non-dominance.",
                )
            ),
            (
                (
                    "A predeclared learned contribution exceeds the practical margin on the declared targets with uncertainty support and no protocol leakage.",
                )
            ),
            (
                (
                    "A simple/reference method is equivalent within a justified margin or dominates the learned method on all claimed outcomes.",
                )
            ),
            (
                (
                    "No practical margin, insufficient independent runs, or conflicting target-wise effects leaves contribution unresolved.",
                )
            ),
            (
                (
                    "Predictive contribution does not show causal identification, real-athlete validity, or physiological realism.",
                )
            ),
            (
                (
                    "One benchmark, split, and model family cannot establish a general benefit of machine learning.",
                )
            ),
            "Do not train or rescore to fill gaps in RES-277; use existing public-safe evidence or report the unsupported requirement.",
        ),
        (),
    ),
    ValidityAxis(
        "out_of_distribution_robustness",
        CONTRACT_VERSION,
        "How do predictions and claims change under predeclared shifts from the version's training/evaluation distribution?",
        "Robustness is characterized for named, admissible shifts and does not imply performance on unspecified domains.",
        BENCHMARK_VERSIONS,
        AuditSpec(
            CONTRACT_VERSION,
            (
                (
                    "Version-specific support, train/evaluation identities, shift declaration or public generator intervention, and target-wise predictions.",
                )
            ),
            (
                "Pre-register shift operator, direction, magnitude, and in/out-of-support status.",
                "Preserve task, target, and information boundary unless the attack explicitly changes one.",
            ),
            (
                "Evaluate each shift separately on held-out shifted rows or valid paired counterfactuals.",
                "Report response curves/strata and uncertainty; never fold shifts into a single validity score.",
            ),
            (
                (
                    "Frozen model, public generator/data adapter, declared shift semantics, and matched scoring inputs.",
                )
            ),
            (
                (
                    "Shift-specific target-wise performance changes, support notes, and failure cases.",
                )
            ),
            (
                (
                    "Target-wise RMSE/MAE/R²/SRE deltas, calibration/residual changes when defined, and per-shift uncertainty.",
                )
            ),
            (
                (
                    "All named in-scope shifts meet their predeclared practical criteria with supported uncertainty.",
                )
            ),
            (
                (
                    "A declared in-scope shift reproducibly exceeds its predeclared degradation bound.",
                )
            ),
            (
                (
                    "Shift support is missing, a counterfactual is invalid, or uncertainty crosses the bound.",
                )
            ),
            (
                (
                    "Robustness to named synthetic perturbations is not broad OOD or real-world robustness.",
                )
            ),
            (
                (
                    "Do not compare historical scrambled-Sobol and public-native IID scores as a shift contrast.",
                )
            ),
            "For versions without a justified shift operator and executable adapter, classify the attack UNSUPPORTED_BY_EVIDENCE or NOT_APPLICABLE by semantics.",
        ),
        (
            "training_plan_counterfactual_sensitivity@1.0.0",
            "observation_noise_perturbation@1.0.0",
            "sparse_missing_history_sensitivity@1.0.0",
            "distributional_shift_sensitivity@1.0.0",
        ),
    ),
    ValidityAxis(
        "seed_stability",
        CONTRACT_VERSION,
        "Are conclusions stable across declared data-generation, split, fit, and model initialization seeds?",
        "Reported conclusions describe between-seed variation rather than a favorable single run.",
        BENCHMARK_VERSIONS,
        AuditSpec(
            CONTRACT_VERSION,
            (
                (
                    "Per-seed dataset/split identities, fit protocol, predictions, canonical results, and deterministic settings.",
                )
            ),
            (
                "Separate data, split, initialization, and optimization seeds.",
                "Hold protocol and canonical evaluation fixed for each sensitivity contrast.",
            ),
            (
                "Summarize seed-level metrics and rank reversals; repeat only predeclared independent seeds.",
                "Do not tune on the final evaluation while increasing repetitions.",
            ),
            (
                (
                    "Per-seed manifests, fitted-state identity, prediction hashes, and evaluation rows.",
                )
            ),
            (("Seed-level spread and any conclusion changes under seed variation.",)),
            (
                (
                    "Per-target SD/range or interval, intraclass/rank stability where justified, and rank reversals.",
                )
            ),
            (
                (
                    "All predeclared conclusions remain within a justified tolerance across the required seed design.",
                )
            ),
            (
                (
                    "A conclusion changes beyond its declared stability criterion across admissible seeds.",
                )
            ),
            (
                (
                    "Too few independent seeds, confounded seed streams, or overlapping uncertainty prevents a decision.",
                )
            ),
            (("A small number of seeds cannot establish stability outside the sampled protocol.",)),
            (
                (
                    "Deterministic models may have zero fit-seed variance while data/split uncertainty remains unmeasured.",
                )
            ),
            "If per-seed artifacts or seed allocation are unavailable, report UNSUPPORTED_BY_EVIDENCE; never treat one seed as evidence of stability.",
        ),
        ("parameter_seed_sensitivity@1.0.0", "model_ranking_instability@1.0.0"),
    ),
    ValidityAxis(
        "hidden_test_fairness",
        CONTRACT_VERSION,
        "Where a hidden or access-controlled evaluation set is claimed, does its identity and access policy support a fair, non-leaking evaluation?",
        "A hidden-test claim is supported only when test identity, split construction, access, and model-selection boundaries are independently auditable.",
        BENCHMARK_VERSIONS,
        AuditSpec(
            CONTRACT_VERSION,
            (
                (
                    "Explicit hidden-test claim, split identity/construction, participant access logs or equivalent controls, and matching evaluation protocol.",
                )
            ),
            (
                "First establish that a hidden/access-controlled split exists.",
                "Use no hidden labels to tune or create audit attacks.",
            ),
            (
                (
                    "Verify split immutability, group/support balance, pre-test model sealing, permitted access, and complete scoring coverage.",
                )
            ),
            (
                (
                    "Public split declaration, immutable test identity, access/provenance records, and model-selection seal.",
                )
            ),
            (
                (
                    "Applicability decision, split/access checks, uncovered groups, and protocol deviations.",
                )
            ),
            (
                (
                    "Entity overlap, missing/duplicate score coverage, declared support balance, and access chronology.",
                )
            ),
            (
                (
                    "A declared hidden evaluation is identity-stable, access-controlled, representative of its stated target population, and scored after model sealing.",
                )
            ),
            (("An admissible access or split violation compromises the hidden-test claim.",)),
            (("Hidden-set existence, membership, or access history cannot be established.",)),
            (
                (
                    "Fair hidden-test procedure does not establish external validity or fairness across real-athlete groups not represented.",
                )
            ),
            (
                (
                    "A fully public validation set is NOT_APPLICABLE to a hidden-test claim; it is still subject to leakage and split-integrity audits.",
                )
            ),
            "Use NOT_APPLICABLE only when the version has no hidden-test claim by design; unknown split/access evidence is UNSUPPORTED_BY_EVIDENCE.",
        ),
        ("hidden_test_fairness@1.0.0",),
    ),
    ValidityAxis(
        "audit_coverage",
        CONTRACT_VERSION,
        "Were all applicable registered validity attacks attempted or assigned an explicit state with evidence and limitations?",
        "Coverage gaps, unsupported attacks, and unrun work are visible without collapsing them into a validity score.",
        BENCHMARK_VERSIONS,
        AuditSpec(
            CONTRACT_VERSION,
            (
                (
                    "Version-specific applicable attack registry, per-attack status, result/provenance references, and reasons for every exception.",
                )
            ),
            (
                "Determine the denominator from versioned attack applicability, not from attacks that happened to run.",
                "Keep NOT_APPLICABLE, NOT_RUN, and UNSUPPORTED_BY_EVIDENCE distinct.",
            ),
            (
                "Reconcile each applicable attack to one status and evidence/limitation record.",
                "Publish counts by status and missing-evidence category; do not weight or sum axis outcomes.",
            ),
            (("Attack contract registry and version-validity profile.",)),
            (("Per-axis attack coverage ledger and status counts.",)),
            (
                (
                    "Applicable/run/unsupported/not-run/not-applicable counts and completion fraction, shown only as audit coverage.",
                )
            ),
            (
                (
                    "Every applicable attack has a valid status, required provenance, and visible evidence gap or run artifact.",
                )
            ),
            (
                (
                    "A required attack is silently omitted, misclassified, or reports unsupported evidence as a pass.",
                )
            ),
            (("The applicable denominator or status evidence cannot be reconstructed.",)),
            (
                (
                    "Coverage describes the audit process, not the benchmark's predictive or scientific validity.",
                )
            ),
            (
                (
                    "A complete registry is not complete empirical coverage; NOT_RUN and UNSUPPORTED remain unresolved.",
                )
            ),
            "Count states by versioned applicability and keep missing items visible; never emit an overall validity score.",
        ),
        ("audit_coverage_accounting@1.0.0",),
    ),
)


def _attack(
    slug: str,
    axis_slug: str,
    estimand: str,
    target_failure_mode: str,
    versions: tuple[str, ...],
    semantics: tuple[str, ...],
    interventions: tuple[str, ...],
    evidence: tuple[str, ...],
    method: tuple[str, ...],
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
    diagnostics: tuple[str, ...],
    limits: tuple[str, ...],
) -> AttackSpec:
    """Keep the repeated version and state rules uniform across attack records."""
    return AttackSpec(
        slug,
        CONTRACT_VERSION,
        axis_slug,
        estimand,
        target_failure_mode,
        versions,
        semantics,
        interventions,
        evidence,
        (
            "Use only the named benchmark version's native task, information boundary, target, and support.",
            "Pre-register transformations, comparison margins, and held-fixed quantities before inspecting outcomes.",
            "A validity attack tests a claim or failure mode; it is not a replacement performance benchmark.",
        ),
        method,
        inputs,
        outputs,
        diagnostics,
        limits,
        ("A null or small effect under one attack does not establish general validity or safety.",),
        "If a required adapter, artifact, or permission is absent, distinguish NOT_APPLICABLE by semantics from UNSUPPORTED_BY_EVIDENCE; do not synthesize historical inputs.",
    )


ATTACK_SPECS: tuple[AttackSpec, ...] = (
    _attack(
        "participant_input_leakage",
        "leakage_shortcut_susceptibility",
        "Change in predictions or canonical target-wise error when non-scientific participant/row keys are removed or permuted with all permitted inputs fixed.",
        "Participant IDs, row order, split artifacts, or key encodings reveal target, group, or evaluation membership.",
        BENCHMARK_VERSIONS,
        ("Any task with participant-visible rows and a declared input boundary.",),
        (
            "Remove or permute copied identity/key fields while preserving row alignment outside model features.",
        ),
        (
            "Input schema and feature lineage.",
            "Split/group keys.",
            "Sealed fitted preprocessing and model.",
        ),
        (
            "Trace every input feature to the permitted record.",
            "Compare paired predictions before/after key-only interventions.",
        ),
        (("Public-safe input rows, preprocessing, model, and split manifest.",)),
        (("Key-feature reads, invariance failures, and target-wise paired metric deltas.",)),
        (
            (
                "Forbidden feature read count; exact prediction invariance; paired RMSE/MAE/R²/SRE change and uncertainty.",
            )
        ),
        (
            (
                "A key permutation can be out of support; report it as a stress diagnostic, not ordinary test performance.",
            )
        ),
    ),
    _attack(
        "target_identity_contamination",
        "leakage_shortcut_susceptibility",
        "Rate of forbidden target-derived fields, target/identity overlap across splits, and output response to changes in copied target/key canaries.",
        "Targets, evaluation truth, entity identity, or future labels enter features, preprocessing, model selection, or a supposedly independent split.",
        BENCHMARK_VERSIONS,
        (
            "Any task with target fields, row/entity identity, split membership, or future/evaluation records.",
        ),
        (
            "Inject canary values only into disposable copied records; permute/replace forbidden IDs without changing lawful inputs.",
        ),
        (
            "Target/input schemas.",
            "Split grain and identity manifest.",
            "Feature/preprocessing lineage and fit seal.",
        ),
        (
            "Walk target and identity dataflow from source rows through preprocessing and selection.",
            "Check split overlap at the declared independent-unit grain.",
            "Verify predictions are invariant to forbidden canaries.",
        ),
        (("Public-safe schemas, split metadata, source/dataflow, and sealed model artifacts.",)),
        (
            (
                "Target-field reads, duplicate/overlap counts, canary invariance, and affected records.",
            )
        ),
        (
            (
                "Forbidden-field read count; overlap count/rate; prediction changes under forbidden canary.",
            )
        ),
        (
            (
                "Identity overlap is a failure only when it violates the declared split grain; repeated lawful context is not automatically contamination.",
            )
        ),
    ),
    _attack(
        "shortcut_feature_dependence",
        "leakage_shortcut_susceptibility",
        "Paired target-wise prediction/error change when a pre-identified non-scientific or suspect feature is ablated or conditionally perturbed.",
        "A model relies on an accidental proxy or encoding whose predictive value does not match the stated benchmark information claim.",
        (PUBLIC_NATIVE_VERSION,),
        ("Public-native version with sealed comparator inputs and feature definitions.",),
        (
            "Ablate or conditionally permute one pre-identified feature in copied rows; keep lawful fields, fitted state, and targets fixed.",
        ),
        (
            "Feature matrix definition and feature provenance.",
            "Fitted preprocessing/model.",
            "Canonical predictions and metrics.",
        ),
        (
            "Name the suspect feature before scoring.",
            "Measure paired effects on the same evaluation rows and label out-of-support interventions.",
        ),
        (
            (
                "Public feature builder, fitted comparator, validation inputs, predictions, and evaluation records.",
            )
        ),
        (("Per-feature reliance diagnostics and target-wise paired score deltas.",)),
        (
            (
                "Paired RMSE/MAE/R²/SRE deltas, prediction correlation, and uncertainty by declared target.",
            )
        ),
        (
            (
                "Ablation dependence alone does not establish that a feature is invalid; its scientific and support status must be reviewed.",
            )
        ),
    ),
    _attack(
        "temporal_history_disruption",
        "leakage_shortcut_susceptibility",
        "Prediction and error sensitivity to declared chronology, history truncation, and chronology-preserving cadence perturbations.",
        "A model exploits chronology/order artifacts, an invalid cutoff, or undocumented dependence on specific history positions.",
        BENCHMARK_VERSIONS,
        ("Forecast task with ordered observations and a documented decision cutoff.",),
        (
            "Truncate at the legal cutoff; mask predeclared observations; optionally shuffle timestamps relative to values in copied diagnostic rows.",
        ),
        (
            (
                "Observation timestamps/order, decision cutoff, missingness/cadence rules, and fitted model.",
            )
        ),
        (
            (
                "Check cutoff adherence, then compare registered history disruptions at fixed target, plan, and row identity.",
            )
        ),
        (("Public history rows, timestamps, cutoff contract, and sealed model.",)),
        (
            (
                "Forbidden future reads, cutoff violations, cadence-specific predictions, and target-wise error changes.",
            )
        ),
        (
            (
                "Future-read count; paired metric deltas by retained-history fraction/cadence; uncertainty.",
            )
        ),
        (
            (
                "A disruption outside the intended observation process tests stress tolerance, not normal benchmark validity.",
            )
        ),
    ),
    _attack(
        "training_plan_counterfactual_sensitivity",
        "out_of_distribution_robustness",
        "Change in declared target and model prediction under an admissible alternative future plan conditional on the same history and horizon.",
        "A model ignores, misreads, or spuriously extrapolates the declared future plan that is visible at forecast time.",
        PLAN_VISIBLE_VERSIONS,
        (
            "Forecast task whose native contract explicitly exposes a declared future training plan.",
        ),
        (
            "Swap only to an alternative plan inside the same version's declared support; regenerate the corresponding target under its native world.",
        ),
        (
            (
                "Plan visibility and support, history cutoff, horizon, generator/world adapter, paired target construction, and model.",
            )
        ),
        (
            (
                "Pair rows on fixed history/horizon, vary plan, regenerate target, and compare plan-response directions/magnitudes.",
            )
        ),
        (
            (
                "Native plan and world adapters, public-safe histories, fitted model, and regenerated paired targets.",
            )
        ),
        (("Plan-conditioned target and prediction response, errors, and support checks.",)),
        (
            (
                "Within-support paired target/prediction deltas by plan/horizon; directional agreement and uncertainty.",
            )
        ),
        (
            (
                "The estimand is conditional on the declared synthetic world; it is not the causal effect of training for real athletes.",
            )
        ),
    ),
    _attack(
        "observation_noise_perturbation",
        "out_of_distribution_robustness",
        "Prediction/error response to fresh or perturbed observations generated under the same versioned observation law with latent target held fixed.",
        "Predictions are brittle to admissible observation noise or exploit a particular noise realization rather than the declared signal.",
        OBSERVATION_MODEL_VERSIONS,
        (
            "World version with a public observation model and generator adapter that can hold latent trajectories and targets fixed.",
        ),
        (
            "Regenerate observation noise under the same observation law while fixing latent trajectory, plan, horizon, and target.",
        ),
        (
            (
                "Observation model, random stream allocation, fixed latent/target identity, and model.",
            )
        ),
        (
            (
                "Use paired noise draws from the same law; report in-law variation separately from out-of-law stress.",
            )
        ),
        (
            (
                "Public observation/world implementation, input history, fixed target, and fitted model.",
            )
        ),
        (
            (
                "Noise draw identities, prediction dispersion, target-wise metric changes, and calibration/residual changes if defined.",
            )
        ),
        (
            (
                "Paired error/prediction variance over declared noise replicates and target-wise deltas with uncertainty.",
            )
        ),
        (
            (
                "Noise robustness is specific to the declared observation law and does not validate real measurement noise.",
            )
        ),
    ),
    _attack(
        "sparse_missing_history_sensitivity",
        "out_of_distribution_robustness",
        "Prediction/error change under predeclared observation thinning or missingness patterns while target and legal information cutoff remain fixed.",
        "Performance depends on dense or complete histories beyond what the benchmark's claimed deployment setting supports.",
        BENCHMARK_VERSIONS,
        (
            "Task with longitudinal history and either declared cadence/missingness support or a clearly labeled stress extension.",
        ),
        (
            "Thin or mask only history observations according to a preregistered cadence/pattern; do not alter targets or expose future records.",
        ),
        (
            (
                "Observation cadence, missingness semantics, cutoff, model preprocessing, and target rows.",
            )
        ),
        (
            (
                "Evaluate each declared mask/cadence separately; distinguish in-support missingness from synthetic stress.",
            )
        ),
        (("Public history, mask generator, preprocessing, model, and held-out targets.",)),
        (
            (
                "Availability counts, prediction/error changes by history density, and unsupported mask cases.",
            )
        ),
        (
            (
                "Retained-observation fraction; missingness-stratified target-wise metric changes and uncertainty.",
            )
        ),
        (
            (
                "Synthetic deletion patterns do not establish robustness to real-world informative missingness.",
            )
        ),
    ),
    _attack(
        "distributional_shift_sensitivity",
        "out_of_distribution_robustness",
        "Target-wise performance and prediction changes under a predeclared distribution shift relative to the same benchmark version's reference distribution.",
        "A result is generalized beyond the support it actually covers, or a named shift causes material degradation that is hidden by aggregate reporting.",
        (PUBLIC_NATIVE_VERSION,),
        (
            "Version with a public-safe generator and a predeclared shift operator tied to its native world/task semantics.",
        ),
        (
            "Apply one supported population/plan/history/observation transform at a time in a copied or newly generated audit realization.",
        ),
        (
            (
                "Native generator and support, shift declaration, train/reference/shifted split identities, and model outputs.",
            )
        ),
        (
            (
                "Separate in-support and extrapolative regimes; freeze model before scoring shifted rows; report every shift independently.",
            )
        ),
        (
            (
                "Public generator, frozen model, declared shift manifest, and shifted held-out realization.",
            )
        ),
        (("Per-shift support relation, stratum metrics, degradation, and uncertainty.",)),
        (
            (
                "Target-wise metric delta and relative degradation by declared shift; paired intervals where pairing is valid.",
            )
        ),
        (
            (
                "A shift result cannot be compared to a different dataset sampling design as if sampling design alone were an intervention.",
            )
        ),
    ),
    _attack(
        "parameter_seed_sensitivity",
        "seed_stability",
        "Variation in target-wise outcomes attributable separately to predeclared fit/initialization seeds and predeclared parameter settings on fixed data/splits.",
        "A reported model conclusion depends on a favorable seed or unreported parameter choice.",
        (PUBLIC_NATIVE_VERSION,),
        ("Version with public per-seed fit protocols, predictions, and fitted-state identities.",),
        (
            "Repeat only predeclared fit seeds or bounded parameter settings; never change split, targets, or final evaluation during selection.",
        ),
        (
            (
                "Seed allocation, hyperparameter/parameter protocol, fitted states, predictions, and evaluation identity.",
            )
        ),
        (
            "Partition data-generation, split, initialization, and optimization seed effects.",
            "Report every registered setting; do not select a winner on canonical validation.",
        ),
        (("Frozen training protocol, per-seed predictions/results, and fit seals.",)),
        (
            (
                "Seed/setting-level metric distribution, fitted-state variability, and any conclusion reversals.",
            )
        ),
        (
            (
                "Per-target range/SD/interval and pairwise outcome/rank reversals across declared seeds/settings.",
            )
        ),
        (
            (
                "A fixed deterministic method's repeated identical fit does not estimate data-generation or split uncertainty.",
            )
        ),
    ),
    _attack(
        "baseline_domination",
        "simple_model_frontier",
        "Whether any predeclared simple/reference model Pareto-dominates the claimed learned or historical method on matched target-wise metrics.",
        "A complex-method claim is presented without a strong simple/reference comparator or is dominated under the declared evaluation.",
        (PUBLIC_NATIVE_VERSION,),
        (
            "Version with matched public prediction artifacts from learned and simple/mechanistic/reference methods.",
        ),
        ("Use existing prediction/evaluation artifacts only; do not refit or rescore in RES-277.",),
        (
            (
                "Same rows, targets, support, information boundary, canonical metric identities, and model provenance.",
            )
        ),
        (
            (
                "Construct target-wise Pareto relations using metric direction and predeclared practical margins; retain crossing trade-offs.",
            )
        ),
        (
            (
                "Public comparator registry, per-seed result table, result artifacts, and model cards.",
            )
        ),
        (("Dominance graph/frontier, target-wise metric deltas, and limitations.",)),
        (("Pareto dominance by target and metric; paired uncertainty/margin when available.",)),
        (
            (
                "Existing M4 results are an input example, not a RES-277 verdict; their finite method set does not prove a universal frontier.",
            )
        ),
    ),
    _attack(
        "model_ranking_instability",
        "seed_stability",
        "Probability or frequency that a model-pair or model ordering reverses under declared participant-level resampling, seed variation, or admissible within-version perturbation.",
        "A reported model superiority/ranking is unstable to sampling uncertainty or is an artifact of an unmatched comparison.",
        (PUBLIC_NATIVE_VERSION,),
        (
            "At least two models evaluated on the same version, rows, metric definitions, and independent-unit structure.",
        ),
        (
            "Resample only declared independent units or use existing seeds; no cross-version score pooling.",
        ),
        (
            (
                "Aligned per-row predictions, group IDs, per-seed outputs, canonical metrics, and comparability decision.",
            )
        ),
        (
            (
                "Compute paired model differences and rank reversals within version; apply a comparability gate before any cross-version analysis.",
            )
        ),
        (("Public per-row predictions/results, split-group identities, and model/seed registry.",)),
        (("Pairwise differences, ranking uncertainty/reversal rates, and unresolved ties.",)),
        (
            (
                "Participant-cluster bootstrap intervals, per-seed rank reversals, and target-wise pairwise deltas.",
            )
        ),
        (
            (
                "Ranks summarize a finite method set and metric choice; no single overall winner is inferred across unmatched targets.",
            )
        ),
    ),
    _attack(
        "reconstruction_provenance_gaps",
        "reconstructability",
        "Fraction and type of required identity, source, data, model, evaluation, and artifact-provenance links that can be reconstructed and verified.",
        "A benchmark or audit claim cannot be reproduced because a required source, transformation, identity, permission, or artifact link is absent or inconsistent.",
        BENCHMARK_VERSIONS,
        ("Any versioned benchmark claim or public result artifact.",),
        (
            "Read public manifests and hashes; reconstruct only rights-cleared public artifacts and explicitly permitted projections.",
        ),
        (
            (
                "Benchmark registry, source provenance, data/model/evaluation references, rights metadata, and public artifact hashes.",
            )
        ),
        (
            (
                "Walk each required provenance edge, verify identities and hashes, and list unverified/missing edges by claim.",
            )
        ),
        (
            (
                "Public registry/docs/manifests and rights-cleared artifacts; no private historical data or checkpoints.",
            )
        ),
        (("Verified/missing provenance links, mismatches, and unsupported claims.",)),
        (("Required-link completion count/rate by artifact class; hash/identity mismatch count.",)),
        (
            (
                "Completeness is not truth; provenance cannot repair absent historical source data or prove a scientific mechanism.",
            )
        ),
    ),
    _attack(
        "hidden_test_fairness",
        "hidden_test_fairness",
        "Conformance of any claimed hidden evaluation split and access protocol to its predeclared identity, independence, group, and coverage rules.",
        "A nominally hidden test is leaked, mutable, selectively scored, or mismatched to its stated evaluation population.",
        BENCHMARK_VERSIONS,
        (
            "Only versions explicitly claiming hidden or access-controlled evaluation; first test whether such a split exists.",
        ),
        (
            "Inspect public split/access manifests and seals; never inspect or release hidden labels to perform the audit.",
        ),
        (
            (
                "Explicit hidden-test claim, split identity, access policy/logs, model seal, score-coverage records, and declared test population.",
            )
        ),
        (
            "If absent by design, report NOT_APPLICABLE; if claimed but proof is unavailable, report UNSUPPORTED_BY_EVIDENCE.",
            "Otherwise verify identity immutability, permitted access chronology, group separation, and score completeness.",
        ),
        (
            (
                "Split/access manifests, public test protocol, and model selection/provenance records.",
            )
        ),
        (("Applicability state, split/access violations, and group/score coverage diagnostics.",)),
        (
            (
                "Entity overlap counts, missing/duplicate score coverage, and access-before-seal violation count.",
            )
        ),
        (
            (
                "Fairness here concerns evaluation procedure and stated test population, not social fairness or unobserved athlete subgroups.",
            )
        ),
    ),
    _attack(
        "audit_coverage_accounting",
        "audit_coverage",
        "Counts of applicable attacks with admissible completed evidence, explicit non-run status, unsupported inputs, and semantic non-applicability for one version.",
        "Audit coverage is overstated by omitting difficult attacks, conflating missing evidence with a pass, or using an unstable denominator.",
        BENCHMARK_VERSIONS,
        ("Versioned validity-axis and attack registries plus one profile per benchmark version.",),
        (
            "Count registered applicable contracts and explicit status records; retain reasons and provenance for every count.",
        ),
        (
            (
                "Versioned registries, applicability predicates, result statuses, evidence refs, and missing-evidence declarations.",
            )
        ),
        (
            "Reconcile each registered attack to exactly one state; report status counts by axis and version.",
            "Never aggregate validity states into a scalar.",
        ),
        (("Axis/attack registries and VersionValidityProfile entries.",)),
        (("Attack coverage ledger, status counts, and uncovered contracts.",)),
        (
            (
                "Applicable/run/unsupported/not-run/not-applicable counts; coverage fraction as process metadata only.",
            )
        ),
        (
            (
                "A complete paperwork ledger does not imply empirical execution or benchmark validity.",
            )
        ),
    ),
)


# Compatibility aliases for the pre-RES-277 audit taxonomy imports.
AuditAxis = ValidityAxis
AUDIT_AXES = VALIDITY_AXES
