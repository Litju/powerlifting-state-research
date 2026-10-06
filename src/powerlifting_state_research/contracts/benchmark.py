"""Minimal typed records for the bootstrap benchmark registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .components import ComponentReference


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
    target_ontology: str
    task_type: str
    component_references: tuple[ComponentReference, ...]


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
