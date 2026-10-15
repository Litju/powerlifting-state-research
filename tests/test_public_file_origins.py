import base64
import copy
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_repository_integrity import (  # noqa: E402
    RES297_BASELINE,
    RES297_PREDICTION_RIGHTS,
    RES297_RECORD,
    baseline_paths_from_ledger_prefix,
    derive_res297_release_gate,
    is_verified_owner_commit,
    validate_res297_rights_record,
    verify_owner_grant_commit,
)


def _res297_inputs() -> tuple[dict, dict, set[str], dict[str, dict[str, str]]]:
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / RES297_RECORD).read_text(encoding="utf-8"))
    prediction_rights = json.loads((root / RES297_PREDICTION_RIGHTS).read_text(encoding="utf-8"))
    with (root / "provenance/PUBLIC_FILE_ORIGINS.csv").open(newline="", encoding="utf-8") as handle:
        rows = {row["path"]: row for row in csv.DictReader(handle)}
    baseline_paths = {
        item.decode("utf-8")
        for item in subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", RES297_BASELINE], cwd=root
        ).split(b"\0")
        if item
    }
    return record, prediction_rights, baseline_paths, rows


def _validate(
    record: dict,
    prediction_rights: dict,
    expected_paths: set[str],
    origins: dict,
    verified_owner_commits: set[str] | None = None,
) -> list[str]:
    return validate_res297_rights_record(
        record,
        expected_paths,
        origins,
        prediction_rights,
        verified_owner_commits=verified_owner_commits,
    )


def _owner_grant(path: str, digest: str, index: int, license_expression: str = "CC-BY-4.0") -> dict:
    source_path = f"provenance/rights-grants/test-owner-decision-{index}.json"
    source_sha = f"{index + 1:064x}"
    return {
        "authority_type": "OWNER_ATTESTATION",
        "owner_identity": "Powerlifting State Research contributors",
        "evidence": [{"path": source_path, "sha256": source_sha, "role": "owner_grant"}],
        "artifact_path": path,
        "artifact_sha256": digest,
        "license_expression": license_expression,
        "authorization_scope": (
            "Redistribute these exact prediction bytes in the public repository, its source "
            "archives, and release bundles."
        ),
        "valid_from": "2026-10-15",
        "valid_until": None,
        "redistribution_conditions": (
            "Include the copyright and permission notice."
            if license_expression == "MIT"
            else "Give attribution and link the CC BY 4.0 license."
        ),
        "owner_attestation": {
            "decision_id": f"test-owner-decision-{index}",
            "rightsholder_identity": "Powerlifting State Research contributors",
            "authorized_signer_login": "Litju",
            "authority_basis": "Authorized representative of the named rightsholder.",
            "decision_date": "2026-10-15",
            "verified_commit": f"{index + 1:040x}",
        },
    }


def _verified_owner_commits(record: dict, prediction_rights: dict) -> set[str]:
    items = [
        *record["hash_decisions"],
        *record["candidate_inventory"]["new_candidate_files"],
        *record["checkpoint_dispositions"],
        *prediction_rights["artifacts"],
    ]
    return {
        item["rights_authorization"]["owner_attestation"]["verified_commit"]
        for item in items
        if isinstance(item.get("rights_authorization"), dict)
        and isinstance(item["rights_authorization"].get("owner_attestation"), dict)
    }


