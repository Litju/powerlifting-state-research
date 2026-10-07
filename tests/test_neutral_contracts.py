from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from powerlifting_state_research.artifacts.hashes import sha256_bytes
from powerlifting_state_research.artifacts.manifests import RightsMetadata
from powerlifting_state_research.components import COMPONENT_REGISTRIES, WORLD_DECLARATIONS
from powerlifting_state_research.components.source_identity_provenance import (
    SOURCE_COMPONENT_ALIASES,
)
from powerlifting_state_research.contracts.benchmark import (
    BenchmarkIdentityAuthority,
    ClaimScope,
    ComponentIdentity,
    DecisionCutoff,
    IdentityResolution,
)
from powerlifting_state_research.contracts.comparability import (
    ComparisonProfile,
    EstimandKind,
    SupportAlignment,
    assess_comparability,
)
from powerlifting_state_research.contracts.components import ComponentClass
from powerlifting_state_research.contracts.datasets import (
    ArtifactHash,
    DatasetRealizationManifest,
    ObservationAvailability,
    SplitIdentity,
    SupportSummary,
    TemporalCoverage,
)
from powerlifting_state_research.contracts.prediction import (
    InformationKind,
    InputField,
    MissingPredictionPolicy,
    NonFiniteOutputPolicy,
    OrderingAlignmentPolicy,
    OutputField,
    PredictionContract,
)
from powerlifting_state_research.contracts.serialization import canonical_json_bytes
from powerlifting_state_research.contracts.shifts import (
    ShiftCategory,
    ShiftDeclaration,
    SupportRelation,
)
from powerlifting_state_research.evaluation.metrics import (
    MetricName,
    MetricStatus,
    NonFiniteMetricInputPolicy,
    canonical_target_metrics,
)
from powerlifting_state_research.evaluation.protocols import (
    EvaluationResult,
    MetricEvidenceStatus,
    MetricIdentity,
    PredictionArtifactReference,
    ResultStatus,
)
from powerlifting_state_research.models.references import (
    DeterminismStatus,
    EnvironmentProvenance,
    ModelReference,
    RNGProvenance,
    TrainingProtocolReference,
)
from powerlifting_state_research.registry import (
    BENCHMARK_REGISTRY,
    BENCHMARKS,
    query_benchmarks,
    resolve_benchmark,
    resolve_historical_alias,
)

TRANSIENT_EXPRESSION_BENCHMARK = BENCHMARK_REGISTRY[
    "latent_capacity_change_with_transient_expression_forecasting"
]


def _manifest(seed: int) -> DatasetRealizationManifest:
    return DatasetRealizationManifest(
        dataset_spec_id="psr:dataset-spec:test@1.0.0~000000000000",
        realization_id="test-realization",
        generator_identity="synthetic-generator@1",
        source_identity=None,
        seeds=(("population", seed),),
        replicate_ids=("replicate-1",),
        entity_count=2,
        row_count=4,
        split_identities=(SplitIdentity("test", "final evaluation", 2, 4),),
        artifact_hashes=(ArtifactHash("targets", "a" * 64, "text/csv"),),
        schema_identity="target-schema@1",
        temporal_coverage=TemporalCoverage("day", 1, 224),
        realized_intervention_support=(SupportSummary("plan", "four declared plans"),),
        observation_availability=(ObservationAvailability("performance", 4, 0),),
        provenance="Generated from the declared test generator.",
        rights=RightsMetadata("CC0-1.0", "Research authors", "REDISTRIBUTABLE"),
    )


