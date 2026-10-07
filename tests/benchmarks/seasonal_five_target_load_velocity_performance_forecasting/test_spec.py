from powerlifting_state_research.contracts.benchmark import (
    CompletenessStatus,
    HistoricalSpecimenStatus,
    ImplementationStatus,
)
from powerlifting_state_research.registry import BENCHMARK_REGISTRY


def test_declaration_matches_frozen_record() -> None:
    spec = BENCHMARK_REGISTRY["seasonal_five_target_load_velocity_performance_forecasting"]
    assert spec.slug == "seasonal_five_target_load_velocity_performance_forecasting"
    assert spec.python_namespace.endswith(
        "seasonal_five_target_load_velocity_performance_forecasting"
    )
    assert spec.docs_path.endswith("seasonal-five-target-load-velocity-performance-forecasting.md")
    assert spec.public_implementation_status is ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING
    assert spec.historical_specimen_status is HistoricalSpecimenStatus.PARTIALLY_RECONSTRUCTED
    assert spec.completeness_status is CompletenessStatus.PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS
    assert spec.component_references
