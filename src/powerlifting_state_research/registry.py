"""Explicit, deterministic registry of the eight scientific benchmark records."""

from __future__ import annotations

from .benchmarks.class_normalized_cross_lift_five_target_performance_forecasting import (
    SPEC as CLASS_NORMALIZED_CROSS_LIFT_FIVE_TARGET,
)
from .benchmarks.four_target_load_velocity_and_competition_performance_forecasting import (
    SPEC as FOUR_TARGET_LOAD_VELOCITY_AND_COMPETITION_PERFORMANCE,
)
from .benchmarks.held_out_final_origin_five_target_performance_evaluation import (
    SPEC as HELD_OUT_FINAL_ORIGIN_FIVE_TARGET,
)
from .benchmarks.latent_capacity_change_with_transient_expression_forecasting import (
    SPEC as LATENT_CAPACITY_CHANGE_WITH_TRANSIENT_EXPRESSION,
)
from .benchmarks.latent_origin_capacity_change_forecasting import (
    SPEC as LATENT_ORIGIN_CAPACITY_CHANGE,
)
from .benchmarks.observed_origin_referenced_capacity_change_forecasting import (
    SPEC as OBSERVED_ORIGIN_REFERENCED_CAPACITY_CHANGE,
)
from .benchmarks.performance_forecasting_under_schedule_exposure_reporting_heterogeneity import (
    SPEC as PERFORMANCE_FORECASTING_UNDER_SCHEDULE_EXPOSURE_REPORTING_HETEROGENEITY,
)
from .benchmarks.seasonal_five_target_load_velocity_performance_forecasting import (
    SPEC as SEASONAL_FIVE_TARGET_LOAD_VELOCITY_PERFORMANCE,
)
from .contracts.benchmark import BenchmarkSpec, CompletenessStatus, ImplementationStatus
from .contracts.components import ComponentClass
from .provenance import HISTORICAL_SOURCES

# Registry enumeration is lexicographic by canonical scientific slug.
BENCHMARKS: tuple[BenchmarkSpec, ...] = tuple(
    sorted(
        (
            CLASS_NORMALIZED_CROSS_LIFT_FIVE_TARGET,
            FOUR_TARGET_LOAD_VELOCITY_AND_COMPETITION_PERFORMANCE,
            HELD_OUT_FINAL_ORIGIN_FIVE_TARGET,
            LATENT_CAPACITY_CHANGE_WITH_TRANSIENT_EXPRESSION,
            LATENT_ORIGIN_CAPACITY_CHANGE,
            OBSERVED_ORIGIN_REFERENCED_CAPACITY_CHANGE,
            SEASONAL_FIVE_TARGET_LOAD_VELOCITY_PERFORMANCE,
            PERFORMANCE_FORECASTING_UNDER_SCHEDULE_EXPOSURE_REPORTING_HETEROGENEITY,
        ),
        key=lambda item: item.slug,
    )
)
BENCHMARK_REGISTRY: dict[str, BenchmarkSpec] = {item.slug: item for item in BENCHMARKS}


def resolve_benchmark(identifier: str) -> BenchmarkSpec:
    """Resolve only canonical slugs or currently minted scientific IDs."""
    if identifier in BENCHMARK_REGISTRY:
        return BENCHMARK_REGISTRY[identifier]
    for benchmark in BENCHMARKS:
        if benchmark.benchmark_id == identifier:
            return benchmark
    raise KeyError(identifier)


def resolve_historical_alias(alias: str) -> tuple[BenchmarkSpec, ...]:
    """Resolve provenance aliases separately from canonical names and IDs."""
    matches = tuple(
        benchmark
        for benchmark in BENCHMARKS
        if alias in HISTORICAL_SOURCES[benchmark.slug].historical_aliases
    )
    if not matches:
        raise KeyError(alias)
    return matches


def query_benchmarks(
    *,
    implementation_status: ImplementationStatus | None = None,
    completeness_status: CompletenessStatus | None = None,
    component_class: ComponentClass | None = None,
    component_key: str | None = None,
) -> tuple[BenchmarkSpec, ...]:
    """Filter the static registry without services or mutable global state."""
    return tuple(
        benchmark
        for benchmark in BENCHMARKS
        if (
            implementation_status is None
            or benchmark.public_implementation_status is implementation_status
        )
        and (completeness_status is None or benchmark.completeness_status is completeness_status)
        and (
            component_class is None
            or any(
                reference.component_class is component_class
                and (component_key is None or reference.canonical_key == component_key)
                for reference in benchmark.component_references
            )
        )
    )
