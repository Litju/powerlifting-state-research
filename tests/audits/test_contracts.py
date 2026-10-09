from dataclasses import fields, replace
from pathlib import Path

import pytest

from powerlifting_state_research.audits import (
    ATTACK_SPECS,
    BENCHMARK_VERSIONS,
    VALIDITY_AXES,
    VERSION_VALIDITY_PROFILES,
    AuditResult,
    AuditStatus,
)
from powerlifting_state_research.contracts.benchmark import BenchmarkIdentityAuthority
from powerlifting_state_research.registry import BENCHMARKS

ROOT = Path(__file__).resolve().parents[2]


def test_axis_contracts_cover_the_res277_dimensions_and_all_versions() -> None:
    expected = {
        "domain_faithfulness",
        "reproducibility",
        "leakage_shortcut_susceptibility",
        "reconstructability",
        "simple_model_frontier",
        "ml_load_bearing_contribution",
        "out_of_distribution_robustness",
        "seed_stability",
        "hidden_test_fairness",
        "audit_coverage",
    }
    assert {axis.slug for axis in VALIDITY_AXES} == expected
    assert len(BENCHMARK_VERSIONS) == len(BENCHMARKS) == 9
    for axis in VALIDITY_AXES:
        assert set(axis.applicable_benchmark_versions) == set(BENCHMARK_VERSIONS)
        assert axis.audit_spec.version == "1.0.0"
        assert axis.audit_spec.expected_output_schema == "PSR_AUDIT_RESULT_V1"
        assert axis.scientific_question and axis.intended_claim
        assert axis.audit_spec.methodology
        assert axis.audit_spec.inputs and axis.audit_spec.outputs
        assert axis.audit_spec.quantitative_diagnostics
        assert axis.audit_spec.required_evidence
        assert axis.audit_spec.admissibility_conditions
        assert axis.audit_spec.pass_criteria
        assert axis.audit_spec.fail_criteria
        assert axis.audit_spec.inconclusive_criteria
        assert axis.audit_spec.interpretation_boundaries
        assert axis.audit_spec.limitations
        assert axis.audit_spec.missing_evidence_handling
    attacks = {attack.reference: attack for attack in ATTACK_SPECS}
    referenced_attacks: set[str] = set()
    for axis in VALIDITY_AXES:
        referenced_attacks.update(axis.attack_spec_refs)
        assert all(attacks[ref].axis_slug == axis.slug for ref in axis.attack_spec_refs)
    assert referenced_attacks == set(attacks)


def test_attack_contracts_are_versioned_scoped_and_use_audit_result_schema() -> None:
    axes = {axis.slug for axis in VALIDITY_AXES}
    attacks = {attack.slug: attack for attack in ATTACK_SPECS}
    assert len(attacks) == 14
    assert len({attack.reference for attack in ATTACK_SPECS}) == len(ATTACK_SPECS)
    for attack in ATTACK_SPECS:
        assert attack.version == "1.0.0"
        assert attack.axis_slug in axes
        assert set(attack.applicable_benchmark_versions) <= set(BENCHMARK_VERSIONS)
        assert attack.world_task_semantics
        assert attack.permitted_interventions
        assert attack.estimand and attack.target_failure_mode
        assert attack.required_evidence and attack.admissibility_conditions
        assert attack.methodology and attack.inputs and attack.expected_outputs
        assert attack.quantitative_diagnostics
        assert attack.interpretation_boundaries and attack.limitations
        assert attack.expected_output_schema == "PSR_AUDIT_RESULT_V1"
        assert attack.study_kind == "VALIDITY_ATTACK"
        assert attack.missing_evidence_handling

    assert set(
        attacks["training_plan_counterfactual_sensitivity"].applicable_benchmark_versions
    ) == {
        "iid_latent_capacity_change_with_transient_expression_forecasting@1.0.0",
        "latent_capacity_change_with_transient_expression_forecasting@1.0.0",
        "latent_origin_capacity_change_forecasting@1.0.0",
        "observed_origin_referenced_capacity_change_forecasting@1.0.0",
    }
    assert attacks["distributional_shift_sensitivity"].applicable_benchmark_versions == (
        "iid_latent_capacity_change_with_transient_expression_forecasting@1.0.0",
    )
    assert attacks["baseline_domination"].applicable_benchmark_versions == (
        "iid_latent_capacity_change_with_transient_expression_forecasting@1.0.0",
    )


