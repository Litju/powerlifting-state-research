"""Evidence-state profiles for the public benchmark versions in the registry."""

from __future__ import annotations

from ..contracts.benchmark import BenchmarkIdentityAuthority, BenchmarkSpec
from ..registry import BENCHMARKS
from .specifications import (
    ATTACK_SPECS,
    CONTRACT_VERSION,
    PUBLIC_NATIVE_VERSION,
    VALIDITY_AXES,
    AuditResult,
    AuditStatus,
    VersionValidityProfile,
)

_PUBLIC_NATIVE_EVIDENCE: dict[str, tuple[str, ...]] = {
    "domain_faithfulness": (
        "docs/science/system-model.md",
        "docs/benchmarks/iid-latent-capacity-change-with-transient-expression-forecasting.md",
    ),
    "reproducibility": (
        "data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json",
        "scripts/verify_public_iid_production.py",
        "results/manifests/public-native-comparator-suite-checksums.json",
    ),
    "leakage_shortcut_susceptibility": (
        "docs/benchmarks/iid-latent-capacity-change-public-native-evaluation.md",
        "artifacts/schemas/prediction-contract.schema.json",
        "results/manifests/public-native-comparator-suite.json",
    ),
    "reconstructability": (
        "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/research.py",
        "docs/benchmarks/iid-latent-capacity-change-with-transient-expression-forecasting.md",
    ),
    "simple_model_frontier": (
        "artifacts/model-cards/public-native-comparator-suite.md",
        "artifacts/registries/public-native-comparator-registry.json",
        "results/tables/public-native-comparator-frontier.csv",
    ),
    "ml_load_bearing_contribution": (
        "artifacts/model-cards/public-native-comparator-suite.md",
        "artifacts/registries/public-native-comparator-registry.json",
        "results/tables/public-native-comparator-frontier.csv",
    ),
    "out_of_distribution_robustness": (
        "docs/benchmarks/iid-latent-capacity-change-with-transient-expression-forecasting.md",
        "docs/benchmarks/claim-boundaries.md",
    ),
    "seed_stability": (
        "artifacts/registries/public-native-comparator-registry.json",
        "results/manifests/public-native-comparator-suite.json",
        "results/tables/public-native-comparator-frontier.csv",
    ),
    "hidden_test_fairness": (
        "docs/benchmarks/iid-latent-capacity-change-public-native-evaluation.md",
        "data/manifests/realizations/latent_capacity_change_with_transient_expression_forecasting/iid-production.json",
    ),
    "audit_coverage": (
        "artifacts/registries/validity-axis-registry.json",
        "artifacts/registries/attack-contract-registry.json",
    ),
}
_HISTORICAL_MISSING = (
    "Public row-level realization, executable audit adapter, and matching model/evaluation artifacts are not available for this historical version.",
)
_NATIVE_NOT_RUN = "RES-277 defines this diagnostic but does not execute it; linked public artifacts are inputs, not audit findings."
_COVERAGE_NOT_RUN = "RES-277 defines the applicable denominator and status ledger; RES-278 has not executed the coverage audit."


