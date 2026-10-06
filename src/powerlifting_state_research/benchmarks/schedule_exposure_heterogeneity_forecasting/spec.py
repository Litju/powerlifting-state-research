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
    display_name="Schedule/Exposure Heterogeneity Four-Target Forecasting",
    slug="schedule_exposure_heterogeneity_forecasting",
    python_namespace="powerlifting_state_research.benchmarks.schedule_exposure_heterogeneity_forecasting",
    docs_path="docs/benchmarks/schedule-exposure-heterogeneity-forecasting.md",
    test_path="tests/benchmarks/schedule_exposure_heterogeneity_forecasting/test_spec.py",
    historical_specimen_status=HistoricalSpecimenStatus.PARTIALLY_RECONSTRUCTED,
    historical_qualification_state=HistoricalQualificationState.NOT_QUALIFIED_OR_UNRESOLVED,
    completeness_status=CompletenessStatus.PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS,
    public_implementation_status=IMPLEMENTATION_STATUS,
    target_ontology="MULTI_OUTPUT_OTHER",
    task_type="FOUR_OUTPUT_25_DAY_FORECAST",
    component_references=(
        COMPONENT_REGISTRIES[ComponentClass.WORLD]["schedule_exposure_heterogeneity"],
        ComponentReference(
            ComponentClass.POPULATION, None, ComponentResolution.UNRESOLVED_DIRECT_ID
        ),
        ComponentReference(
            ComponentClass.INTERVENTION_REGIME, None, ComponentResolution.UNRESOLVED_DIRECT_ID
        ),
        COMPONENT_REGISTRIES[ComponentClass.OBSERVATION_MODEL]["schedule_reporting_observation"],
        COMPONENT_REGISTRIES[ComponentClass.DATASET_SPEC][
            "schedule_exposure_heterogeneity_forecasting_sampling_design"
        ],
        COMPONENT_REGISTRIES[ComponentClass.TASK]["four_performance_target_forecast"],
        COMPONENT_REGISTRIES[ComponentClass.QOI]["four_performance_targets"],
        COMPONENT_REGISTRIES[ComponentClass.REPRESENTATION]["four_target_temporal_inputs"],
        COMPONENT_REGISTRIES[ComponentClass.EVALUATION]["four_target_weighted_evaluation"],
    ),
)