def test_profiles_preserve_benchmark_identities_and_report_evidence_states_only() -> None:
    profiles = {
        f"{item.benchmark_slug}@{item.benchmark_version}": item
        for item in VERSION_VALIDITY_PROFILES
    }
    assert set(profiles) == set(BENCHMARK_VERSIONS)
    for benchmark in BENCHMARKS:
        profile = profiles[f"{benchmark.slug}@{benchmark.version}"]
        assert profile.benchmark_id == benchmark.benchmark_id
        assert profile.semantic_digest == benchmark.semantic_digest
        assert {result.axis_slug for result in profile.axis_results} == {
            axis.slug for axis in VALIDITY_AXES
        }
        assert len(profile.attack_results) == len(ATTACK_SPECS)
        assert {result.attack_spec_refs[0] for result in profile.attack_results} == {
            attack.reference for attack in ATTACK_SPECS
        }
        axis_versions = {axis.slug: axis.version for axis in VALIDITY_AXES}
        attacks = {attack.reference: attack for attack in ATTACK_SPECS}
        assert all(
            result.benchmark_version == f"{benchmark.slug}@{benchmark.version}"
            for result in (*profile.axis_results, *profile.attack_results)
        )
        assert all(
            result.axis_spec_version == axis_versions[result.axis_slug]
            for result in (*profile.axis_results, *profile.attack_results)
        )
        assert all(
            attacks[attack_ref].axis_slug == result.axis_slug
            for result in profile.attack_results
            for attack_ref in result.attack_spec_refs
        )
        assert all(
            (result.benchmark_id, result.semantic_digest)
            == (profile.benchmark_id, profile.semantic_digest)
            for result in (*profile.axis_results, *profile.attack_results)
        )
        assert all(
            (ROOT / evidence_ref).is_file()
            for result in (*profile.axis_results, *profile.attack_results)
            for evidence_ref in result.evidence_refs
        )
        assert all(
            result.status
            in {
                AuditStatus.NOT_APPLICABLE,
                AuditStatus.NOT_RUN,
                AuditStatus.UNSUPPORTED_BY_EVIDENCE,
            }
            for result in (*profile.axis_results, *profile.attack_results)
        )
        assert all(
            not result.diagnostics for result in (*profile.axis_results, *profile.attack_results)
        )
        assert not any("score" in item.name for item in fields(profile))

        axes = {result.axis_slug: result for result in profile.axis_results}
        assert axes["audit_coverage"].status is AuditStatus.NOT_RUN
        for attack_result in profile.attack_results:
            attack = next(
                item for item in ATTACK_SPECS if item.reference == attack_result.attack_spec_refs[0]
            )
            if attack.slug in {"audit_coverage_accounting", "reconstruction_provenance_gaps"}:
                expected_status = AuditStatus.NOT_RUN
            elif (
                attack.slug == "hidden_test_fairness"
                and benchmark.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE
            ):
                expected_status = AuditStatus.NOT_APPLICABLE
            elif (
                f"{benchmark.slug}@{benchmark.version}" not in attack.applicable_benchmark_versions
            ):
                expected_status = AuditStatus.NOT_APPLICABLE
            elif benchmark.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE:
                expected_status = AuditStatus.NOT_RUN
            else:
                expected_status = AuditStatus.UNSUPPORTED_BY_EVIDENCE
            assert attack_result.status is expected_status

    native = next(
        item
        for item in BENCHMARKS
        if item.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE
    )
    profile = profiles[f"{native.slug}@{native.version}"]
    by_axis = {result.axis_slug: result for result in profile.axis_results}
    assert by_axis["hidden_test_fairness"].status is AuditStatus.NOT_APPLICABLE
    assert by_axis["simple_model_frontier"].status is AuditStatus.NOT_RUN
    assert (
        "results/tables/public-native-comparator-frontier.csv"
        in by_axis["simple_model_frontier"].evidence_refs
    )
    assert "not audit findings" in by_axis["simple_model_frontier"].status_reason
    attacks = {result.attack_spec_refs[0]: result for result in profile.attack_results}
    assert attacks["baseline_domination@1.0.0"].status is AuditStatus.NOT_RUN
    assert attacks["hidden_test_fairness@1.0.0"].status is AuditStatus.NOT_APPLICABLE

    historical = profiles["class_normalized_cross_lift_five_target_performance_forecasting@1.0.0"]
    historical_attacks = {
        result.attack_spec_refs[0]: result for result in historical.attack_results
    }
    assert historical_attacks["baseline_domination@1.0.0"].status is AuditStatus.NOT_APPLICABLE
    assert historical_attacks["reconstruction_provenance_gaps@1.0.0"].status is AuditStatus.NOT_RUN
    assert (
        historical_attacks["participant_input_leakage@1.0.0"].status
        is AuditStatus.UNSUPPORTED_BY_EVIDENCE
    )