def _profile_for(benchmark: BenchmarkSpec) -> VersionValidityProfile:
    slug = benchmark.slug
    version = benchmark.version
    benchmark_version = f"{slug}@{version}"
    is_native = benchmark.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE
    is_public_native_ref = benchmark_version == PUBLIC_NATIVE_VERSION
    axis_results: list[AuditResult] = []
    refs: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    for axis in VALIDITY_AXES:
        refs = ()
        missing = ()
        if axis.slug == "audit_coverage":
            status = AuditStatus.NOT_RUN
            reason = _COVERAGE_NOT_RUN
            refs = (
                "artifacts/registries/validity-axis-registry.json",
                "artifacts/registries/attack-contract-registry.json",
            )
            missing = ()
        elif axis.slug == "hidden_test_fairness" and is_public_native_ref:
            status = AuditStatus.NOT_APPLICABLE
            reason = "This public-native version publishes its evaluation split and makes no hidden-test claim."
            refs = _PUBLIC_NATIVE_EVIDENCE[axis.slug]
            missing = ()
        elif is_native:
            status = AuditStatus.NOT_RUN
            reason = _NATIVE_NOT_RUN
            refs = _PUBLIC_NATIVE_EVIDENCE[axis.slug]
            missing = ()
        else:
            status = AuditStatus.UNSUPPORTED_BY_EVIDENCE
            reason = "The public historical record does not contain the executable evidence needed to run this diagnostic."
            refs = (
                f"docs/benchmarks/{slug.replace('_', '-')}.md",
                "artifacts/registries/benchmark-registry.json",
                "src/powerlifting_state_research/provenance/historical_sources.py",
            )
            missing = (
                "Public row-level realization, executable audit adapter, and matching model/evaluation artifacts are not available for this historical version.",
            )
            if axis.slug == "hidden_test_fairness":
                missing = (
                    "Public evidence does not establish whether a hidden/access-controlled test exists or document its split identity and access controls.",
                )

        axis_results.append(
            AuditResult(
                benchmark_version=benchmark_version,
                axis_slug=axis.slug,
                axis_spec_version=axis.version,
                status=status,
                status_reason=reason,
                benchmark_id=benchmark.benchmark_id,
                semantic_digest=benchmark.semantic_digest,
                evidence_refs=refs,
                missing_evidence=missing,
            )
        )

    attack_results: list[AuditResult] = []
    for attack in ATTACK_SPECS:
        refs = ()
        missing = ()
        applies = benchmark_version in attack.applicable_benchmark_versions
        if attack.slug == "audit_coverage_accounting":
            status = AuditStatus.NOT_RUN
            reason = _COVERAGE_NOT_RUN
            refs = (
                "artifacts/registries/validity-axis-registry.json",
                "artifacts/registries/attack-contract-registry.json",
            )
            missing = ()
        elif attack.slug == "reconstruction_provenance_gaps":
            status = AuditStatus.NOT_RUN
            reason = "The public provenance records can be checked, but RES-277 did not execute this diagnostic."
            refs = (
                _PUBLIC_NATIVE_EVIDENCE[attack.axis_slug]
                if is_native
                else (
                    f"docs/benchmarks/{slug.replace('_', '-')}.md",
                    "artifacts/registries/benchmark-registry.json",
                    "src/powerlifting_state_research/provenance/historical_sources.py",
                )
            )
            missing = ()
        elif attack.slug == "hidden_test_fairness" and is_public_native_ref:
            status = AuditStatus.NOT_APPLICABLE
            reason = (
                "The public-native version has no hidden-test claim or access-controlled split."
            )
            refs = _PUBLIC_NATIVE_EVIDENCE[attack.axis_slug]
            missing = ()
        elif not applies:
            status = AuditStatus.NOT_APPLICABLE
            reason = (
                "This version is outside the attack contract's declared semantic applicability."
            )
            refs = (
                f"docs/benchmarks/{slug.replace('_', '-')}.md",
                "artifacts/registries/attack-contract-registry.json",
            )
            missing = ()
        elif is_native:
            status = AuditStatus.NOT_RUN
            reason = _NATIVE_NOT_RUN
            refs = _PUBLIC_NATIVE_EVIDENCE[attack.axis_slug]
            missing = ()
        else:
            status = AuditStatus.UNSUPPORTED_BY_EVIDENCE
            reason = "The public historical record does not contain the executable evidence needed to run this attack."
            refs = (
                f"docs/benchmarks/{slug.replace('_', '-')}.md",
                "artifacts/registries/benchmark-registry.json",
                "src/powerlifting_state_research/provenance/historical_sources.py",
            )
            missing = _HISTORICAL_MISSING
            if attack.slug == "hidden_test_fairness":
                missing = (
                    "Public evidence does not establish whether a hidden/access-controlled test exists or document its split identity and access controls.",
                )
        attack_results.append(
            AuditResult(
                benchmark_version=benchmark_version,
                axis_slug=attack.axis_slug,
                axis_spec_version=next(
                    axis.version for axis in VALIDITY_AXES if axis.slug == attack.axis_slug
                ),
                status=status,
                status_reason=reason,
                benchmark_id=benchmark.benchmark_id,
                semantic_digest=benchmark.semantic_digest,
                attack_spec_refs=(attack.reference,),
                evidence_refs=refs,
                missing_evidence=missing,
            )
        )

    return VersionValidityProfile(
        profile_version=CONTRACT_VERSION,
        benchmark_slug=slug,
        benchmark_version=version,
        benchmark_id=benchmark.benchmark_id,
        semantic_digest=benchmark.semantic_digest,
        axis_results=tuple(axis_results),
        attack_results=tuple(attack_results),
    )


VERSION_VALIDITY_PROFILES: tuple[VersionValidityProfile, ...] = tuple(
    _profile_for(benchmark) for benchmark in BENCHMARKS
)
