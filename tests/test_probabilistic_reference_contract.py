"""Identity, leakage, rights and safe-failure checks for the RES-615 public reference contract."""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from powerlifting_state_research.contracts.serialization import (
    require_scientific_id,
    sha256_record,
)
from powerlifting_state_research.probabilistic import contract as C

ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results/references/public-probabilistic-latent-capacity-change-v1"


def test_frozen_protocol_file_is_exactly_the_code_contract() -> None:
    assert (RESULT_DIR / "protocol.json").read_bytes() == C.protocol_bytes()
    document = json.loads((RESULT_DIR / "protocol.json").read_text(encoding="utf-8"))
    assert document["reference_id"] == C.REFERENCE_ID
    assert document["protocol_digest"] == sha256_record(document["protocol"])
    assert document["rights_register_digest"] == sha256_record(document["rights_register"])


def test_identity_is_new_distinct_and_content_bound() -> None:
    require_scientific_id(C.REFERENCE_ID, "reference", expected_class="reference-experiment")
    assert C.REFERENCE_ID.endswith("~" + C.PROTOCOL_DIGEST[7:19])
    # a different protocol content must mint a different identity
    changed = copy.deepcopy(C.PROTOCOL)
    changed["cohorts"]["roles"]["TEST"]["seeds"][0] += 1
    assert sha256_record(changed) != C.PROTOCOL_DIGEST
    # never conflated with the GRU model identity or the historical M10-M12 evidence digests
    assert C.REFERENCE_ID != C.GRU_ID
    historical = (
        "c38c8952fc5308892d77323a12ba20c1215144dee13ca5c2ddabfe3e3230e4bf",
        "74ff10e1694dcd2f8cd055e1f40975ce1f121280c71c6f17de5b818d6c4b0536",
        "c801305e704c72e7c5b18da0bfa102a3b3bde2f5c5267e5644b3ef8c1cdd9284",
    )
    assert not any(item in C.protocol_bytes().decode() for item in historical)
    assert "NOT a reproduction" in C.PROTOCOL["route"]
    assert any("does not reproduce historical" in item for item in C.PROTOCOL["nonclaims"])


@pytest.mark.parametrize("roles", ["roles", "smoke_roles"])
def test_cohorts_are_disjoint_balanced_and_exclude_canonical_seeds(roles: str) -> None:
    cohorts = C.PROTOCOL["cohorts"][roles]
    assert set(cohorts) == {"FIT", "CAL_C", "CAL_G", "TEST"}
    seeds = [seed for item in cohorts.values() for seed in item["seeds"]]
    assert len(seeds) == len(set(seeds)) == 20
    assert not set(seeds) & set(C.CANONICAL_IID_SEEDS)
    all_seeds = [
        seed
        for group in ("roles", "smoke_roles")
        for item in C.PROTOCOL["cohorts"][group].values()
        for seed in item["seeds"]
    ]
    assert len(all_seeds) == len(set(all_seeds)), "smoke and full cohorts must not share seeds"
    strata = len(C.PLANS) * len(C.HORIZONS)
    assert all(item["rows"] % strata == 0 and item["rows"] >= strata for item in cohorts.values())
    # separate roles, so calibration never sees fit rows and TEST never feeds any parameter
    assert C.PROTOCOL["cohorts"]["split_use"]["TEST"].startswith("scored once")


def test_full_cohorts_follow_the_documented_sizes() -> None:
    sizes = {name: item["rows"] for name, item in C.COHORTS.items()}
    assert sizes == {"FIT": 12288, "CAL_C": 3072, "CAL_G": 3072, "TEST": 3072}
    assert C.RESOURCE_LIMITS["max_process_memory_bytes"] == 2 * 1024**3
    assert C.RESOURCE_LIMITS["max_cpu_seconds"] == 1800
    assert C.RESOURCE_LIMITS["workers"] == 1 and C.RESOURCE_LIMITS["gpu"] is False


def test_protocol_pins_the_published_checkpoint_hashes() -> None:
    assets = C.verify_released_assets(ROOT)
    assert set(assets) == {
        "seed-383001.pt",
        "seed-383002.pt",
        "seed-383003.pt",
        "normalization-stats.json",
    }
    manifest = json.loads((ROOT / C.GRU_MANIFEST_PATH).read_text(encoding="utf-8"))
    published = {
        item["scientific_identity"]["seed"]: item["sha256"]
        for item in manifest["artifacts"]
        if item["kind"] == "trained checkpoint"
    }
    assert published == {
        int(name.removeprefix("seed-")): digest for name, digest in C.GRU_CHECKPOINT_SHA256.items()
    }


