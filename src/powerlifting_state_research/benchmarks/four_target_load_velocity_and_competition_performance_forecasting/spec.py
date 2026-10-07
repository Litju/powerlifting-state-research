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
    display_name="Four-Target Load–Velocity and Competition Performance Forecasting",
    slug="four_target_load_velocity_and_competition_performance_forecasting",
    python_namespace="powerlifting_state_research.benchmarks.four_target_load_velocity_and_competition_performance_forecasting",
    docs_path="docs/benchmarks/four-target-load-velocity-and-competition-performance-forecasting.md",
    test_path="tests/benchmarks/four_target_load_velocity_and_competition_performance_forecasting/test_spec.py",
    historical_specimen_status=HistoricalSpecimenStatus.PARTIALLY_RECONSTRUCTED,
    historical_qualification_state=HistoricalQualificationState.NOT_QUALIFIED_OR_UNRESOLVED,
    completeness_status=CompletenessStatus.PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS,
    public_implementation_status=IMPLEMENTATION_STATUS,
    target_ontology="MULTI_OUTPUT_OTHER",
    task_type="FOUR_TARGET_25_DAY_PERFORMANCE_FORECAST",
    component_references=(
        COMPONENT_REGISTRIES[ComponentClass.WORLD]["four_target_longitudinal_performance_state"],
        ComponentReference(
            ComponentClass.POPULATION, None, ComponentResolution.UNRESOLVED_DIRECT_ID
        ),
        ComponentReference(
            ComponentClass.INTERVENTION_REGIME, None, ComponentResolution.UNRESOLVED_DIRECT_ID
        ),
        COMPONENT_REGISTRIES[ComponentClass.OBSERVATION_MODEL][
            "athlete_state_training_observation"
        ],
        COMPONENT_REGISTRIES[ComponentClass.DATASET_SPEC][
            "four_target_load_velocity_and_competition_performance_forecasting_sampling_design"
        ],
        COMPONENT_REGISTRIES[ComponentClass.TASK][
            "four_target_load_velocity_and_competition_performance_forecast"
        ],
        COMPONENT_REGISTRIES[ComponentClass.QOI][
            "four_load_velocity_and_competition_performance_targets"
        ],
        COMPONENT_REGISTRIES[ComponentClass.REPRESENTATION]["four_target_temporal_inputs"],
        COMPONENT_REGISTRIES[ComponentClass.EVALUATION]["four_target_weighted_evaluation"],
    ),
)
