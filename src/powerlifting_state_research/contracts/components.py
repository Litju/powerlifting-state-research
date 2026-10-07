"""Immutable scientific component references and historical provenance records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ComponentClass(StrEnum):
    WORLD = "WORLD"
    POPULATION = "POPULATION"
    INTERVENTION_REGIME = "INTERVENTION_REGIME"
    OBSERVATION_MODEL = "OBSERVATION_MODEL"
    QOI = "QOI"
    TASK = "TASK"
    REPRESENTATION = "REPRESENTATION"
    DATASET_SPEC = "DATASET_SPEC"
    EVALUATION = "EVALUATION"
    METRIC = "METRIC"
    SHIFT = "SHIFT"


class ComponentResolution(StrEnum):
    """Whether a component reference resolves historically, publicly, or through a config."""

    DIRECT_HISTORICAL_IDENTITY = "DIRECT_HISTORICAL_IDENTITY"
    DIRECT_PUBLIC_NATIVE_IDENTITY = "DIRECT_PUBLIC_NATIVE_IDENTITY"
    UNRESOLVED_DIRECT_ID = "UNRESOLVED_DIRECT_ID"
    COMMITTED_BY_SYSTEM_CONFIG = "COMMITTED_BY_SYSTEM_CONFIG"


@dataclass(frozen=True, slots=True)
class ComponentReference:
    component_class: ComponentClass
    canonical_key: str | None
    resolution: ComponentResolution


@dataclass(frozen=True, slots=True)
class HistoricalProvenance:
    specimen_id: str
    historical_aliases: tuple[str, ...]
    historical_parent_specimen_id: str | None
    parentage_status: str
    source_technical_label: str
    source_system_focus: str
    source_prediction_setting: str
    source_research_question: str
    source_research_question_evidence: str
    historical_objective: str
    historical_objective_evidence: str
    source_qualification_status: str
    source_component_ids: dict[str, str | None]
    source_component_changes: dict[str, object]
    evidence_pointers: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    attached_audit_aliases: tuple[str, ...]
