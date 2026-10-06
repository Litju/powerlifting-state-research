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
    display_name=(
        "Parsimonious Latent Capacity-Change Forecasting with Transient Performance Expression"
    ),
    slug="parsimonious_latent_capacity_change_forecasting",
    python_namespace="powerlifting_state_research.benchmarks.parsimonious_latent_capacity_change_forecasting",
    docs_path="docs/benchmarks/parsimonious-latent-capacity-change-forecasting.md",
    test_path="tests/benchmarks/parsimonious_latent_capacity_change_forecasting/test_spec.py",
    historical_specimen_status=HistoricalSpecimenStatus.REPRODUCIBLE_SPEC,
    historical_qualification_state=HistoricalQualificationState.QUALIFIED_HISTORICAL,
    completeness_status=CompletenessStatus.FULL_FROM_EXISTING_EVIDENCE,
    public_implementation_status=IMPLEMENTATION_STATUS,
    target_ontology="LATENT_CAPACITY_CHANGE",
    task_type="LATENT_CAPACITY_CHANGE_FORECAST",
    component_references=(
        COMPONENT_REGISTRIES[ComponentClass.WORLD]["parsimonious_capacity_expression"],
        ComponentReference(
            ComponentClass.POPULATION, None, ComponentResolution.COMMITTED_BY_SYSTEM_CONFIG
        ),
        ComponentReference(
            ComponentClass.INTERVENTION_REGIME, None, ComponentResolution.COMMITTED_BY_SYSTEM_CONFIG
        ),
        COMPONENT_REGISTRIES[ComponentClass.OBSERVATION_MODEL][
            "performance_expression_observation"
        ],
        COMPONENT_REGISTRIES[ComponentClass.DATASET_SPEC][
            "parsimonious_latent_capacity_change_forecasting_sampling_design"
        ],
        COMPONENT_REGISTRIES[ComponentClass.TASK]["latent_capacity_change_forecast"],
        COMPONENT_REGISTRIES[ComponentClass.QOI]["latent_capacity_change"],
        COMPONENT_REGISTRIES[ComponentClass.REPRESENTATION][
            "weekly_performance_history_and_plan_inputs"
        ],
        COMPONENT_REGISTRIES[ComponentClass.EVALUATION][
            "latent_capacity_change_canonical_sre_evaluation"
        ],
    ),
)
