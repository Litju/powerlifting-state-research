"""Minimal typed records for the bootstrap benchmark registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .components import ComponentReference
from .serialization import require_scientific_id, sha256_record
from .shifts import ShiftDeclaration


class HistoricalSpecimenStatus(StrEnum):
    HISTORICAL_REGISTRY_ONLY = "HISTORICAL_REGISTRY_ONLY"
    PARTIALLY_RECONSTRUCTED = "PARTIALLY_RECONSTRUCTED"
    REPRODUCIBLE_SPEC = "REPRODUCIBLE_SPEC"
    QUALIFIED_HISTORICAL = "QUALIFIED_HISTORICAL"


class HistoricalQualificationState(StrEnum):
    NOT_QUALIFIED_OR_UNRESOLVED = "NOT_QUALIFIED_OR_UNRESOLVED"
    QUALIFIED_HISTORICAL = "QUALIFIED_HISTORICAL"


class CompletenessStatus(StrEnum):
    PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS = "PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS"
    FULL_FROM_EXISTING_EVIDENCE = "FULL_FROM_EXISTING_EVIDENCE"


class ImplementationStatus(StrEnum):
    PUBLIC_IMPLEMENTATION_PENDING = "PUBLIC_IMPLEMENTATION_PENDING"
    PUBLIC_IMPLEMENTED = "PUBLIC_IMPLEMENTED"


class IdentityResolution(StrEnum):
    DIRECT = "DIRECT"
    COMMITTED_BY_SYSTEM_CONFIG = "COMMITTED_BY_SYSTEM_CONFIG"
    UNRESOLVED = "UNRESOLVED"


class BenchmarkIdentityAuthority(StrEnum):
    HISTORICAL_PROJECTION = "HISTORICAL_PROJECTION"
    PUBLIC_NATIVE = "PUBLIC_NATIVE"


class ClaimScope(StrEnum):
    IDENTIFIABILITY = "IDENTIFIABILITY"
    INTERVENTION_EFFECT = "INTERVENTION_EFFECT"
    MECHANISTIC_MODEL = "MECHANISTIC_MODEL"
    OOD_GENERALIZATION = "OOD_GENERALIZATION"
    PREDICTIVE = "PREDICTIVE"
    REAL_ATHLETE_EMPIRICAL = "REAL_ATHLETE_EMPIRICAL"
    SYNTHETIC_BENCHMARK = "SYNTHETIC_BENCHMARK"


@dataclass(frozen=True, slots=True)
class ComponentIdentity:
    resolution: IdentityResolution
    id: str | None = None
    system_config_id: str | None = None
    reason: str | None = None
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        if self.resolution is IdentityResolution.DIRECT and (not self.id or self.system_config_id):
            raise ValueError("direct component identity needs exactly one direct ID")
        if self.resolution is IdentityResolution.DIRECT:
            require_scientific_id(self.id or "", "component ID")
        if self.resolution is IdentityResolution.COMMITTED_BY_SYSTEM_CONFIG and (
            self.id or not self.system_config_id
        ):
            raise ValueError("committed component identity needs a system-config ID only")
        if self.resolution is IdentityResolution.COMMITTED_BY_SYSTEM_CONFIG:
            require_scientific_id(
                self.system_config_id or "",
                "system-config ID",
                expected_class="scientific-system-config",
            )
        if self.resolution is IdentityResolution.UNRESOLVED and (
            self.id or self.system_config_id or not self.reason or not self.evidence_ref
        ):
            raise ValueError("unresolved component identity needs a reason and evidence reference")

    def identity_payload(self, system_config_id: str) -> dict[str, str | None]:
        if self.resolution is IdentityResolution.DIRECT:
            return {"id": self.id, "resolution": self.resolution.value}
        if self.resolution is IdentityResolution.COMMITTED_BY_SYSTEM_CONFIG:
            return {
                "direct_component_id": None,
                "resolution": self.resolution.value,
                "system_config_id": self.system_config_id or system_config_id,
            }
        return {
            "evidence_ref": self.evidence_ref,
            "reason": self.reason,
            "resolution": self.resolution.value,
        }


@dataclass(frozen=True, slots=True)
class DecisionCutoff:
    event_index: str
    value: int | str
    timestamp: str | None = None
    timezone: str | None = None

    def __post_init__(self) -> None:
        if not self.event_index.strip():
            raise ValueError("decision cutoff event index must be non-empty")

    def identity_payload(self) -> dict[str, int | str | None]:
        payload: dict[str, int | str | None] = {
            "event_index": self.event_index,
            "value": self.value,
        }
        if self.timestamp is not None:
            payload["timestamp"] = self.timestamp
        if self.timezone is not None:
            payload["timezone"] = self.timezone
        return payload


@dataclass(frozen=True, slots=True)
class PredictionInformationBoundary:
    decision_cutoff: DecisionCutoff
    cutoff_inclusive: bool
    history_observation_last_day: int | None
    static_or_context_inputs: str
    declared_future_plan_visible: bool
    future_plan_means_delivered_exposure: bool = False
    future_realized_performance_forbidden: bool = True
    future_realized_observations_forbidden: bool = True
    future_process_disturbances_forbidden: bool = True
    future_intervention_deviations_forbidden: bool = True
    target_derived_information_forbidden: bool = True
    evaluation_truth_forbidden: bool = True

    def __post_init__(self) -> None:
        if not self.static_or_context_inputs.strip():
            raise ValueError("static/context input rule must be explicit")
        if not all(
            (
                self.future_realized_performance_forbidden,
                self.future_realized_observations_forbidden,
                self.future_process_disturbances_forbidden,
                self.future_intervention_deviations_forbidden,
                self.target_derived_information_forbidden,
                self.evaluation_truth_forbidden,
            )
        ):
            raise ValueError(
                "future outcomes, target-derived fields, and evaluation truth are forbidden"
            )
        if self.future_plan_means_delivered_exposure:
            raise ValueError("a declared future plan cannot mean delivered exposure")

    def identity_payload(self) -> dict[str, object]:
        return {
            "decision_cutoff": self.decision_cutoff.identity_payload(),
            "declared_future_plan_visible": self.declared_future_plan_visible,
            "evaluation_truth_forbidden": self.evaluation_truth_forbidden,
            "future_intervention_deviations_forbidden": (
                self.future_intervention_deviations_forbidden
            ),
            "future_plan_means_delivered_exposure": self.future_plan_means_delivered_exposure,
            "future_process_disturbances_forbidden": self.future_process_disturbances_forbidden,
            "future_realized_observations_forbidden": self.future_realized_observations_forbidden,
            "future_realized_performance_forbidden": self.future_realized_performance_forbidden,
            "history_observation_last_day": self.history_observation_last_day,
            # The V1 flag encodes cutoff inclusivity to preserve the frozen digest.
            "history_observed_through_cutoff": self.cutoff_inclusive,
            "static_or_context_inputs": self.static_or_context_inputs,
            "target_derived_information_forbidden": self.target_derived_information_forbidden,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkSemanticIdentity:
    scientific_system_config_id: str
    world_id: ComponentIdentity
    population_id: ComponentIdentity
    intervention_regime_id: ComponentIdentity
    observation_model_id: ComponentIdentity
    dataset_spec_id: str
    task_id: str
    qoi_ids: tuple[str, ...]
    prediction_information_boundary: PredictionInformationBoundary
    representation_id: str | None
    evaluation_id: str
    declared_shift_relations: tuple[ShiftDeclaration, ...]
    claim_scope: tuple[ClaimScope, ...]

    def __post_init__(self) -> None:
        required_ids = (
            self.scientific_system_config_id,
            self.dataset_spec_id,
            self.task_id,
            self.evaluation_id,
        )
        if (
            any(not item.strip() for item in required_ids)
            or not self.qoi_ids
            or not self.claim_scope
        ):
            raise ValueError("benchmark semantic identity is missing a required reference")
        for label, value, expected_class in (
            (
                "scientific-system config ID",
                self.scientific_system_config_id,
                "scientific-system-config",
            ),
            ("dataset-spec ID", self.dataset_spec_id, "dataset-spec"),
            ("task ID", self.task_id, "task"),
            ("evaluation ID", self.evaluation_id, "evaluation"),
        ):
            require_scientific_id(value, label, expected_class=expected_class)
        for qoi_id in self.qoi_ids:
            require_scientific_id(qoi_id, "QOI ID", expected_class="qoi")
        if self.representation_id is not None:
            require_scientific_id(
                self.representation_id, "representation ID", expected_class="representation"
            )
        for label, component, component_class in (
            ("WORLD", self.world_id, "world"),
            ("POPULATION", self.population_id, "population"),
            ("INTERVENTION_REGIME", self.intervention_regime_id, "intervention-regime"),
            ("OBSERVATION_MODEL", self.observation_model_id, "observation-model"),
        ):
            if component.resolution is IdentityResolution.DIRECT:
                require_scientific_id(
                    component.id or "", f"{label} ID", expected_class=component_class
                )
            elif component.resolution is IdentityResolution.COMMITTED_BY_SYSTEM_CONFIG:
                require_scientific_id(
                    component.system_config_id or "",
                    f"{label} system-config ID",
                    expected_class="scientific-system-config",
                )
        if len(set(self.qoi_ids)) != len(self.qoi_ids):
            raise ValueError("QOI identity references must be unique")

    @property
    def is_complete(self) -> bool:
        refs = (
            self.world_id,
            self.population_id,
            self.intervention_regime_id,
            self.observation_model_id,
        )
        return all(ref.resolution is not IdentityResolution.UNRESOLVED for ref in refs)

    def payload(self) -> dict[str, object]:
        return {
            "identity_payload_format": "PSR_BENCHMARK_SEMANTIC_IDENTITY_V1",
            "scientific_system_config_id": self.scientific_system_config_id,
            "world_id": self.world_id.identity_payload(self.scientific_system_config_id),
            "population_id": self.population_id.identity_payload(self.scientific_system_config_id),
            "intervention_regime_id": self.intervention_regime_id.identity_payload(
                self.scientific_system_config_id
            ),
            "observation_model_id": self.observation_model_id.identity_payload(
                self.scientific_system_config_id
            ),
            "dataset_spec_id": self.dataset_spec_id,
            "task_id": self.task_id,
            "qoi_ids": sorted(self.qoi_ids),
            "prediction_information_boundary": (
                self.prediction_information_boundary.identity_payload()
            ),
            "representation_id": self.representation_id,
            "evaluation_id": self.evaluation_id,
            "declared_shift_relations": sorted(
                (shift.identity_payload() for shift in self.declared_shift_relations),
                key=lambda item: str(item["shift_id"]),
            ),
            "claim_scope": sorted(claim.value for claim in self.claim_scope),
        }

    @property
    def digest(self) -> str:
        if not self.is_complete:
            raise ValueError("incomplete historical component references cannot mint an identity")
        return sha256_record(self.payload(), reject_floats=True)


@dataclass(frozen=True, slots=True)
class BenchmarkSpec:
    display_name: str
    slug: str
    python_namespace: str
    docs_path: str
    test_path: str
    historical_specimen_status: HistoricalSpecimenStatus
    historical_qualification_state: HistoricalQualificationState
    completeness_status: CompletenessStatus
    public_implementation_status: ImplementationStatus
    identity_authority: BenchmarkIdentityAuthority
    target_ontology: str
    task_type: str
    component_references: tuple[ComponentReference, ...]
    contract_schema_version: str = "1.0.0"
    semantic_identity: BenchmarkSemanticIdentity | None = None
    version: str = "1.0.0"
    related_benchmark_slugs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", self.slug):
            raise ValueError("benchmark slug must be a lowercase scientific identifier")
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.version):
            raise ValueError("benchmark version must use semantic version form")
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.contract_schema_version):
            raise ValueError("contract schema version must use semantic version form")
        if not all(
            value.strip()
            for value in (
                self.display_name,
                self.python_namespace,
                self.docs_path,
                self.test_path,
                self.target_ontology,
                self.task_type,
            )
        ):
            raise ValueError("benchmark name, paths, and task semantics must be explicit")
        if not isinstance(self.identity_authority, BenchmarkIdentityAuthority):
            raise ValueError("benchmark identity authority must be explicit")
        if self.slug in self.related_benchmark_slugs or len(
            set(self.related_benchmark_slugs)
        ) != len(self.related_benchmark_slugs):
            raise ValueError("related benchmark slugs must be unique and exclude this benchmark")
        if any(
            not re.fullmatch(r"[a-z0-9][a-z0-9_]*", slug) for slug in self.related_benchmark_slugs
        ):
            raise ValueError("related benchmark slugs must be lowercase scientific identifiers")
        if self.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE:
            if self.semantic_identity is None or any(
                component.resolution is not IdentityResolution.DIRECT
                for component in (
                    self.semantic_identity.world_id,
                    self.semantic_identity.population_id,
                    self.semantic_identity.intervention_regime_id,
                    self.semantic_identity.observation_model_id,
                )
            ):
                raise ValueError(
                    "PUBLIC_NATIVE benchmarks need explicit direct WORLD, POPULATION, "
                    "INTERVENTION_REGIME, and OBSERVATION_MODEL identities"
                )

    @property
    def identity_mintable(self) -> bool:
        return (
            self.completeness_status is CompletenessStatus.FULL_FROM_EXISTING_EVIDENCE
            and self.semantic_identity is not None
            and self.semantic_identity.is_complete
        )

    @property
    def semantic_digest(self) -> str | None:
        if not self.identity_mintable or self.semantic_identity is None:
            return None
        return self.semantic_identity.digest

    @property
    def identity_payload(self) -> dict[str, object] | None:
        return (
            self.semantic_identity.payload()
            if self.identity_mintable and self.semantic_identity
            else None
        )

    @property
    def benchmark_id(self) -> str | None:
        digest = self.semantic_digest
        if digest is None:
            return None
        return f"psr:benchmark-spec:{self.slug.replace('_', '-')}@{self.version}~{digest[7:19]}"


@dataclass(frozen=True, slots=True)
class ResearchMetadata:
    canonical_research_question: str
    canonical_scientific_objective: str
    research_question_evidence_class: str
    information_setting: str
    source_prediction_setting: str
    historical_objective: str
    historical_objective_evidence: str
    canonical_claim_scope: tuple[str, ...]
    claim_escalations_prohibited: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
