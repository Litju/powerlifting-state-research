import json
from dataclasses import replace
from pathlib import Path

import pytest

from powerlifting_state_research.benchmarks import (
    latent_capacity_change_with_transient_expression_forecasting as iid_benchmark,
)
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


def test_dataset_card_matches_canonical_machine_readable_identity() -> None:
    root = Path(__file__).resolve().parents[3]
    public = iid_benchmark.PUBLIC_NATIVE_SPEC
    registry = json.loads((root / "artifacts/registries/benchmark-registry.json").read_text())
    record = next(item for item in registry["benchmarks"] if item["slug"] == public.slug)
    manifest_path = (
        root
        / "data/manifests/realizations"
        / "latent_capacity_change_with_transient_expression_forecasting"
        / "iid-production.json"
    )
    manifest = json.loads(manifest_path.read_text())
    card = (root / manifest["source_identity"]).read_text()

    assert public.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE
    assert record["benchmark_id"] == public.benchmark_id
    assert record["semantic_digest"] == public.semantic_digest
    assert public.semantic_identity is not None
    dataset_spec_id = public.semantic_identity.dataset_spec_id
    assert dataset_spec_id == manifest["dataset_spec_id"]
    assert (
        f"generator-source-sha256={iid_benchmark.dataset.GENERATOR_SOURCE_SHA256.removeprefix('sha256:')}"
        in manifest["generator_identity"]
    )
    assert (
        f"config-sha256={iid_benchmark.dataset.PUBLIC_GENERATION_CONFIGURATION_SHA256.removeprefix('sha256:')}"
        in manifest["generator_identity"]
    )
    artifacts = {item["artifact_id"]: item["sha256"] for item in manifest["artifact_hashes"]}
    expected_identity_rows = (
        ("PUBLIC_NATIVE BenchmarkSpec", record["benchmark_id"]),
        ("BenchmarkSpec digest", record["semantic_digest"]),
        ("DatasetSpec", dataset_spec_id),
    )
    expected_provenance_rows = (
        ("Generator-source SHA-256", iid_benchmark.dataset.GENERATOR_SOURCE_SHA256),
        (
            "Generation-config SHA-256",
            iid_benchmark.dataset.PUBLIC_GENERATION_CONFIGURATION_SHA256,
        ),
        ("Realization ID", manifest["identity_id"]),
        ("Realization digest", manifest["realization_digest"]),
        ("Manifest digest", manifest["manifest_digest"]),
        ("Train SHA-256", artifacts["train"]),
        ("Validation SHA-256", artifacts["validation"]),
    )
    identity_section = card.split("## Benchmark identity", 1)[1].split("\n## ", 1)[0]
    provenance_section = card.split("## Canonical realization and regeneration", 1)[1].split(
        "\n## ", 1
    )[0]
    assert all(
        [line for line in identity_section.splitlines() if line.startswith(f"| {label} |")]
        == [f"| {label} | `{value}` |"]
        for label, value in expected_identity_rows
    )
    assert all(
        [line for line in provenance_section.splitlines() if line.startswith(f"| {label} |")]
        == [f"| {label} | `{value}` |"]
        for label, value in expected_provenance_rows
    )