def _prediction_contract(
    inputs: tuple[InputField, ...], *, allows_plan: bool
) -> PredictionContract:
    return PredictionContract(
        task_id="psr:task:forecast@1.0.0~000000000000",
        qoi_ids=("psr:qoi:capacity-change@1.0.0~000000000000",),
        entity_identity_fields=("athlete_id",),
        row_identity_fields=("query_id",),
        event_index="day",
        decision_cutoff=DecisionCutoff("day", 224),
        cutoff_inclusive=True,
        inputs=inputs,
        outputs=(
            OutputField(
                "delta_capacity",
                "psr:qoi:capacity-change@1.0.0~000000000000",
                "kg",
            ),
        ),
        task_allows_declared_future_plan=allows_plan,
        missing_prediction_policy=MissingPredictionPolicy.REJECT,
        non_finite_output_policy=NonFiniteOutputPolicy.REJECT,
        ordering_alignment_policy=OrderingAlignmentPolicy.ALIGN_BY_DECLARED_KEYS,
    )


def _profile(
    world: str,
    qoi: str,
    estimand: EstimandKind,
    evaluation: str,
) -> ComparisonProfile:
    return ComparisonProfile(
        world_id=world,
        qoi_ids=(qoi,),
        output_fields=(("capacity_change", "kg"),),
        metric_ids=("psr:metric:sre-ddof-0@1.0.0~000000000000",),
        evaluation_id=evaluation,
        estimand=estimand,
    )


def _changed_component_id(value: str) -> str:
    prefix, digest = value.rsplit("~", 1)
    return prefix + "~" + ("0" * 12 if digest != "0" * 12 else "1" * 12)


def test_registry_names_aliases_and_completeness_are_explicit() -> None:
    assert len(BENCHMARKS) == len(BENCHMARK_REGISTRY) == 8
    assert len(WORLD_DECLARATIONS) == 6
    assert len({world.slug for world in WORLD_DECLARATIONS}) == 6
    assert all(not name.startswith("benchmark_") for name in BENCHMARK_REGISTRY)
    for slug in (
        "stable_slope_tilt_four_target_forecasting",
        "final_origin_target_domain_evaluation",
        "parsimonious_latent_capacity_change_forecasting",
    ):
        with pytest.raises(KeyError):
            resolve_benchmark(slug)
    assert resolve_historical_alias("stable_slope_tilt_four_target_forecasting")[0].slug == (
        "four_target_load_velocity_and_competition_performance_forecasting"
    )
    assert SOURCE_COMPONENT_ALIASES["parsimonious_capacity_expression"] == (
        "latent_capacity_transient_performance_expression_dynamics"
    )
    assert "stable_slope_tilt_athlete_state" not in COMPONENT_REGISTRIES[ComponentClass.WORLD]
    assert (
        len(
            query_benchmarks(completeness_status=TRANSIENT_EXPRESSION_BENCHMARK.completeness_status)
        )
        == 1
    )
    assert not any(
        name in " ".join((spec.slug, spec.python_namespace, spec.docs_path, spec.test_path))
        for spec in BENCHMARKS
        for name in (
            "stable_slope",
            "capacity_fatigue",
            "parsimonious",
            "final_origin_target_domain",
        )
    )
    assert all(
        spec.identity_mintable is (spec is TRANSIENT_EXPRESSION_BENCHMARK) for spec in BENCHMARKS
    )
    assert all(
        spec.identity_authority is BenchmarkIdentityAuthority.HISTORICAL_PROJECTION
        for spec in BENCHMARKS
    )


def test_scientific_paths_are_migrated_across_code_tests_docs_data_and_results() -> None:
    root = Path(__file__).resolve().parents[1]
    prohibited = ("stable_slope", "capacity_fatigue", "parsimonious", "final_origin_target_domain")
    for spec in BENCHMARKS:
        module_path = Path("src") / Path(*spec.python_namespace.split("."))
        data_home = Path("data/manifests/realizations") / spec.slug
        result_home = Path("results/benchmarks") / spec.slug
        paths = (module_path, Path(spec.docs_path), Path(spec.test_path), data_home, result_home)
        assert all((root / path).exists() for path in paths)
        assert all(not any(token in path.as_posix() for token in prohibited) for path in paths)
    assert all(not any(token in world.slug for token in prohibited) for world in WORLD_DECLARATIONS)