def _copy_release(tmp_path: Path) -> Path:
    for relative in (
        C.GRU_MANIFEST_PATH,
        *[
            f"models/published/public-native-temporal-expert/checkpoints/{name}.pt"
            for name in C.GRU_CHECKPOINT_SHA256
        ],
        "models/published/public-native-temporal-expert/source-run/normalization/"
        "normalization-stats.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return tmp_path


def test_release_copy_verifies_and_failures_are_safe(tmp_path: Path) -> None:
    release = _copy_release(tmp_path)
    assert len(C.verify_released_assets(release)) == 4
    checkpoint = (
        release / "models/published/public-native-temporal-expert/checkpoints/seed-383002.pt"
    )
    original = checkpoint.read_bytes()
    checkpoint.write_bytes(original + b"\0")
    with pytest.raises(ValueError, match="do not match the pinned SHA-256"):
        C.verify_released_assets(release)
    checkpoint.unlink()
    with pytest.raises(FileNotFoundError, match="missing from this checkout"):
        C.verify_released_assets(release)
    checkpoint.write_bytes(original)
    manifest_path = release / C.GRU_MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        if item["path"].endswith("seed-383001.pt"):
            item["artifact_manifest"]["license_expression"] = "CC-BY-4.0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="not a cleared, hash-pinned release record"):
        C.verify_released_assets(release)
    manifest_path.unlink()
    with pytest.raises(FileNotFoundError, match="manifest is missing"):
        C.verify_released_assets(release)
    with pytest.raises(FileNotFoundError):
        C.verify_released_assets(tmp_path / "not-a-checkout")


def test_a_matching_hash_alone_does_not_clear_an_unlisted_file(tmp_path: Path) -> None:
    release = _copy_release(tmp_path)
    manifest_path = release / C.GRU_MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"] = [
        item for item in manifest["artifacts"] if not item["path"].endswith("seed-383003.pt")
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    # the file bytes are present and correct, but no MIT release record names them
    assert (
        release / "models/published/public-native-temporal-expert/checkpoints/seed-383003.pt"
    ).is_file()
    with pytest.raises(ValueError, match="not a cleared, hash-pinned release record"):
        C.verify_released_assets(release)


def test_rights_register_separates_reuse_from_excluded_private_artifacts() -> None:
    by_decision: dict[str, list[str]] = {}
    for entry in C.RIGHTS_REGISTER:
        assert {
            "artifact",
            "decision",
            "access",
            "use",
            "modification",
            "redistribution",
            "basis",
        } <= set(entry)
        by_decision.setdefault(entry["decision"], []).append(entry["artifact"])
    assert set(by_decision) == {
        "REUSED",
        "NOT_USED",
        "GENERATED_AT_RUNTIME",
        "EXCLUDED",
        "REFERENCED_ONLY",
    }
    excluded = " ".join(by_decision["EXCLUDED"])
    for name in ("H / H_GT", "G factors", "adapters", "cohorts"):
        assert name in excluded
    for entry in C.RIGHTS_REGISTER:
        if entry["decision"] == "EXCLUDED":
            assert entry["redistribution"].startswith("no grant")


def test_no_rights_excluded_artifact_class_is_tracked_in_the_repository() -> None:
    tracked = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    binaries = [
        path
        for path in tracked
        if path.endswith((".pt", ".npz", ".pkl", ".pickle", ".joblib", ".safetensors"))
        and not path.startswith("models/published/")
        and not path.startswith("models/checkpoints/")
    ]
    assert binaries == []
    reference_files = [path for path in tracked if "references/public-probabilistic" in path]
    assert not any(path.endswith((".jsonl", ".parquet", ".npy")) for path in reference_files)


def test_resource_and_tolerance_declarations_are_complete() -> None:
    assert C.TOLERANCES["crps_hard_bound_kg_abs"] == 0.0167
    assert C.PROTOCOL["resources"]["retries"] == 0
    assert C.PROTOCOL["truth_firewall"]["order"][-1] == "open TEST truth and score once"
