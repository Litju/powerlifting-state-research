"""Typed scientific benchmark specification."""

from __future__ import annotations

from ...components import COMPONENT_REGISTRIES
from ...contracts.benchmark import (
    BenchmarkSemanticIdentity,
    BenchmarkSpec,
    ClaimScope,
    CompletenessStatus,
    ComponentIdentity,
    DecisionCutoff,
    HistoricalQualificationState,
    HistoricalSpecimenStatus,
    IdentityResolution,
    ImplementationStatus,
    PredictionInformationBoundary,
)
from ...contracts.components import ComponentClass, ComponentReference, ComponentResolution

IMPLEMENTATION_STATUS = ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING

SPEC = BenchmarkSpec(
    display_name=("Latent Capacity-Change Forecasting with Transient Performance Expression"),
    slug="latent_capacity_change_with_transient_expression_forecasting",
    python_namespace="powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting",
    docs_path="docs/benchmarks/latent-capacity-change-with-transient-expression-forecasting.md",
    test_path="tests/benchmarks/latent_capacity_change_with_transient_expression_forecasting/test_spec.py",
    historical_specimen_status=HistoricalSpecimenStatus.REPRODUCIBLE_SPEC,
    historical_qualification_state=HistoricalQualificationState.QUALIFIED_HISTORICAL,
    completeness_status=CompletenessStatus.FULL_FROM_EXISTING_EVIDENCE,
    public_implementation_status=IMPLEMENTATION_STATUS,
    target_ontology="LATENT_CAPACITY_CHANGE",
    task_type="LATENT_CAPACITY_CHANGE_FORECAST",
    component_references=(
        COMPONENT_REGISTRIES[ComponentClass.WORLD][
            "latent_capacity_transient_performance_expression_dynamics"
        ],
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
            "latent_capacity_change_with_transient_expression_forecasting_sampling_design"
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
    semantic_identity=BenchmarkSemanticIdentity(
        scientific_system_config_id=(
            "psr:scientific-system-config:pl-response-v2-parsimonious-production-"
            "historical-system@1.0.0~81141316f605"
        ),
        world_id=ComponentIdentity(
            IdentityResolution.DIRECT,
            id="psr:world:world-v2-parsimonious-response-world@1.0.0~a1afbf2f5c1e",
        ),
        population_id=ComponentIdentity(
            IdentityResolution.COMMITTED_BY_SYSTEM_CONFIG,
            system_config_id=(
                "psr:scientific-system-config:pl-response-v2-parsimonious-production-"
                "historical-system@1.0.0~81141316f605"
            ),
        ),
        intervention_regime_id=ComponentIdentity(
            IdentityResolution.COMMITTED_BY_SYSTEM_CONFIG,
            system_config_id=(
                "psr:scientific-system-config:pl-response-v2-parsimonious-production-"
                "historical-system@1.0.0~81141316f605"
            ),
        ),
        observation_model_id=ComponentIdentity(
            IdentityResolution.DIRECT,
            id=(
                "psr:observation-model:world-v2-performance-expression-observation@"
                "1.0.0~c8a52272a9cd"
            ),
        ),
        dataset_spec_id=(
            "psr:dataset-spec:pl-response-v2-parsimonious-production-sampling-design@"
            "1.0.0~7098655518cd"
        ),
        task_id="psr:task:latent-capacity-change@1.0.0~44fc77353e7a",
        qoi_ids=("psr:qoi:latent-capacity-change@1.0.0~675491124046",),
        prediction_information_boundary=PredictionInformationBoundary(
            decision_cutoff=DecisionCutoff("day", 224),
            cutoff_inclusive=True,
            history_observation_last_day=223,
            static_or_context_inputs="only task-declared fields",
            declared_future_plan_visible=True,
        ),
        representation_id=(
            "psr:representation:world-v2-participant-inputs-json-v2@1.0.0~2c2c7f0222c6"
        ),
        evaluation_id="psr:evaluation:world-v2-canonical-sre-evaluation@1.0.0~2b606bcf527f",
        declared_shift_relations=(),
        claim_scope=(ClaimScope.PREDICTIVE, ClaimScope.SYNTHETIC_BENCHMARK),
    ),
)