def test_frozen_v2_identity_and_all_semantic_axes_change_the_digest() -> None:
    identity = TRANSIENT_EXPRESSION_BENCHMARK.semantic_identity
    assert identity is not None
    assert (
        identity.digest == "sha256:fbfbe59eb0a8e94b12b424c6d6837dfd455a6c5a55084bb2898b53f741cc6472"
    )
    assert TRANSIENT_EXPRESSION_BENCHMARK.benchmark_id == (
        "psr:benchmark-spec:latent-capacity-change-with-transient-expression-forecasting"
        "@1.0.0~fbfbe59eb0a8"
    )
    assert resolve_benchmark(TRANSIENT_EXPRESSION_BENCHMARK.benchmark_id or "") is (
        TRANSIENT_EXPRESSION_BENCHMARK
    )
    changed_shift = ShiftDeclaration(
        "psr:shift:observation@1.0.0~000000000000",
        ShiftCategory.OBSERVATION_SHIFT,
        "source-support",
        "target-support",
        ("sensor",),
        ("world",),
        SupportRelation.COVARIATE_SHIFT,
        "partial overlap",
        "Changed sensor availability may change prediction error.",
        identity.task_id,
        identity.qoi_ids,
        identity.evaluation_id,
        "PROPOSED",
    )
    mutations = (
        replace(
            identity,
            scientific_system_config_id=_changed_component_id(identity.scientific_system_config_id),
        ),
        replace(
            identity,
            world_id=replace(
                identity.world_id,
                id=_changed_component_id(identity.world_id.id or ""),
            ),
        ),
        replace(
            identity,
            population_id=replace(
                identity.population_id,
                system_config_id=_changed_component_id(
                    identity.population_id.system_config_id or ""
                ),
            ),
        ),
        replace(
            identity,
            intervention_regime_id=replace(
                identity.intervention_regime_id,
                system_config_id=_changed_component_id(
                    identity.intervention_regime_id.system_config_id or ""
                ),
            ),
        ),
        replace(
            identity,
            observation_model_id=replace(
                identity.observation_model_id,
                id=_changed_component_id(identity.observation_model_id.id or ""),
            ),
        ),
        replace(identity, dataset_spec_id=_changed_component_id(identity.dataset_spec_id)),
        replace(identity, task_id=_changed_component_id(identity.task_id)),
        replace(identity, qoi_ids=(_changed_component_id(identity.qoi_ids[0]),)),
        replace(
            identity,
            prediction_information_boundary=replace(
                identity.prediction_information_boundary,
                decision_cutoff=replace(
                    identity.prediction_information_boundary.decision_cutoff,
                    value=225,
                ),
            ),
        ),
        replace(
            identity,
            representation_id=_changed_component_id(identity.representation_id or ""),
        ),
        replace(identity, evaluation_id=_changed_component_id(identity.evaluation_id)),
        replace(identity, declared_shift_relations=(changed_shift,)),
        replace(identity, claim_scope=(*identity.claim_scope, ClaimScope.MECHANISTIC_MODEL)),
    )
    assert all(item.digest != identity.digest for item in mutations)


def test_identity_authority_scopes_historical_system_config_resolution() -> None:
    spec = TRANSIENT_EXPRESSION_BENCHMARK
    identity = spec.semantic_identity
    assert identity is not None
    assert identity.digest == (
        "sha256:fbfbe59eb0a8e94b12b424c6d6837dfd455a6c5a55084bb2898b53f741cc6472"
    )
    with pytest.raises(ValueError, match="PUBLIC_NATIVE.*explicit direct"):
        replace(spec, identity_authority=BenchmarkIdentityAuthority.PUBLIC_NATIVE)

    direct_identity = replace(
        identity,
        population_id=ComponentIdentity(
            IdentityResolution.DIRECT,
            id="psr:population:public-native@1.0.0~000000000000",
        ),
        intervention_regime_id=ComponentIdentity(
            IdentityResolution.DIRECT,
            id="psr:intervention-regime:public-native@1.0.0~000000000000",
        ),
    )
    historical_projection = replace(spec, semantic_identity=direct_identity)
    public_native = replace(
        historical_projection,
        identity_authority=BenchmarkIdentityAuthority.PUBLIC_NATIVE,
    )
    assert public_native.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE
    assert public_native.semantic_digest == historical_projection.semantic_digest


