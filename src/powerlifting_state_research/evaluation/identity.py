"""Public-native metric and evaluation identities for the IID benchmark."""

from __future__ import annotations

from ..contracts.serialization import sha256_record
from .metrics import MetricName
from .protocols import MetricEvidenceStatus, MetricIdentity

TASK_ID = "psr:task:latent-capacity-change@1.0.0~44fc77353e7a"
QOI_ID = "psr:qoi:latent-capacity-change@1.0.0~675491124046"
DATASET_SPEC_ID = (
    "psr:dataset-spec:latent-capacity-transient-iid-sampling-design@1.0.0~1d079eb645ed"
)
TARGETS = (
    "squat_delta_capacity_kg",
    "bench_press_delta_capacity_kg",
    "deadlift_delta_capacity_kg",
)


def _public_native_id(component_class: str, slug: str, semantics: dict[str, object]) -> str:
    digest = sha256_record(
        {
            "format": "PSR_PUBLIC_NATIVE_COMPONENT_ID_V1",
            "component_class": component_class,
            "slug": slug,
            "version": "1.0.0",
            "semantics": semantics,
        },
        reject_floats=True,
    )
    return f"psr:{component_class}:{slug}@1.0.0~{digest[7:19]}"


_METRIC_DEFINITIONS: tuple[tuple[MetricName, str, str, dict[str, object]], ...] = (
    (
        MetricName.RMSE,
        "rmse",
        "sqrt(mean((prediction - truth)^2)); target unit (kg).",
        {"formula": "sqrt(mean((prediction - truth)^2))", "unit": "kg"},
    ),
    (
        MetricName.MAE,
        "mae",
        "mean(abs(prediction - truth)); target unit (kg).",
        {"formula": "mean(abs(prediction - truth))", "unit": "kg"},
    ),
    (
        MetricName.R2,
        "r-squared",
        "1 - SSE/SST; dimensionless; undefined for constant truth.",
        {"formula": "1 - SSE/SST", "unit": "1", "constant_truth": "UNDEFINED"},
    ),
    (
        MetricName.SRE,
        "sre-population-sd-ddof-0",
        "RMSE / sqrt(mean((truth - mean(truth))^2)); population SD (ddof=0); dimensionless.",
        {
            "formula": "RMSE / sqrt(mean((truth - mean(truth))^2))",
            "unit": "1",
            "standard_deviation_ddof": 0,
            "zero_truth_population_sd": "UNDEFINED",
        },
    ),
)

METRIC_IDENTITIES = tuple(
    MetricIdentity(
        _public_native_id("metric", slug, semantics),
        metric,
        definition,
        MetricEvidenceStatus.CANONICAL_RESEARCH,
    )
    for metric, slug, definition, semantics in _METRIC_DEFINITIONS
)
METRIC_SEMANTICS = {
    item.metric_id: semantics
    for item, (_, _, _, semantics) in zip(METRIC_IDENTITIES, _METRIC_DEFINITIONS, strict=True)
}

EVALUATION_SEMANTICS: dict[str, object] = {
    "task_id": TASK_ID,
    "qoi_ids": (QOI_ID,),
    "validation": {
        "dataset_spec_id": DATASET_SPEC_ID,
        "split_id": "validation",
        "purpose": "same-law held-out validation",
        "row_count": 3072,
        "coverage": "complete split; no row drops or imputation",
    },
    "metric_ids": tuple(item.metric_id for item in METRIC_IDENTITIES),
    "targets": TARGETS,
    "reporting": "target-wise",
    "alignment": {"policy": "ALIGN_BY_DECLARED_KEYS", "keys": ("row_id",)},
    "missing_prediction": "REJECT",
    "non_finite_prediction": "REJECT",
    "aggregation": "none; no universal scalar aggregate",
    "stratification": "none; optional diagnostics are non-canonical",
    "uncertainty": "none",
}

EVALUATION_ID = _public_native_id(
    "evaluation",
    "iid-latent-capacity-change-four-metric-validation",
    EVALUATION_SEMANTICS,
)
