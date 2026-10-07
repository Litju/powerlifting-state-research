from powerlifting_state_research.registry import BENCHMARK_REGISTRY


def test_shared_dose_history_world_keeps_distinct_origin_estimands() -> None:
    observed = BENCHMARK_REGISTRY["observed_origin_referenced_capacity_change_forecasting"]
    latent = BENCHMARK_REGISTRY["latent_origin_capacity_change_forecasting"]
    transient_expression = BENCHMARK_REGISTRY[
        "latent_capacity_change_with_transient_expression_forecasting"
    ]

    def reference(spec, kind):
        return next(
            item for item in spec.component_references if item.component_class.value == kind
        )

    assert reference(observed, "WORLD") is reference(latent, "WORLD")
    assert reference(observed, "TASK").canonical_key != reference(latent, "TASK").canonical_key
    assert reference(observed, "QOI").canonical_key != reference(latent, "QOI").canonical_key
    assert (
        reference(latent, "QOI").canonical_key
        == reference(transient_expression, "QOI").canonical_key
    )
    assert (
        reference(latent, "WORLD").canonical_key
        != reference(transient_expression, "WORLD").canonical_key
    )
    worlds = {reference(spec, "WORLD").canonical_key for spec in BENCHMARK_REGISTRY.values()}
    assert len(worlds) == 6
