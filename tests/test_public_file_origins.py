import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_repository_integrity import (  # noqa: E402
    RES297_BASELINE,
    RES297_RECORD,
    validate_res297_rights_record,
)


def _res297_inputs() -> tuple[dict, set[str], dict[str, dict[str, str]]]:
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / RES297_RECORD).read_text(encoding="utf-8"))
    with (root / "provenance/PUBLIC_FILE_ORIGINS.csv").open(newline="", encoding="utf-8") as handle:
        rows = {row["path"]: row for row in csv.DictReader(handle)}
    return record, set(rows) - {RES297_RECORD}, rows


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
    record, expected_paths, origins = _res297_inputs()
    errors = validate_res297_rights_record(record, expected_paths, origins)
    assert errors == []
    assert len(record["hash_decisions"]) == 641

    for item in record["hash_decisions"]:
        path = item["path"]
        candidate_content = (root / path).read_bytes()
        assert hashlib.sha256(candidate_content).hexdigest() == item["candidate_sha256"], path
        baseline_content = candidate_content
        if hashlib.sha256(baseline_content).hexdigest() != item["sha256"]:
            baseline_content = subprocess.check_output(
                ["git", "show", f"{RES297_BASELINE}:{path}"], cwd=root
            )
        assert hashlib.sha256(baseline_content).hexdigest() == item["sha256"], path


def test_res297_rejects_clearing_the_prediction_rights_contradiction() -> None:
    record, expected_paths, origins = _res297_inputs()
    prediction = record["prediction_artifacts"][0]
    prediction["rights_disposition"] = "CLEARED"
    next(item for item in record["hash_decisions"] if item["path"] == prediction["path"])[
        "rights_disposition"
    ] = "CLEARED"
    errors = validate_res297_rights_record(record, expected_paths, origins)
    assert any("prediction rights conflict" in error for error in errors)


def test_res297_rejects_missing_checkpoint_disposition() -> None:
    record, expected_paths, origins = _res297_inputs()
    record["checkpoint_dispositions"].pop()
    errors = validate_res297_rights_record(record, expected_paths, origins)
    assert any("all three checkpoint hashes" in error for error in errors)


def test_res297_rejects_incomplete_inventory() -> None:
    record, expected_paths, origins = _res297_inputs()
    record["hash_decisions"].pop()
    errors = validate_res297_rights_record(record, expected_paths, origins)
    assert any("exactly cover the baseline inventory" in error for error in errors)


def test_res297_rejects_unauthorized_release_inclusion() -> None:
    record, expected_paths, origins = _res297_inputs()
    record["prediction_artifacts"][0]["release_inclusion"] = True
    errors = validate_res297_rights_record(record, expected_paths, origins)
    assert any("unresolved or excluded bytes" in error for error in errors)