def _clear_all_predictions(record: dict, prediction_rights: dict) -> None:
    prediction_family = next(
        item
        for item in record["rights_families"]
        if item["family_id"] == "temporal_expert_prediction_bytes"
    )
    prediction_family["rights_disposition"] = "CLEARED"
    prediction_family["rights_owner"] = "Powerlifting State Research contributors"
    for index, resolution in enumerate(prediction_rights["artifacts"]):
        path = resolution["path"]
        digest = resolution["sha256"]
        grant = _owner_grant(path, digest, index)
        evidence = grant["evidence"][0]
        record["rights_source_hashes"].append(
            {"path": evidence["path"], "sha256": evidence["sha256"]}
        )
        decision = next(item for item in record["hash_decisions"] if item["path"] == path)
        public_record = next(
            item for item in record["prediction_artifacts"] if item["path"] == path
        )
        for item in (decision, resolution):
            item["rights_disposition"] = "CLEARED"
            item["release_inclusion"] = True
            item["rights_license_expression"] = "CC-BY-4.0"
            item["rights_authorization"] = copy.deepcopy(grant)
        public_record["rights_disposition"] = "CLEARED"
        public_record["release_inclusion"] = True
        public_record["rights_license_expression"] = "CC-BY-4.0"
        resolution.pop("owner_decision_required", None)
    prediction_rights["rights_status"] = "CLEARED"
    record["summary"] = {
        disposition: sum(
            item["rights_disposition"] == disposition for item in record["hash_decisions"]
        )
        for disposition in ("CLEARED", "EXCLUDED", "BLOCKED", "UNRESOLVED")
    }
    additions = record["candidate_inventory"]["new_candidate_files"]
    record["candidate_release_gate"] = derive_res297_release_gate(
        record["hash_decisions"],
        prediction_rights,
        additions,
        record["record_rights"],
        record["checkpoint_dispositions"],
    )
    record["release_inclusion_policy"]["candidate_release_gate"] = record["candidate_release_gate"]


def _clear_all_checkpoints(record: dict) -> None:
    family = next(
        item
        for item in record["rights_families"]
        if item["family_id"] == "temporal_expert_checkpoint_weights"
    )
    family["rights_owner"] = "Powerlifting State Research contributors"
    family["rights_disposition"] = "CLEARED"
    family["license_expression"] = "MIT"
    for index, item in enumerate(record["checkpoint_dispositions"]):
        grant = _owner_grant(item["checkpoint_id"], item["expected_sha256"], index + 10, "MIT")
        grant["authorization_scope"] = (
            "Redistribute this exact checkpoint SHA-256 in the public model release bundle."
        )
        evidence = grant["evidence"][0]
        record["rights_source_hashes"].append(
            {"path": evidence["path"], "sha256": evidence["sha256"]}
        )
        item.update(
            {
                "rights_disposition": "CLEARED",
                "rights_owner": "Powerlifting State Research contributors",
                "rights_license_expression": "MIT",
                "rights_authorization": grant,
                "redistribution_authorized": "CLEARED",
                "weights_release_status": "RELEASED",
                "release_inclusion": True,
            }
        )
    record["checkpoint_bytes_search"].update(
        {
            "redistribution_authorized": "CLEARED",
            "weights_release_status": "RELEASED",
            "release_inclusion": True,
        }
    )


def test_every_repository_file_has_an_origin_and_license_record() -> None:
    root = Path(__file__).resolve().parents[1]
    ledger = root / "provenance" / "PUBLIC_FILE_ORIGINS.csv"
    with ledger.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    paths = {row["path"] for row in rows}
    tracked = set(
        item.decode("utf-8")
        for item in subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
        ).split(b"\0")
        if item
    )
    assert len(paths) == len(rows)
    assert paths == tracked
    assert all((root / path).is_file() for path in paths)
    assert all(row["origin_class"] for row in rows)
    assert all(row["license_expression"] in {"MIT", "CC-BY-4.0"} for row in rows)
    for row in rows:
        parts = Path(row["path"]).parts
        public_audit_realization = (
            row["origin_class"] == "GENERATED_PUBLIC_ARTIFACT"
            and parts[:2] == ("results", "audits")
            and len(parts) > 4
            and parts[3] == "realizations"
        )
        expected = (
            "CC-BY-4.0"
            if row["path"].endswith(".md")
            or row["path"] == "LICENSE-DOCS"
            or public_audit_realization
            else "MIT"
        )
        assert row["license_expression"] == expected


def test_res297_baseline_hashes_cover_all_641_origin_records() -> None:
    root = Path(__file__).resolve().parents[1]
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    errors = _validate(record, prediction_rights, expected_paths, origins)
    assert errors == []
    assert len(record["hash_decisions"]) == 641

    for item in record["hash_decisions"]:
        path = item["path"]
        candidate_content = (root / path).read_bytes()
        assert hashlib.sha256(candidate_content).hexdigest() == item["candidate_sha256"], path
        baseline_content = subprocess.check_output(
            ["git", "show", f"{RES297_BASELINE}:{path}"], cwd=root
        )
        assert hashlib.sha256(baseline_content).hexdigest() == item["sha256"], path


