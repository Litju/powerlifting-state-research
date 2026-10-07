from powerlifting_state_research.contracts.benchmark import (
    BenchmarkIdentityAuthority,
    HistoricalQualificationState,
    IdentityResolution,
    ImplementationStatus,
)
from powerlifting_state_research.registry import resolve_benchmark


def test_iid_variant_has_distinct_public_native_identity() -> None:
    historical = resolve_benchmark("latent_capacity_change_with_transient_expression_forecasting")
    public = resolve_benchmark("iid_latent_capacity_change_with_transient_expression_forecasting")
    historical_identity = historical.semantic_identity
    public_identity = public.semantic_identity
    assert historical_identity is not None
    assert public_identity is not None

    assert historical.semantic_digest == (
        "sha256:fbfbe59eb0a8e94b12b424c6d6837dfd455a6c5a55084bb2898b53f741cc6472"
    )
    assert historical.identity_authority is BenchmarkIdentityAuthority.HISTORICAL_PROJECTION
    assert (
        historical.public_implementation_status
        is ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING
    )
    assert historical.related_benchmark_slugs == (public.slug,)

    assert public.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE
    assert public.public_implementation_status is ImplementationStatus.PUBLIC_IMPLEMENTED
    assert (
        public.historical_qualification_state
        is HistoricalQualificationState.NOT_QUALIFIED_OR_UNRESOLVED
    )
    assert public.related_benchmark_slugs == (historical.slug,)
    assert public_identity.world_id.resolution is IdentityResolution.DIRECT
    assert public_identity.population_id.resolution is IdentityResolution.DIRECT
    assert public_identity.intervention_regime_id.resolution is IdentityResolution.DIRECT
    assert public_identity.observation_model_id.resolution is IdentityResolution.DIRECT
    assert public_identity.world_id == historical_identity.world_id
    assert public_identity.dataset_spec_id != historical_identity.dataset_spec_id
    assert public.semantic_digest != historical.semantic_digest
