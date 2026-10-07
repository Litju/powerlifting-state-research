"""Typed scientific benchmark specification."""

from __future__ import annotations

from ...components import COMPONENT_REGISTRIES
from ...contracts.benchmark import (
    BenchmarkSpec,
    CompletenessStatus,
    HistoricalQualificationState,
    HistoricalSpecimenStatus,
    ImplementationStatus,
)
from ...contracts.components import ComponentClass, ComponentReference, ComponentResolution

IMPLEMENTATION_STATUS = ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING

SPEC = BenchmarkSpec(
    display_name="Observed-Origin Performance-Change Forecasting",
    slug="observed_origin_performance_change_forecasting",
    python_namespace="powerlifting_state_research.benchmarks.observed_origin_performance_change_forecasting",
    docs_path="docs/benchmarks/observed-origin-performance-change-forecasting.md",
    test_path="tests/benchmarks/observed_origin_performance_change_forecasting/test_spec.py",
    historical_specimen_status=HistoricalSpecimenStatus.PARTIALLY_RECONSTRUCTED,
    historical_qualification_state=HistoricalQualificationState.NOT_QUALIFIED_OR_UNRESOLVED,
    completeness_status=CompletenessStatus.PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS,
    public_implementation_status=IMPLEMENTATION_STATUS,
    target_ontology="OBSERVED_PERFORMANCE",
    task_type="OBSERVED_ORIGIN_RESPONSE_FORECAST",
    component_references=(
        COMPONENT_REGISTRIES[ComponentClass.WORLD]["training_dose_history_capacity_dynamics"],
        ComponentReference(
            ComponentClass.POPULATION, None, ComponentResolution.UNRESOLVED_DIRECT_ID
        ),
        ComponentReference(
            ComponentClass.INTERVENTION_REGIME, None, ComponentResolution.UNRESOLVED_DIRECT_ID
        ),
        COMPONENT_REGISTRIES[ComponentClass.OBSERVATION_MODEL][
            "performance_assessment_observation"
        ],
        COMPONENT_REGISTRIES[ComponentClass.DATASET_SPEC][
            "observed_origin_performance_change_forecasting_sampling_design"
        ],
        COMPONENT_REGISTRIES[ComponentClass.TASK]["observed_origin_performance_change_forecast"],
        COMPONENT_REGISTRIES[ComponentClass.QOI]["observed_origin_performance_change"],
        COMPONENT_REGISTRIES[ComponentClass.REPRESENTATION]["dose_history_and_assessment_inputs"],
        COMPONENT_REGISTRIES[ComponentClass.EVALUATION]["observed_origin_public_sre_evaluation"],
    ),
)