def test_res297_shallow_checkout_uses_the_hash_pinned_baseline_ledger_prefix() -> None:
    baseline = subprocess.check_output(
        ["git", "show", f"{RES297_BASELINE}:provenance/PUBLIC_FILE_ORIGINS.csv"], cwd=ROOT
    )
    paths = baseline_paths_from_ledger_prefix(baseline)
    assert len(paths) == 641
    with pytest.raises(ValueError, match="prefix SHA-256"):
        baseline_paths_from_ledger_prefix(baseline[:-1])


def test_res297_accepts_a_complete_owner_authorized_prediction_transition() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    _clear_all_predictions(record, prediction_rights)
    assert record["candidate_release_gate"] == "GO"
    assert (
        _validate(
            record,
            prediction_rights,
            expected_paths,
            origins,
            _verified_owner_commits(record, prediction_rights),
        )
        == []
    )


def test_owner_grant_requires_a_github_verified_commit_by_the_owner() -> None:
    signed = {
        "sha": "a" * 40,
        "author": {"login": "Litju"},
        "committer": {"login": "Litju"},
        "commit": {
            "verification": {
                "verified": True,
                "reason": "valid",
                "signature": "signature",
                "payload": "payload",
            }
        },
    }
    assert is_verified_owner_commit(signed, "a" * 40)
    assert not is_verified_owner_commit(signed, "b" * 40)
    assert not is_verified_owner_commit({**signed, "author": {"login": "attacker"}}, "a" * 40)
    assert not is_verified_owner_commit(
        {**signed, "commit": {"verification": {"verified": False}}}, "a" * 40
    )
    assert not is_verified_owner_commit(
        {
            **signed,
            "commit": {"verification": {**signed["commit"]["verification"], "reason": "unknown"}},
        },
        "a" * 40,
    )
    assert not is_verified_owner_commit(
        {
            **signed,
            "commit": {"verification": {**signed["commit"]["verification"], "signature": ""}},
        },
        "a" * 40,
    )


def test_owner_grant_verifier_binds_github_signature_to_exact_document_bytes(monkeypatch) -> None:
    commit_sha = "a" * 40
    grant_path = "provenance/rights-grants/test.json"
    grant_bytes = b'{"owner_identity":"Powerlifting State Research contributors"}\n'
    commit_payload = {
        "sha": commit_sha,
        "author": {"login": "Litju"},
        "committer": {"login": "Litju"},
        "commit": {
            "verification": {
                "verified": True,
                "reason": "valid",
                "signature": "signature",
                "payload": "payload",
            }
        },
    }
    content_payload = {
        "encoding": "base64",
        "content": base64.b64encode(grant_bytes).decode("ascii"),
    }

    class Response:
        def __init__(self, payload: dict):
            self.payload = json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return self.payload

    def fake_urlopen(request, timeout):
        assert timeout == 15
        return Response(commit_payload if "/commits/" in request.full_url else content_payload)

    monkeypatch.setattr("check_repository_integrity.urllib.request.urlopen", fake_urlopen)
    verify_owner_grant_commit.cache_clear()
    assert verify_owner_grant_commit(
        commit_sha, grant_path, hashlib.sha256(grant_bytes).hexdigest()
    )
    verify_owner_grant_commit.cache_clear()
    assert not verify_owner_grant_commit(commit_sha, grant_path, "0" * 64)
    verify_owner_grant_commit.cache_clear()
    commit_payload["author"]["login"] = "attacker"
    assert not verify_owner_grant_commit(
        commit_sha, grant_path, hashlib.sha256(grant_bytes).hexdigest()
    )
    verify_owner_grant_commit.cache_clear()
    assert not verify_owner_grant_commit(
        commit_sha,
        "provenance/rights-grants/../../LICENSE",
        hashlib.sha256(grant_bytes).hexdigest(),
    )
    verify_owner_grant_commit.cache_clear()
    commit_payload["author"]["login"] = "Litju"
    content_payload["content"] = "not-base64!"
    assert not verify_owner_grant_commit(
        commit_sha, grant_path, hashlib.sha256(grant_bytes).hexdigest()
    )
    verify_owner_grant_commit.cache_clear()


