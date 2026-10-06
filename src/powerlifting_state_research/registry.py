"""Explicit, deterministic registry of the eight scientific benchmark records."""

from __future__ import annotations

from .benchmarks.class_normalized_cross_lift_capacity_fatigue_forecasting import SPEC as benchmark_1
from .benchmarks.final_origin_target_domain_evaluation import SPEC as benchmark_2
from .benchmarks.latent_origin_capacity_change_forecasting import SPEC as benchmark_6
from .benchmarks.observed_origin_performance_change_forecasting import SPEC as benchmark_5
from .benchmarks.parsimonious_latent_capacity_change_forecasting import SPEC as benchmark_7
from .benchmarks.schedule_exposure_heterogeneity_forecasting import SPEC as benchmark_4
from .benchmarks.seasonal_capacity_fatigue_five_target_forecasting import SPEC as benchmark_0
from .benchmarks.stable_slope_tilt_four_target_forecasting import SPEC as benchmark_3
from .contracts.benchmark import BenchmarkSpec

BENCHMARKS: tuple[BenchmarkSpec, ...] = (
    benchmark_0,
    benchmark_1,
    benchmark_2,
    benchmark_3,
    benchmark_4,
    benchmark_5,
    benchmark_6,
    benchmark_7,
)
BENCHMARK_REGISTRY: dict[str, BenchmarkSpec] = {item.slug: item for item in BENCHMARKS}