def test_names_paths_realizations_models_and_prose_do_not_change_benchmark_identity() -> None:
    spec = TRANSIENT_EXPRESSION_BENCHMARK
    renamed = replace(
        spec,
        display_name="Descriptive wording only",
        slug="another_readable_label",
        python_namespace="new.package.path",
        docs_path="docs/new.md",
        test_path="tests/new.py",
        contract_schema_version="2.0.0",
        version="2.0.0",
    )
    assert renamed.semantic_digest == spec.semantic_digest
    assert _manifest(7).digest != _manifest(8).digest
    assert (
        spec.semantic_digest
        == "sha256:fbfbe59eb0a8e94b12b424c6d6837dfd455a6c5a55084bb2898b53f741cc6472"
    )
    assert canonical_json_bytes({"name": "e\u0301"}) == canonical_json_bytes({"name": "é"})
    assert sha256_bytes(b"same content") == sha256_bytes(b"same content")


def test_dataset_realization_identity_is_separate_and_records_rights_and_hashes() -> None:
    first = _manifest(11)
    second = _manifest(12)
    assert first.dataset_spec_id == second.dataset_spec_id
    assert first.identity_id != second.identity_id
    assert first.digest.startswith("sha256:")
    assert first.canonical_serialization == first.canonical_serialization
    assert first.artifact_hashes[0].sha256 == "a" * 64
    assert first.rights.license_expression == "CC0-1.0"


def test_prediction_firewall_allows_history_and_permitted_plan_only() -> None:
    history = InputField("weekly_observations", InformationKind.HISTORICAL_OBSERVATION)
    context = InputField("lift_id", InformationKind.STATIC_CONTEXT)
    plan = InputField("declared_plan", InformationKind.DECLARED_FUTURE_PLAN)
    _prediction_contract((history, context), allows_plan=False).validate()
    _prediction_contract((history, context, plan), allows_plan=True).validate()
    denied_plan = _prediction_contract((history, plan), allows_plan=False)
    with pytest.raises(ValueError, match="future plan input"):
        denied_plan.validate()
    for kind in (
        InformationKind.FUTURE_REALIZED_PERFORMANCE,
        InformationKind.FUTURE_OBSERVATION,
        InformationKind.FUTURE_PROCESS_DISTURBANCE,
        InformationKind.UNKNOWN_FUTURE_INTERVENTION_DEVIATION,
        InformationKind.TARGET_DERIVED,
        InformationKind.EVALUATION_TRUTH,
    ):
        contract = _prediction_contract((InputField("leak", kind),), allows_plan=True)
        with pytest.raises(ValueError, match="forbidden prediction input"):
            contract.validate()