def test_res297_rejects_owner_attestation_without_verified_commit() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    _clear_all_predictions(record, prediction_rights)
    errors = _validate(record, prediction_rights, expected_paths, origins)
    assert any("per-hash owner grant" in error for error in errors)


def test_res297_accepts_authorized_checkpoint_release_transition() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    _clear_all_predictions(record, prediction_rights)
    _clear_all_checkpoints(record)
    record["candidate_release_gate"] = derive_res297_release_gate(
        record["hash_decisions"],
        prediction_rights,
        record["candidate_inventory"]["new_candidate_files"],
        record["record_rights"],
        record["checkpoint_dispositions"],
    )
    record["release_inclusion_policy"]["candidate_release_gate"] = record["candidate_release_gate"]
    assert record["candidate_release_gate"] == "GO"
    assert (
        _validate(
            record,
            prediction_rights,
            expected_paths,
            origins,
            _verified_owner_commits(record, prediction_rights),
        )
        == []
    )


def test_res297_rejects_missing_or_forged_grants() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    cleared = next(
        item for item in record["hash_decisions"] if item["rights_disposition"] == "CLEARED"
    )
    cleared.pop("rights_authorization")
    assert any(
        "hash-bound owner grant" in error
        for error in _validate(record, prediction_rights, expected_paths, origins)
    )

    record, prediction_rights, expected_paths, origins = _res297_inputs()
    _clear_all_predictions(record, prediction_rights)
    prediction_rights["artifacts"][0]["rights_authorization"]["owner_attestation"][
        "authorized_signer_login"
    ] = "attacker"
    assert any(
        "per-hash owner grant" in error
        for error in _validate(
            record,
            prediction_rights,
            expected_paths,
            origins,
            _verified_owner_commits(record, prediction_rights),
        )
    )
    assert any(
        "per-hash owner grant" in error
        for error in _validate(record, prediction_rights, expected_paths, origins)
    )

    record, prediction_rights, expected_paths, origins = _res297_inputs()
    _clear_all_predictions(record, prediction_rights)
    prediction_rights["artifacts"][0]["rights_authorization"]["owner_attestation"][
        "authority_basis"
    ] = ""
    assert any(
        "per-hash owner grant" in error
        for error in _validate(
            record,
            prediction_rights,
            expected_paths,
            origins,
            _verified_owner_commits(record, prediction_rights),
        )
    )
    assert (
        derive_res297_release_gate(
            record["hash_decisions"],
            prediction_rights,
            record["candidate_inventory"]["new_candidate_files"],
            record["record_rights"],
            record["checkpoint_dispositions"],
            ["invalid owner grant"],
        )
        == "NO-GO"
    )


def test_res297_rejects_wrong_artifact_hash_and_wrong_rightsholder() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    cleared = next(
        item for item in record["hash_decisions"] if item["rights_disposition"] == "CLEARED"
    )
    cleared["rights_authorization"]["artifact_sha256"] = "0" * 64
    assert any(
        "hash-bound owner grant" in error
        for error in _validate(record, prediction_rights, expected_paths, origins)
    )

    record, prediction_rights, expected_paths, origins = _res297_inputs()
    _clear_all_predictions(record, prediction_rights)
    grant = prediction_rights["artifacts"][0]["rights_authorization"]
    grant["owner_identity"] = "Unverified third party"
    assert any(
        "per-hash owner grant" in error
        for error in _validate(
            record,
            prediction_rights,
            expected_paths,
            origins,
            _verified_owner_commits(record, prediction_rights),
        )
    )


