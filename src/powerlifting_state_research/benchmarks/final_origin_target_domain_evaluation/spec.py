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
    display_name="Final-Origin Target-Domain Evaluation of Seasonal Performance Forecasts",
    slug="final_origin_target_domain_evaluation",
    python_namespace="powerlifting_state_research.benchmarks.final_origin_target_domain_evaluation",
    docs_path="docs/benchmarks/final-origin-target-domain-evaluation.md",
    test_path="tests/benchmarks/final_origin_target_domain_evaluation/test_spec.py",
    historical_specimen_status=HistoricalSpecimenStatus.PARTIALLY_RECONSTRUCTED,
    historical_qualification_state=HistoricalQualificationState.NOT_QUALIFIED_OR_UNRESOLVED,
    completeness_status=CompletenessStatus.PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS,
    public_implementation_status=IMPLEMENTATION_STATUS,
    target_ontology="MULTI_OUTPUT_OTHER",
    task_type="FINAL_ORIGIN_TARGET_DOMAIN_FORECAST",
    component_references=(
        COMPONENT_REGISTRIES[ComponentClass.WORLD]["class_normalized_cross_lift_capacity_fatigue"],
        ComponentReference(
            ComponentClass.POPULATION, None, ComponentResolution.UNRESOLVED_DIRECT_ID
        ),
        ComponentReference(
            ComponentClass.INTERVENTION_REGIME, None, ComponentResolution.UNRESOLVED_DIRECT_ID
        ),
        COMPONENT_REGISTRIES[ComponentClass.OBSERVATION_MODEL][
            "field_velocity_and_load_observation"
        ],
        COMPONENT_REGISTRIES[ComponentClass.DATASET_SPEC][
            "final_origin_target_domain_evaluation_sampling_design"
        ],
        COMPONENT_REGISTRIES[ComponentClass.TASK]["final_origin_seasonal_forecast"],
        COMPONENT_REGISTRIES[ComponentClass.QOI]["seasonal_five_performance_outputs"],
        COMPONENT_REGISTRIES[ComponentClass.REPRESENTATION]["class_normalized_table_inputs"],
        COMPONENT_REGISTRIES[ComponentClass.EVALUATION]["final_origin_target_domain_evaluation"],
    ),
)
