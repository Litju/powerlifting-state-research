"""Typed scientific benchmark specification."""

from __future__ import annotations

from ...components import COMPONENT_REGISTRIES
from ...contracts.benchmark import (
    BenchmarkIdentityAuthority,
    BenchmarkSpec,
    CompletenessStatus,
    HistoricalQualificationState,
    HistoricalSpecimenStatus,
    ImplementationStatus,
)
from ...contracts.components import ComponentClass, ComponentReference, ComponentResolution

IMPLEMENTATION_STATUS = ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING

SPEC = BenchmarkSpec(
    display_name="Held-Out Final-Origin Evaluation of Five Performance Targets",
    slug="held_out_final_origin_five_target_performance_evaluation",
    python_namespace="powerlifting_state_research.benchmarks.held_out_final_origin_five_target_performance_evaluation",
    docs_path="docs/benchmarks/held-out-final-origin-five-target-performance-evaluation.md",
    test_path="tests/benchmarks/held_out_final_origin_five_target_performance_evaluation/test_spec.py",
    historical_specimen_status=HistoricalSpecimenStatus.PARTIALLY_RECONSTRUCTED,
    historical_qualification_state=HistoricalQualificationState.NOT_QUALIFIED_OR_UNRESOLVED,
    completeness_status=CompletenessStatus.PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS,
    public_implementation_status=IMPLEMENTATION_STATUS,
    identity_authority=BenchmarkIdentityAuthority.HISTORICAL_PROJECTION,
    target_ontology="MULTI_OUTPUT_OTHER",
    task_type="HELD_OUT_FINAL_ORIGIN_FIVE_TARGET_FORECAST",
    component_references=(
        COMPONENT_REGISTRIES[ComponentClass.WORLD]["athlete_latent_state_dynamics"],
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
            "held_out_final_origin_five_target_performance_evaluation_sampling_design"
        ],
        COMPONENT_REGISTRIES[ComponentClass.TASK][
            "held_out_final_origin_five_target_performance_forecast"
        ],
        COMPONENT_REGISTRIES[ComponentClass.QOI]["seasonal_five_target_performance_outputs"],
        COMPONENT_REGISTRIES[ComponentClass.REPRESENTATION]["class_normalized_table_inputs"],
        COMPONENT_REGISTRIES[ComponentClass.EVALUATION][
            "held_out_final_origin_five_target_performance_evaluation"
        ],
    ),
)