def test_res297_rejects_license_scope_and_evidence_contradictions() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    cleared = next(
        item for item in record["hash_decisions"] if item["rights_disposition"] == "CLEARED"
    )
    cleared["rights_authorization"]["license_expression"] = "CC-BY-4.0"
    assert any(
        "hash-bound owner grant" in error
        for error in _validate(record, prediction_rights, expected_paths, origins)
    )

    record, prediction_rights, expected_paths, origins = _res297_inputs()
    _clear_all_predictions(record, prediction_rights)
    grant = prediction_rights["artifacts"][0]["rights_authorization"]
    grant["authorization_scope"] = ""
    assert any(
        "per-hash owner grant" in error
        for error in _validate(
            record,
            prediction_rights,
            expected_paths,
            origins,
            _verified_owner_commits(record, prediction_rights),
        )
    )

    record, prediction_rights, expected_paths, origins = _res297_inputs()
    cleared = next(
        item for item in record["hash_decisions"] if item["rights_disposition"] == "CLEARED"
    )
    cleared["rights_authorization"]["evidence"][0]["sha256"] = "0" * 64
    assert any(
        "hash-bound owner grant" in error
        for error in _validate(record, prediction_rights, expected_paths, origins)
    )


def test_res297_rejects_missing_checkpoint_disposition() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    record["checkpoint_dispositions"].pop()
    errors = _validate(record, prediction_rights, expected_paths, origins)
    assert any("all three checkpoint hashes" in error for error in errors)


def test_res297_rejects_incomplete_inventory() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    record["hash_decisions"].pop()
    errors = _validate(record, prediction_rights, expected_paths, origins)
    assert any("exactly cover the baseline inventory" in error for error in errors)


def test_res297_rejects_unauthorized_release_inclusion() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    record["prediction_artifacts"][0]["release_inclusion"] = True
    errors = _validate(record, prediction_rights, expected_paths, origins)
    assert any("unresolved or excluded bytes" in error for error in errors)


def test_res297_rejects_owner_grant_without_release_bundle_scope() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    _clear_all_predictions(record, prediction_rights)
    prediction_rights["artifacts"][0]["rights_authorization"]["authorization_scope"] = (
        "Redistribute these exact prediction bytes in the public repository and source archives."
    )
    errors = _validate(
        record,
        prediction_rights,
        expected_paths,
        origins,
        _verified_owner_commits(record, prediction_rights),
    )
    assert any("valid per-hash owner grant" in error for error in errors)


def test_res297_rejects_checkpoint_release_without_release_bundle_scope() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    _clear_all_predictions(record, prediction_rights)
    _clear_all_checkpoints(record)
    record["checkpoint_dispositions"][0]["rights_authorization"]["authorization_scope"] = (
        "Redistribute this checkpoint publicly."
    )
    errors = _validate(
        record,
        prediction_rights,
        expected_paths,
        origins,
        _verified_owner_commits(record, prediction_rights),
    )
    assert any("cleared checkpoint lacks a valid per-hash owner grant" in error for error in errors)


def test_res297_records_already_public_predictions_as_unresolved() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    assert _validate(record, prediction_rights, expected_paths, origins) == []
    assert all(item["already_public_git_tracked"] for item in prediction_rights["artifacts"])
    assert all(
        item["rights_disposition"] == "UNRESOLVED" for item in prediction_rights["artifacts"]
    )
    assert all(item["release_inclusion"] is False for item in prediction_rights["artifacts"])
    assert "does not contain" in prediction_rights["public_git_disposition"]


def test_res297_checkpoint_availability_is_separate_from_release_rights() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    assert _validate(record, prediction_rights, expected_paths, origins) == []
    for item in record["checkpoint_dispositions"]:
        assert item["tracked_in_git"] is False
        assert item["externally_available"] is True
        assert item["bytes_available"] is True
        assert item["bytes_hash_independently_verified"] is True
        assert item["redistribution_authorized"] == "UNRESOLVED"
        assert item["weights_release_status"] == "NOT_RELEASED"
        assert item["release_inclusion"] is False


def test_res297_rejects_incomplete_candidate_addition_inventory() -> None:
    record, prediction_rights, expected_paths, origins = _res297_inputs()
    record["candidate_inventory"]["new_candidate_files"].pop()
    assert any(
        "candidate inventory" in error
        for error in _validate(record, prediction_rights, expected_paths, origins)
    )
