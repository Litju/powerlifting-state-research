from powerlifting_state_research.contracts.benchmark import (
    CompletenessStatus,
    HistoricalSpecimenStatus,
    ImplementationStatus,
)
from powerlifting_state_research.registry import BENCHMARK_REGISTRY


def test_declaration_matches_frozen_record() -> None:
    spec = BENCHMARK_REGISTRY["schedule_exposure_heterogeneity_forecasting"]
    assert spec.slug == "schedule_exposure_heterogeneity_forecasting"
    assert spec.python_namespace.endswith("schedule_exposure_heterogeneity_forecasting")
    assert spec.docs_path.endswith("schedule-exposure-heterogeneity-forecasting.md")
    assert spec.public_implementation_status is ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING
    assert spec.historical_specimen_status is HistoricalSpecimenStatus.PARTIALLY_RECONSTRUCTED
    assert spec.completeness_status is CompletenessStatus.PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS
    assert spec.component_references