def test_per_target_metrics_and_invalid_value_policies() -> None:
    result = canonical_target_metrics("squat", (1.0, 2.0, 3.0), (1.0, 2.0, 4.0), unit="kg")
    values = {metric.metric: metric for metric in result.metrics}
    assert math.isclose(values[MetricName.RMSE].value or 0.0, math.sqrt(1 / 3))
    assert math.isclose(values[MetricName.MAE].value or 0.0, 1 / 3)
    assert values[MetricName.R2].value == 0.5
    assert math.isclose(values[MetricName.SRE].value or 0.0, math.sqrt(0.5))
    assert values[MetricName.RMSE].unit == "kg"
    assert values[MetricName.SRE].unit == "1"

    empty = canonical_target_metrics("squat", (), (), unit="kg")
    assert all(
        metric.status is MetricStatus.UNDEFINED and metric.reason == "EMPTY_TRUTH"
        for metric in empty.metrics
    )
    constant = canonical_target_metrics("squat", (2.0, 2.0), (2.0, 3.0), unit="kg")
    constant_values = {metric.metric: metric for metric in constant.metrics}
    assert constant_values[MetricName.R2].reason == "CONSTANT_TRUTH"
    assert constant_values[MetricName.SRE].reason == "ZERO_TRUTH_POPULATION_SD"
    with pytest.raises(ValueError, match="missing predictions"):
        canonical_target_metrics("squat", (1.0,), (None,), unit="kg")
    missing = canonical_target_metrics(
        "squat",
        (1.0,),
        (None,),
        unit="kg",
        missing_prediction_policy=MissingPredictionPolicy.MARK_TARGET_UNDEFINED,
    )
    assert all(metric.reason == "MISSING_PREDICTION" for metric in missing.metrics)
    with pytest.raises(ValueError, match="non-finite"):
        canonical_target_metrics("squat", (1.0,), (float("nan"),), unit="kg")
    non_finite = canonical_target_metrics(
        "squat",
        (1.0,),
        (float("nan"),),
        unit="kg",
        non_finite_policy=NonFiniteMetricInputPolicy.MARK_TARGET_UNDEFINED,
    )
    assert all(metric.reason == "NON_FINITE_VALUE" for metric in non_finite.metrics)


def test_shifts_and_historical_comparability_rules_are_executable() -> None:
    identity = TRANSIENT_EXPRESSION_BENCHMARK.semantic_identity
    assert identity is not None
    with pytest.raises(ValueError, match="OOD alone"):
        ShiftDeclaration(
            "psr:shift:observation@1.0.0~000000000000",
            ShiftCategory.OBSERVATION_SHIFT,
            "source",
            "target",
            ("OOD",),
            ("world",),
            SupportRelation.DISJOINT,
            "OOD",
            "A test hypothesis.",
            identity.task_id,
            identity.qoi_ids,
            identity.evaluation_id,
            "PROPOSED",
        )
    observed = _profile(
        "psr:world:dose-history@1.0.0~000000000000",
        "psr:qoi:observed-origin-change@1.0.0~000000000000",
        EstimandKind.OBSERVED_ORIGIN_PERFORMANCE_CHANGE,
        "psr:evaluation:common@1.0.0~000000000000",
    )
    latent = _profile(
        "psr:world:dose-history@1.0.0~000000000000",
        "psr:qoi:latent-capacity-change@1.0.0~000000000000",
        EstimandKind.LATENT_CAPACITY_CHANGE,
        "psr:evaluation:common@1.0.0~000000000000",
    )
    observed_vs_latent = assess_comparability(observed, latent)
    assert not observed_vs_latent.direct_performance_comparable

    latent_origin = _profile(
        "psr:world:dose-history@1.0.0~000000000000",
        "psr:qoi:latent-capacity-change@1.0.0~000000000000",
        EstimandKind.LATENT_CAPACITY_CHANGE,
        "psr:evaluation:latent-origin@1.0.0~000000000000",
    )
    transient_expression = _profile(
        "psr:world:transient-expression@1.0.0~000000000000",
        "psr:qoi:latent-capacity-change@1.0.0~000000000000",
        EstimandKind.LATENT_CAPACITY_CHANGE,
        "psr:evaluation:transient-expression@1.0.0~000000000000",
    )
    unmatched = assess_comparability(
        latent_origin,
        transient_expression,
        common_evaluation_id="psr:evaluation:common@1.0.0~000000000000",
        support_alignment=SupportAlignment.UNMATCHED,
    )
    assert unmatched.support_match_required and not unmatched.direct_performance_comparable
    matched = assess_comparability(
        latent_origin,
        transient_expression,
        common_evaluation_id="psr:evaluation:common@1.0.0~000000000000",
        support_alignment=SupportAlignment.STRATIFIED_MATCHED,
    )
    assert matched.direct_performance_comparable
    with pytest.raises(ValueError, match="common evaluation ID"):
        assess_comparability(
            latent_origin,
            transient_expression,
            common_evaluation_id="common-evaluation",
            support_alignment=SupportAlignment.STRATIFIED_MATCHED,
        )
    with pytest.raises(ValueError, match="common evaluation ID"):
        assess_comparability(
            latent_origin,
            transient_expression,
            common_evaluation_id="psr:metric:common@1.0.0~000000000000",
            support_alignment=SupportAlignment.STRATIFIED_MATCHED,
        )


