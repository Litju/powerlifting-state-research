"""The frozen minimum predicates for direct and property-only comparison."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .serialization import require_scientific_id


class EstimandKind(StrEnum):
    OBSERVED_ORIGIN_REFERENCED_CAPACITY_CHANGE = "OBSERVED_ORIGIN_REFERENCED_CAPACITY_CHANGE"
    LATENT_CAPACITY_CHANGE = "LATENT_CAPACITY_CHANGE"
    OTHER = "OTHER"


class SupportAlignment(StrEnum):
    MATCHED = "MATCHED"
    STRATIFIED_MATCHED = "STRATIFIED_MATCHED"
    UNMATCHED = "UNMATCHED"
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass(frozen=True, slots=True)
class ComparisonProfile:
    world_id: str
    qoi_ids: tuple[str, ...]
    output_fields: tuple[tuple[str, str], ...]
    metric_ids: tuple[str, ...]
    evaluation_id: str
    estimand: EstimandKind
    support_match_required: bool = False

    def __post_init__(self) -> None:
        require_scientific_id(self.world_id, "world ID", expected_class="world")
        require_scientific_id(self.evaluation_id, "evaluation ID", expected_class="evaluation")
        for qoi_id in self.qoi_ids:
            require_scientific_id(qoi_id, "QOI ID", expected_class="qoi")
        for metric_id in self.metric_ids:
            require_scientific_id(metric_id, "metric ID", expected_class="metric")


@dataclass(frozen=True, slots=True)
class ComparabilityDecision:
    qoi_compatible: bool
    output_compatible: bool
    metric_evaluation_compatible: bool
    support_match_required: bool
    direct_performance_comparable: bool
    property_only_comparable: bool
    rationale: str


def assess_comparability(
    left: ComparisonProfile,
    right: ComparisonProfile,
    *,
    common_evaluation_id: str | None = None,
    support_alignment: SupportAlignment = SupportAlignment.NOT_ASSESSED,
) -> ComparabilityDecision:
    if common_evaluation_id is not None:
        require_scientific_id(
            common_evaluation_id, "common evaluation ID", expected_class="evaluation"
        )
    qoi_ok = set(left.qoi_ids) == set(right.qoi_ids)
    output_ok = set(left.output_fields) == set(right.output_fields)
    metrics_ok = set(left.metric_ids) == set(right.metric_ids)
    eval_ok = left.evaluation_id == right.evaluation_id or common_evaluation_id is not None
    metric_evaluation_ok = metrics_ok and eval_ok
    latent_pair = (
        left.estimand is EstimandKind.LATENT_CAPACITY_CHANGE
        and right.estimand is EstimandKind.LATENT_CAPACITY_CHANGE
    )
    support_required = (
        left.support_match_required
        or right.support_match_required
        or (latent_pair and left.world_id != right.world_id)
    )
    support_ok = not support_required or support_alignment in {
        SupportAlignment.MATCHED,
        SupportAlignment.STRATIFIED_MATCHED,
    }
    origin_mismatch = {
        left.estimand,
        right.estimand,
    } == {
        EstimandKind.OBSERVED_ORIGIN_REFERENCED_CAPACITY_CHANGE,
        EstimandKind.LATENT_CAPACITY_CHANGE,
    }
    direct = qoi_ok and output_ok and metric_evaluation_ok and support_ok and not origin_mismatch
    property_only = qoi_ok and output_ok and not direct
    if origin_mismatch:
        rationale = "observed-origin and latent-origin estimands are not directly rankable"
    elif support_required and not support_ok:
        rationale = "direct comparison requires matched or stratified-matched support"
    elif not metric_evaluation_ok:
        rationale = "direct comparison requires compatible metrics and a common evaluation"
    elif not qoi_ok or not output_ok:
        rationale = "QOI or output definitions differ"
    else:
        rationale = "QOI, outputs, metrics, evaluation, and required support align"
    return ComparabilityDecision(
        qoi_compatible=qoi_ok,
        output_compatible=output_ok,
        metric_evaluation_compatible=metric_evaluation_ok,
        support_match_required=support_required,
        direct_performance_comparable=direct,
        property_only_comparable=property_only,
        rationale=rationale,
    )
