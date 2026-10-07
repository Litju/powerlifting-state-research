from powerlifting_state_research.contracts.benchmark import (
    CompletenessStatus,
    HistoricalSpecimenStatus,
    ImplementationStatus,
)
from powerlifting_state_research.registry import BENCHMARK_REGISTRY


def test_declaration_matches_frozen_record() -> None:
    spec = BENCHMARK_REGISTRY["latent_capacity_change_with_transient_expression_forecasting"]
    assert spec.slug == "latent_capacity_change_with_transient_expression_forecasting"
    assert spec.python_namespace.endswith(
        "latent_capacity_change_with_transient_expression_forecasting"
    )
    assert spec.docs_path.endswith(
        "latent-capacity-change-with-transient-expression-forecasting.md"
    )
    assert spec.public_implementation_status is ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING
    assert spec.historical_specimen_status is HistoricalSpecimenStatus.REPRODUCIBLE_SPEC
    assert spec.completeness_status is CompletenessStatus.FULL_FROM_EXISTING_EVIDENCE
    assert spec.component_references
