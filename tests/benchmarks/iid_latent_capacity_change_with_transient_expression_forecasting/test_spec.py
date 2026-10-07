from dataclasses import replace

import pytest

from powerlifting_state_research.contracts.benchmark import (
    BenchmarkIdentityAuthority,
    HistoricalQualificationState,
    HistoricalSpecimenStatus,
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
    assert public.historical_specimen_status is HistoricalSpecimenStatus.NOT_HISTORICAL
    assert public.historical_qualification_state is HistoricalQualificationState.NOT_APPLICABLE
    assert public.semantic_digest == (
        "sha256:49b4994f7df4443c6f8d80c968d456d611b5e7886c32659727e8c351dfed9de3"
    )
    assert public.related_benchmark_slugs == (historical.slug,)
    assert public_identity.world_id.resolution is IdentityResolution.DIRECT
    assert public_identity.population_id.resolution is IdentityResolution.DIRECT
    assert public_identity.intervention_regime_id.resolution is IdentityResolution.DIRECT
    assert public_identity.observation_model_id.resolution is IdentityResolution.DIRECT
    assert public_identity.world_id == historical_identity.world_id
    assert public_identity.dataset_spec_id != historical_identity.dataset_spec_id
    assert public.semantic_digest != historical.semantic_digest


def test_historical_states_cannot_be_applied_to_the_wrong_authority() -> None:
    historical = resolve_benchmark("latent_capacity_change_with_transient_expression_forecasting")
    public = resolve_benchmark("iid_latent_capacity_change_with_transient_expression_forecasting")

    with pytest.raises(ValueError, match="PUBLIC_NATIVE.*non-historical"):
        replace(public, historical_specimen_status=HistoricalSpecimenStatus.REPRODUCIBLE_SPEC)
    with pytest.raises(ValueError, match="PUBLIC_NATIVE.*historical qualification"):
        replace(
            public,
            historical_qualification_state=HistoricalQualificationState.NOT_QUALIFIED_OR_UNRESOLVED,
        )
    with pytest.raises(ValueError, match="HISTORICAL_PROJECTION.*historical status"):
        replace(historical, historical_specimen_status=HistoricalSpecimenStatus.NOT_HISTORICAL)
    with pytest.raises(ValueError, match="HISTORICAL_PROJECTION.*historical status"):
        replace(
            historical,
            historical_qualification_state=HistoricalQualificationState.NOT_APPLICABLE,
        )


def test_exports_select_authority_specific_research_metadata() -> None:
    from powerlifting_state_research.exports import registry_document

    records = {item["slug"]: item for item in registry_document()["benchmarks"]}
    historical_research = records["latent_capacity_change_with_transient_expression_forecasting"][
        "research"
    ]
    public_research = records["iid_latent_capacity_change_with_transient_expression_forecasting"][
        "research"
    ]

    assert historical_research.historical_objective is not None
    assert public_research.historical_objective is None
    assert public_research.historical_objective_evidence is None
    assert public_research.dataset_spec_difference is not None
    assert "scrambled Sobol" in public_research.dataset_spec_difference
    assert public_research.limitations
    assert public_research.related_benchmark_relationship is not None
