from powerlifting_state_research.contracts.benchmark import (
    CompletenessStatus,
    HistoricalSpecimenStatus,
    ImplementationStatus,
)
from powerlifting_state_research.registry import BENCHMARK_REGISTRY


def test_declaration_matches_frozen_record() -> None:
    spec = BENCHMARK_REGISTRY[
        "performance_forecasting_under_schedule_exposure_reporting_heterogeneity"
    ]
    assert spec.slug == "performance_forecasting_under_schedule_exposure_reporting_heterogeneity"
    assert spec.python_namespace.endswith(
        "performance_forecasting_under_schedule_exposure_reporting_heterogeneity"
    )
    assert spec.docs_path.endswith(
        "performance-forecasting-under-schedule-exposure-reporting-heterogeneity.md"
    )
    assert spec.public_implementation_status is ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING
    assert spec.historical_specimen_status is HistoricalSpecimenStatus.PARTIALLY_RECONSTRUCTED
    assert spec.completeness_status is CompletenessStatus.PARTIAL_WITH_EXPLICIT_UNRESOLVED_FIELDS
    assert spec.component_references
