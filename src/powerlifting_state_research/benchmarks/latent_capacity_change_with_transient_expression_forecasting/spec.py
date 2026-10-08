"""Historical projection and public-native IID benchmark identities."""

from __future__ import annotations

from collections.abc import Sequence

from ...components import COMPONENT_REGISTRIES, WORLD_DECLARATIONS
from ...contracts.benchmark import (
    BenchmarkIdentityAuthority,
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
from ...contracts.serialization import sha256_record
from ...evaluation.identity import EVALUATION_ID
from .interventions import (
    DOSE_INTENSITY_PAIRS,
    HISTORY_TEMPLATES,
    ORIGIN_DAY,
    PLAN_END_DAY,
)
from .observations import (
    ASSESSMENT_CV,
    HISTORY_OBSERVATION_DAYS,
    LOAD_FRACTION_RANGE,
    RELATIVE_LOAD_DOMAIN,
    VELOCITY_CONSTANTS,
    VELOCITY_SD_MPS,
)
from .population import (
    ADAPTATION_RETENTION_28D_RANGE,
    ADAPTATION_UTILIZATION_RANGE,
    BASELINE_SCALE_KG_RANGE,
    BENCH_RATIO_RANGE,
    COORDINATE_ORDER,
    DEADLIFT_RATIO_RANGE,
    REFERENCE_DOSE_PRODUCT,
    REFERENCE_STIMULUS_RANGE,
    SUPPRESSION_RETENTION_RANGE,
    SUPPRESSION_UTILIZATION_RANGE,
)

HISTORICAL_SLUG = "latent_capacity_change_with_transient_expression_forecasting"
PUBLIC_NATIVE_SLUG = "iid_latent_capacity_change_with_transient_expression_forecasting"
WORLD_ID = next(
    world.component_identity_id
    for world in WORLD_DECLARATIONS
    if world.slug == "latent_capacity_transient_performance_expression_dynamics"
)


def _decimal_values(values: Sequence[float]) -> tuple[str, ...]:
    return tuple(repr(value) for value in values)


def _public_native_id(component_class: str, slug: str, semantics: dict[str, object]) -> str:
    digest = sha256_record(
        {
            "format": "PSR_PUBLIC_NATIVE_COMPONENT_ID_V1",
            "component_class": component_class,
            "slug": slug,
            "version": "1.0.0",
            "semantics": semantics,
        },
        reject_floats=True,
    )
    return f"psr:{component_class}:{slug}@1.0.0~{digest[7:19]}"


PUBLIC_NATIVE_POPULATION_ID = _public_native_id(
    "population",
    "latent-capacity-transient-uniform-coordinate-population",
    {
        "coordinate_count": len(COORDINATE_ORDER),
        "coordinate_order": COORDINATE_ORDER,
        "coordinate_support": "[0,1)",
        "baseline_scale_kg": _decimal_values(BASELINE_SCALE_KG_RANGE),
        "bench_ratio": _decimal_values(BENCH_RATIO_RANGE),
        "deadlift_ratio": _decimal_values(DEADLIFT_RATIO_RANGE),
        "reference_dose_product": repr(REFERENCE_DOSE_PRODUCT),
        "reference_stimulus": _decimal_values(REFERENCE_STIMULUS_RANGE),
        "adaptation_utilization": _decimal_values(ADAPTATION_UTILIZATION_RANGE),
        "adaptation_retention_28_days": _decimal_values(ADAPTATION_RETENTION_28D_RANGE),
        "suppression_utilization": _decimal_values(SUPPRESSION_UTILIZATION_RANGE),
        "suppression_retention": _decimal_values(SUPPRESSION_RETENTION_RANGE),
        "transforms": (
            "baseline scale log-linear",
            "ratios and utilization linear",
            "gains are utilization/reference stimulus",
            "adaptation time is -28/log(1-retention_28d)",
            "suppression time is -1/log(daily_retention)",
            "stimulus reference is dose_product*(1-reference_stimulus)/reference_stimulus",
        ),
    },
)
PUBLIC_NATIVE_INTERVENTION_REGIME_ID = _public_native_id(
    "intervention-regime",
    "latent-capacity-transient-balanced-plan-history-regime",
    {
        "dose_intensity_pairs": tuple(
            (key, _decimal_values(value)) for key, value in sorted(DOSE_INTENSITY_PAIRS.items())
        ),
        "history_templates": HISTORY_TEMPLATES,
        "origin_day": ORIGIN_DAY,
        "plan_end_day": PLAN_END_DAY,
        "declared_plans": "constant dose/intensity pairs from origin through day 279",
        "history_regime": "four fixed piecewise-constant weekly schedules per lift",
    },
)
PUBLIC_NATIVE_OBSERVATION_MODEL_ID = _public_native_id(
    "observation-model",
    "latent-capacity-transient-performance-observation",
    {
        "observation_days": HISTORY_OBSERVATION_DAYS,
        "assessment_cv": tuple((key, repr(value)) for key, value in sorted(ASSESSMENT_CV.items())),
        "velocity_sd_mps": tuple(
            (key, repr(value)) for key, value in sorted(VELOCITY_SD_MPS.items())
        ),
        "velocity_constants": tuple(
            (key, _decimal_values(value)) for key, value in sorted(VELOCITY_CONSTANTS.items())
        ),
        "load_fraction": _decimal_values(LOAD_FRACTION_RANGE),
        "relative_load_domain": _decimal_values(RELATIVE_LOAD_DOMAIN),
        "assessment": "expressed_performance*(1+Normal(0,cv_lift))",
        "prescribed_load": "Uniform(load_fraction)*assessment",
        "velocity": "endpoint+span*((1-relative_load)/0.60)^exponent+Normal(0,sigma_lift)",
    },
)
PUBLIC_NATIVE_DATASET_SPEC_ID = _public_native_id(
    "dataset-spec",
    "latent-capacity-transient-iid-sampling-design",
    {
        "population_sampling_algorithm": (
            "IID pseudorandom Uniform(0,1) coordinates from random.Random(population_seed).random"
        ),
        "population_dimensions": len(COORDINATE_ORDER),
        "coordinate_order": COORDINATE_ORDER,
        "coordinate_assignment": "draw in entity-index order, one complete vector per entity",
        "row_unit": "one entity, one declared plan, one horizon, all lifts",
        "strata": "four declared plans by three horizons, balanced per split",
        "history_allocation": (
            "all 64 three-lift template combinations balanced per stratum and split"
        ),
        "entity_assignment_order": "intervention seed shuffles strata and template groups; "
        "split seed shuffles labels within each fixed template group",
        "split_semantics": "train and same-law validation entities are disjoint",
    },
)
PUBLIC_NATIVE_SYSTEM_CONFIG_ID = _public_native_id(
    "scientific-system-config",
    "latent-capacity-transient-public-system",
    {
        "world_id": WORLD_ID,
        "population_id": PUBLIC_NATIVE_POPULATION_ID,
        "intervention_regime_id": PUBLIC_NATIVE_INTERVENTION_REGIME_ID,
        "observation_model_id": PUBLIC_NATIVE_OBSERVATION_MODEL_ID,
    },
)

_NATIVE_REFS: tuple[ComponentReference, ...] = (
    COMPONENT_REGISTRIES[ComponentClass.WORLD][
        "latent_capacity_transient_performance_expression_dynamics"
    ],
    COMPONENT_REGISTRIES[ComponentClass.POPULATION][
        "latent_capacity_transient_public_uniform_coordinates"
    ],
    COMPONENT_REGISTRIES[ComponentClass.INTERVENTION_REGIME][
        "latent_capacity_transient_public_training_regime"
    ],
    COMPONENT_REGISTRIES[ComponentClass.OBSERVATION_MODEL][
        "latent_capacity_transient_public_performance_observation"
    ],
    COMPONENT_REGISTRIES[ComponentClass.DATASET_SPEC][
        "iid_latent_capacity_change_with_transient_expression_forecasting_sampling_design"
    ],
    COMPONENT_REGISTRIES[ComponentClass.TASK]["latent_capacity_change_forecast"],
    COMPONENT_REGISTRIES[ComponentClass.QOI]["latent_capacity_change"],
    COMPONENT_REGISTRIES[ComponentClass.REPRESENTATION][
        "weekly_performance_history_and_plan_inputs"
    ],
    COMPONENT_REGISTRIES[ComponentClass.EVALUATION][
        "iid_latent_capacity_change_four_metric_validation"
    ],
    *tuple(
        COMPONENT_REGISTRIES[ComponentClass.METRIC][key]
        for key in (
            "iid_public_rmse",
            "iid_public_mae",
            "iid_public_r_squared",
            "iid_public_sre_ddof_0",
        )
    ),
)

SPEC = BenchmarkSpec(
    display_name=("Latent Capacity-Change Forecasting with Transient Performance Expression"),
    slug=HISTORICAL_SLUG,
    python_namespace=(
        "powerlifting_state_research.benchmarks."
        "latent_capacity_change_with_transient_expression_forecasting"
    ),
    docs_path="docs/benchmarks/latent-capacity-change-with-transient-expression-forecasting.md",
    test_path="tests/benchmarks/latent_capacity_change_with_transient_expression_forecasting/test_spec.py",
    historical_specimen_status=HistoricalSpecimenStatus.REPRODUCIBLE_SPEC,
    historical_qualification_state=HistoricalQualificationState.QUALIFIED_HISTORICAL,
    completeness_status=CompletenessStatus.FULL_FROM_EXISTING_EVIDENCE,
    public_implementation_status=ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING,
    identity_authority=BenchmarkIdentityAuthority.HISTORICAL_PROJECTION,
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
            ComponentClass.INTERVENTION_REGIME,
            None,
            ComponentResolution.COMMITTED_BY_SYSTEM_CONFIG,
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
            id="psr:observation-model:world-v2-performance-expression-observation@1.0.0~c8a52272a9cd",
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
    related_benchmark_slugs=(PUBLIC_NATIVE_SLUG,),
)

PUBLIC_NATIVE_SPEC = BenchmarkSpec(
    display_name=(
        "IID-Sampled Latent Capacity-Change Forecasting with Transient Performance Expression"
    ),
    slug=PUBLIC_NATIVE_SLUG,
    python_namespace=(
        "powerlifting_state_research.benchmarks."
        "latent_capacity_change_with_transient_expression_forecasting"
    ),
    docs_path="docs/benchmarks/iid-latent-capacity-change-with-transient-expression-forecasting.md",
    test_path="tests/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/test_spec.py",
    historical_specimen_status=HistoricalSpecimenStatus.NOT_HISTORICAL,
    historical_qualification_state=HistoricalQualificationState.NOT_APPLICABLE,
    completeness_status=CompletenessStatus.FULL_FROM_EXISTING_EVIDENCE,
    public_implementation_status=ImplementationStatus.PUBLIC_IMPLEMENTED,
    identity_authority=BenchmarkIdentityAuthority.PUBLIC_NATIVE,
    target_ontology="LATENT_CAPACITY_CHANGE",
    task_type="LATENT_CAPACITY_CHANGE_FORECAST",
    component_references=_NATIVE_REFS,
    semantic_identity=BenchmarkSemanticIdentity(
        scientific_system_config_id=PUBLIC_NATIVE_SYSTEM_CONFIG_ID,
        world_id=ComponentIdentity(IdentityResolution.DIRECT, id=WORLD_ID),
        population_id=ComponentIdentity(IdentityResolution.DIRECT, id=PUBLIC_NATIVE_POPULATION_ID),
        intervention_regime_id=ComponentIdentity(
            IdentityResolution.DIRECT, id=PUBLIC_NATIVE_INTERVENTION_REGIME_ID
        ),
        observation_model_id=ComponentIdentity(
            IdentityResolution.DIRECT, id=PUBLIC_NATIVE_OBSERVATION_MODEL_ID
        ),
        dataset_spec_id=PUBLIC_NATIVE_DATASET_SPEC_ID,
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
        evaluation_id=EVALUATION_ID,
        declared_shift_relations=(),
        claim_scope=(ClaimScope.PREDICTIVE, ClaimScope.SYNTHETIC_BENCHMARK),
    ),
    related_benchmark_slugs=(HISTORICAL_SLUG,),
)
