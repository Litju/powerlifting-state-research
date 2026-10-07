from powerlifting_state_research.contracts.benchmark import ImplementationStatus
from powerlifting_state_research.provenance import HISTORICAL_SOURCES
from powerlifting_state_research.registry import BENCHMARK_REGISTRY, BENCHMARKS


def test_historical_and_public_native_benchmark_records_import_and_enumerate() -> None:
    assert len(BENCHMARKS) == 9
    assert set(BENCHMARK_REGISTRY) == {item.slug for item in BENCHMARKS}
    historical = [item for item in BENCHMARKS if item.slug in HISTORICAL_SOURCES]
    assert set(HISTORICAL_SOURCES) == {item.slug for item in historical}
    assert len({item.python_namespace for item in historical}) == 8
    assert all(item.python_namespace.endswith(item.slug) for item in historical)
    implemented = [
        item.slug
        for item in BENCHMARKS
        if item.public_implementation_status is ImplementationStatus.PUBLIC_IMPLEMENTED
    ]
    assert implemented == ["iid_latent_capacity_change_with_transient_expression_forecasting"]
    assert (
        sum(
            item.public_implementation_status is ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING
            for item in BENCHMARKS
        )
        == 8
    )
    assert all(
        HISTORICAL_SOURCES[item.slug].specimen_id
        in HISTORICAL_SOURCES[item.slug].historical_aliases
        for item in historical
    )