def test_evaluation_result_binds_model_data_environment_and_metric_records() -> None:
    manifest = _manifest(51)
    target = canonical_target_metrics("squat", (1.0, 2.0), (1.0, 3.0), unit="kg")
    metric_slugs = {
        MetricName.RMSE: "rmse",
        MetricName.MAE: "mae",
        MetricName.R2: "r2",
        MetricName.SRE: "sre-ddof-0",
    }
    metric_ids = tuple(
        MetricIdentity(
            f"psr:metric:{metric_slugs[metric]}@1.0.0~000000000000",
            metric,
            "canonical per-target definition",
            MetricEvidenceStatus.CANONICAL_RESEARCH,
        )
        for metric in MetricName
    )
    benchmark_id = TRANSIENT_EXPRESSION_BENCHMARK.benchmark_id or ""
    benchmark_digest = TRANSIENT_EXPRESSION_BENCHMARK.semantic_digest or ""
    model = ModelReference("psr:model:example@1.0.0~000000000000")
    result_rights = RightsMetadata("CC-BY-4.0", "Research authors", "REDISTRIBUTABLE")
    prediction = PredictionArtifactReference(
        artifact_id="predictions-1",
        benchmark_id=benchmark_id,
        benchmark_spec_digest=benchmark_digest,
        dataset_realization_id=manifest.identity_id,
        dataset_realization_digest=manifest.digest,
        model_id=model.model_id,
        output_schema_identity="schema:targets@1",
        row_count=2,
        content_sha256=sha256_bytes(b"prediction bytes"),
        rights=result_rights,
    )
    result = EvaluationResult(
        benchmark_id=benchmark_id,
        benchmark_spec_digest=benchmark_digest,
        dataset_realization_id=manifest.identity_id,
        dataset_realization_digest=manifest.digest,
        model=model,
        training_protocol=TrainingProtocolReference(
            None, "Analytic comparator has no training run."
        ),
        fitted_instance=None,
        checkpoint=None,
        environment=EnvironmentProvenance("env:local", "3.12", "linux", "dependencies:none"),
        rng=RNGProvenance(DeterminismStatus.SEEDED, (("test", 12),)),
        prediction_artifact=prediction,
        evaluation_id="psr:evaluation:canonical-target-wise@1.0.0~000000000000",
        metric_identities=metric_ids,
        targets=(target,),
        aggregations=(),
        stratifications=(),
        exclusions=(),
        uncertainty=(),
        status=ResultStatus.COMPLETE,
        rights=result_rights,
    )
    changed_prediction = replace(prediction, content_sha256=sha256_bytes(b"corrected predictions"))
    changed_model = replace(
        result,
        model=ModelReference("psr:model:other@1.0.0~000000000000"),
        prediction_artifact=replace(
            prediction,
            model_id="psr:model:other@1.0.0~000000000000",
        ),
    )
    changed_content = replace(result, prediction_artifact=changed_prediction)
    assert result.digest != changed_model.digest
    assert result.digest != changed_content.digest
    assert result.prediction_artifact.identity_id != changed_prediction.identity_id
    assert result.result_id.endswith(result.digest)


def test_checked_in_exports_match_python_sources() -> None:
    from powerlifting_state_research.exports import check_exports

    assert check_exports() == ()
