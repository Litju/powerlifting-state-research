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
    display_name="Seasonal Five-Target Load–Velocity and Performance Forecasting",
    slug="seasonal_five_target_load_velocity_performance_forecasting",
    python_namespace="powerlifting_state_research.benchmarks.seasonal_five_target_load_velocity_performance_forecasting",
    docs_path="docs/benchmarks/seasonal-five-target-load-velocity-performance-forecasting.md",
    test_path="tests/benchmarks/seasonal_five_target_load_velocity_performance_forecasting/test_spec.py",
    historical_specimen_status=HistoricalSpecimenStatus.PARTIALLY_RECONSTRUCTED,
    historical_qualification_state=HistoricalQualificationState.NOT_QUALIFIED_OR_UNRESOLVED,
    completeness_status=CompletenessStatus.PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS,
    public_implementation_status=IMPLEMENTATION_STATUS,
    identity_authority=BenchmarkIdentityAuthority.HISTORICAL_PROJECTION,
    target_ontology="MULTI_OUTPUT_OTHER",
    task_type="MULTI_OUTPUT_SEASONAL_PERFORMANCE_FORECAST",
    component_references=(
        COMPONENT_REGISTRIES[ComponentClass.WORLD]["seasonal_load_velocity_and_performance"],
        ComponentReference(
            ComponentClass.POPULATION, None, ComponentResolution.UNRESOLVED_DIRECT_ID
        ),
        ComponentReference(
            ComponentClass.INTERVENTION_REGIME, None, ComponentResolution.UNRESOLVED_DIRECT_ID
        ),
        COMPONENT_REGISTRIES[ComponentClass.OBSERVATION_MODEL][
            "seasonal_multi_channel_observation"
        ],
        COMPONENT_REGISTRIES[ComponentClass.DATASET_SPEC][
            "seasonal_five_target_load_velocity_performance_forecasting_sampling_design"
        ],
        COMPONENT_REGISTRIES[ComponentClass.TASK]["seasonal_five_target_performance_forecast"],
        COMPONENT_REGISTRIES[ComponentClass.QOI]["seasonal_five_target_performance_outputs"],
        COMPONENT_REGISTRIES[ComponentClass.REPRESENTATION]["seasonal_public_table_inputs"],
        COMPONENT_REGISTRIES[ComponentClass.EVALUATION][
            "seasonal_five_output_consistency_evaluation"
        ],
    ),
)