def test_audit_result_states_require_the_right_evidence_and_provenance() -> None:
    base = AuditResult(
        benchmark_version="example@1.0.0",
        axis_slug="reproducibility",
        axis_spec_version="1.0.0",
        status=AuditStatus.NOT_RUN,
        status_reason="The protocol has not been executed.",
    )
    assert base.status is AuditStatus.NOT_RUN
    with pytest.raises(ValueError, match="cite evidence"):
        replace(
            base,
            status=AuditStatus.UNSUPPORTED_BY_EVIDENCE,
            status_reason="Inputs are absent.",
        )
    with pytest.raises(ValueError, match="semantic condition"):
        replace(
            base,
            status=AuditStatus.NOT_APPLICABLE,
            status_reason="No hidden-test claim exists.",
        )
    with pytest.raises(ValueError, match="non-execution states"):
        replace(base, diagnostics={"paired_rmse_delta": 0.1})
    with pytest.raises(ValueError, match="source commit"):
        replace(
            base,
            status=AuditStatus.PASS,
            status_reason="The criteria were met.",
            evidence_refs=("results/audits/example.json",),
            diagnostics={"identity_match": 1},
        )

    passed = replace(
        base,
        status=AuditStatus.PASS,
        status_reason="The predeclared criterion was met.",
        evidence_refs=("results/audits/example.json",),
        diagnostics={"identity_match": 1},
        run_id="example-run-001",
        source_commit="a" * 40,
    )
    assert passed.status is AuditStatus.PASS
    not_applicable = replace(
        base,
        status=AuditStatus.NOT_APPLICABLE,
        status_reason="The version has no hidden-test claim.",
        evidence_refs=("docs/benchmarks/example.md",),
    )
    unsupported = replace(
        base,
        status=AuditStatus.UNSUPPORTED_BY_EVIDENCE,
        status_reason="The applicable adapter is absent.",
        evidence_refs=("docs/benchmarks/example.md",),
        missing_evidence=("Rights-cleared row-level inputs.",),
    )
    assert not_applicable.status is AuditStatus.NOT_APPLICABLE
    assert unsupported.status is AuditStatus.UNSUPPORTED_BY_EVIDENCE
    failed = replace(
        passed,
        status=AuditStatus.FAIL,
        status_reason="The predeclared criterion was contradicted.",
    )
    assert failed.status is AuditStatus.FAIL
    inconclusive = replace(
        base,
        status=AuditStatus.INCONCLUSIVE,
        status_reason="Uncertainty spans the predeclared margin.",
        evidence_refs=("results/audits/example.json",),
        run_id="example-run-002",
        source_commit="b" * 40,
    )
    assert inconclusive.status is AuditStatus.INCONCLUSIVE


def test_generated_audit_schemas_and_registries_are_exported() -> None:
    from powerlifting_state_research.exports import check_exports, generated_files

    paths = {path.as_posix() for path in generated_files()}
    assert {
        "registries/validity-axis-registry.json",
        "registries/attack-contract-registry.json",
        "registries/version-validity-profiles.json",
        "schemas/audit-spec.schema.json",
        "schemas/validity-axis.schema.json",
        "schemas/attack-spec.schema.json",
        "schemas/audit-result.schema.json",
        "schemas/version-validity-profile.schema.json",
    } <= paths
    assert check_exports() == ()
