from powerlifting_state_research.contracts.benchmark import ImplementationStatus
from powerlifting_state_research.provenance import HISTORICAL_SOURCES
from powerlifting_state_research.registry import BENCHMARK_REGISTRY, BENCHMARKS


def test_eight_scientific_benchmark_records_import_and_enumerate() -> None:
    assert len(BENCHMARKS) == 8
    assert set(BENCHMARK_REGISTRY) == {item.slug for item in BENCHMARKS}
    assert set(HISTORICAL_SOURCES) == set(BENCHMARK_REGISTRY)
    assert len({item.python_namespace for item in BENCHMARKS}) == 8
    assert all(item.python_namespace.endswith(item.slug) for item in BENCHMARKS)
    assert all(item.docs_path.endswith(item.slug.replace("_", "-") + ".md") for item in BENCHMARKS)
    assert all(
        item.public_implementation_status is ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING
        for item in BENCHMARKS
    )
    assert all(
        HISTORICAL_SOURCES[item.slug].specimen_id
        in HISTORICAL_SOURCES[item.slug].historical_aliases
        for item in BENCHMARKS
    )
