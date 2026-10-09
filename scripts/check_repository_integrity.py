#!/usr/bin/env python3
"""Check the public registry, rights ledger, generated exports, and repository safety."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from powerlifting_state_research.components.worlds import WORLD_DECLARATIONS  # noqa: E402
from powerlifting_state_research.contracts.benchmark import (  # noqa: E402
    BenchmarkIdentityAuthority,
    IdentityResolution,
    ImplementationStatus,
)
from powerlifting_state_research.contracts.serialization import require_scientific_id  # noqa: E402
from powerlifting_state_research.exports import check_exports  # noqa: E402
from powerlifting_state_research.provenance import HISTORICAL_SOURCES  # noqa: E402
from powerlifting_state_research.registry import (  # noqa: E402
    BENCHMARK_REGISTRY,
    BENCHMARKS,
    resolve_benchmark,
)

DIGEST = "sha256:fbfbe59eb0a8e94b12b424c6d6837dfd455a6c5a55084bb2898b53f741cc6472"
ORIGINS = {
    "EXTERNAL_LICENSED_ARTIFACT",
    "GENERATED_PUBLIC_ARTIFACT",
    "NEWLY_AUTHORED",
    "PUBLIC_PROJECTION_OF_FROZEN_SPEC",
}
LICENSES = {"CC-BY-4.0", "MIT"}
BINARY_SUFFIXES = {
    ".7z",
    ".arrow",
    ".bin",
    ".bz2",
    ".ckpt",
    ".db",
    ".dylib",
    ".egg",
    ".exe",
    ".gz",
    ".joblib",
    ".npy",
    ".npz",
    ".onnx",
    ".parquet",
    ".pkl",
    ".pickle",
    ".pt",
    ".pth",
    ".rar",
    ".safetensors",
    ".so",
    ".sqlite",
    ".tar",
    ".tgz",
    ".whl",
    ".xz",
    ".zip",
}
PRIVATE_PATH = re.compile(
    r"(?:/(?:home|Users|root|tmp|private/tmp|workspace|workspaces|mnt/data)/[^\s\"']+"
    r"|[A-Za-z]:\\(?:Users|home)\\[^\s\"']+)"
)
SECRET = re.compile(
    r"(?i)-----BEGIN (?:(?:RSA|EC|OPENSSH|DSA) )?PRIVATE KEY-----"
    r"|\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"glpat-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b"
    r"|\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\b"
    r"\s*[:=]\s*['\"][^'\"\r\n]{16,}['\"]"
)
PRIVATE_RUN = re.compile(
    r"(?i)\b(?:codex|cursor|claude|replit|colab|kaggle|vercel|openai|anthropic)"
    r"[._:/-](?:run|job|execution|session)[._:/-][a-z0-9-]{8,}\b"
)
PRIVATE_REPO = "ALI4" + "-OpenSource-Recovery"
OLD_MODULE_NAMES = {"c21", "c22", "v1", "v2", "t0", "t1"}
ERRORS: list[str] = []


def fail(message: str) -> None:
    ERRORS.append(message)


def git_files(*options: str) -> set[str]:
    output = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", *options, "-z"])
    return {item.decode() for item in output.split(b"\0") if item}


def check_registry() -> None:
    if len(BENCHMARKS) != 9 or len(BENCHMARK_REGISTRY) != 9:
        fail("benchmark registry must contain 8 historical records and 1 public-native variant")
    slugs = {spec.slug for spec in BENCHMARKS}
    if len(slugs) != len(BENCHMARKS):
        fail("benchmark slugs must be unique")
    worlds = {world.slug for world in WORLD_DECLARATIONS}
    if len(worlds) != len(WORLD_DECLARATIONS):
        fail("canonical world slugs must be unique")
    if worlds & {alias for world in WORLD_DECLARATIONS for alias in world.historical_aliases}:
        fail("historical world alias is canonical")
    aliases = {alias for item in HISTORICAL_SOURCES.values() for alias in item.historical_aliases}
    if aliases & set(BENCHMARK_REGISTRY):
        fail("historical benchmark alias is canonical")

    for spec in BENCHMARKS:
        if not isinstance(spec.public_implementation_status, ImplementationStatus):
            fail(f"invalid implementation status: {spec.slug}")
        shared_namespace = (
            spec.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE
            and len(spec.related_benchmark_slugs) == 1
            and spec.related_benchmark_slugs[0] in BENCHMARK_REGISTRY
            and BENCHMARK_REGISTRY[spec.related_benchmark_slugs[0]].python_namespace
            == spec.python_namespace
        )
        if (
            spec.slug.startswith("benchmark_")
            or (spec.python_namespace.rsplit(".", 1)[-1] != spec.slug and not shared_namespace)
            or spec.docs_path != f"docs/benchmarks/{spec.slug.replace('_', '-')}.md"
            or spec.test_path != f"tests/benchmarks/{spec.slug}/test_spec.py"
        ):
            fail(f"noncanonical benchmark name or path: {spec.slug}")
        module = ROOT / "src" / Path(*spec.python_namespace.split("."))
        if not (module / "__init__.py").is_file() or not all(
            (ROOT / path).is_file() for path in (spec.docs_path, spec.test_path)
        ):
            fail(f"canonical benchmark files are missing: {spec.slug}")
        if spec.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE:
            identity = spec.semantic_identity
            if (
                not identity
                or any(
                    component.resolution is not IdentityResolution.DIRECT
                    for component in (
                        identity.world_id,
                        identity.population_id,
                        identity.intervention_regime_id,
                        identity.observation_model_id,
                    )
                )
                or not spec.identity_mintable
            ):
                fail(f"PUBLIC_NATIVE requires direct component IDs: {spec.slug}")
    for world in WORLD_DECLARATIONS:
        try:
            require_scientific_id(world.component_identity_id, "world ID", expected_class="world")
        except ValueError as error:
            fail(str(error))
    spec = resolve_benchmark("latent_capacity_change_with_transient_expression_forecasting")
    if not spec.identity_mintable or spec.semantic_digest != DIGEST:
        fail("frozen historical benchmark digest or mintability changed")
    native = resolve_benchmark("iid_latent_capacity_change_with_transient_expression_forecasting")
    if (
        native.identity_authority is not BenchmarkIdentityAuthority.PUBLIC_NATIVE
        or native.public_implementation_status is not ImplementationStatus.PUBLIC_IMPLEMENTED
        or native.semantic_digest == spec.semantic_digest
        or native.semantic_identity is None
        or native.semantic_identity.dataset_spec_id == spec.semantic_identity.dataset_spec_id
        or native.related_benchmark_slugs != (spec.slug,)
        or spec.related_benchmark_slugs != (native.slug,)
        or spec.public_implementation_status
        is not ImplementationStatus.PUBLIC_IMPLEMENTATION_PENDING
    ):
        fail("historical projection and public-native identity/status relation is inconsistent")
    for path in check_exports():
        fail(f"generated export is stale or missing: {path}")


def check_ledger(tracked: set[str]) -> int:
    with (ROOT / "provenance/PUBLIC_FILE_ORIGINS.csv").open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        columns = {"path", "origin_class", "license_expression", "owner", "purpose"}
        if set(reader.fieldnames or ()) != columns:
            fail("origin ledger has unexpected columns")
            return 0
        rows = list(reader)
    paths = [row.get("path") or "" for row in rows]
    if any(not path or Path(path).is_absolute() or ".." in Path(path).parts for path in paths):
        fail("origin ledger contains an invalid repository path")
    counts = Counter(path for path in paths if path)
    if any(count != 1 for count in counts.values()):
        fail("origin ledger contains duplicate paths")
    if tracked - counts.keys():
        fail(f"origin ledger misses tracked files: {sorted(tracked - counts.keys())[:5]}")
    stale = {path for path in counts.keys() - tracked if not (ROOT / path).exists()}
    if stale:
        fail(f"origin ledger contains stale paths: {sorted(stale)[:5]}")
    for row in rows:
        path = row.get("path") or "<missing path>"
        origin, license_scope = row.get("origin_class"), row.get("license_expression")
        if origin not in ORIGINS or license_scope not in LICENSES:
            fail(f"invalid origin or license classification: {path}")
        if any(not (row.get(field) or "").strip() for field in ("owner", "purpose")):
            fail(f"origin ledger row lacks required rights scope: {path}")
        expected = "CC-BY-4.0" if path.endswith(".md") or path == "LICENSE-DOCS" else "MIT"
        if license_scope != expected:
            fail(f"origin ledger license does not match file scope: {path}")
    return len(rows)


def check_public_files(paths: set[str]) -> None:
    for name in paths:
        path, parts = ROOT / name, Path(name).parts
        if ".git" in parts:
            fail(f"nested Git metadata: {name}")
        if path.suffix.lower() in BINARY_SUFFIXES:
            fail(f"forbidden archive or binary class: {name}")
        if parts[0] in {"src", "tests", "docs"} and not ({"provenance", "history"} & set(parts)):
            for part in parts:
                lowered = part.lower()
                if lowered in OLD_MODULE_NAMES or lowered.startswith(
                    ("pl_legacy_", "pl_response_")
                ):
                    fail(f"internal lineage used as canonical path: {name}")
        if PRIVATE_REPO.lower() in name.lower() or PRIVATE_RUN.search(name):
            fail(f"private repository or execution ID: {name}")
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data or data.startswith((b"PK\x03\x04", b"\x1f\x8b", b"Rar!\x1a\x07")):
            fail(f"binary or archive payload: {name}")
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            fail(f"non-text payload: {name}")
            continue
        if PRIVATE_PATH.search(text):
            fail(f"private absolute path: {name}")
        if SECRET.search(text):
            fail(f"credential or private-key material: {name}")
        if PRIVATE_REPO.lower() in text.lower() or PRIVATE_RUN.search(text):
            fail(f"private repository or execution ID: {name}")

    for current, dirs, files in os.walk(ROOT):
        if Path(current) == ROOT:
            dirs[:] = [name for name in dirs if name not in {".git", ".venv", "__pycache__"}]
        elif ".git" in dirs or ".git" in files:
            fail(f"nested Git metadata: {Path(current).relative_to(ROOT)}")
            dirs[:] = [name for name in dirs if name != ".git"]


def verify_gate_c_package(root: Path = ROOT) -> list[str]:
    """Verify committed RES-274 Gate-C evidence without external services."""
    errors: list[str] = []
    bundle_sha = "fa31764220dbca936275b07965e7b4b4adb146251fc38db063dc5e88de8eaec4"
    inventory_path = "results/manifests/public-native-temporal-expert-source-inventory.json"
    receipt_path = "results/manifests/public-native-temporal-expert-verification-receipt.json"
    manifest_path = "results/manifests/public-native-temporal-expert.json"
    index_path = "results/manifests/public-native-temporal-expert-checksums.json"
    inventory_sha = "416a7cfb2f0a7bef3a6865a3649f49859f1108db1f98aafc09529f447855e616"
    receipt_sha = "fd11790ea0f4b461f38d6cb96f6fb925ec9917128b53a54e0a6f053197771273"
    distribution = "PUBLIC_SAFE_BYTES_VERIFIED_RELEASE_ASSET_PENDING"
    model = "psr:model:public-native-lift-shared-temporal-gru-capacity-change@1.0.0~34d23123138f"
    protocol = "psr:training-protocol:public-native-temporal-expert@1.0.0~dc47230f3465"
    dataset = (
        "psr:dataset-realization:latent-capacity-transient-iid-production@sha256:"
        "2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad"
    )
    evaluation = (
        "psr:evaluation:iid-latent-capacity-change-four-metric-validation@1.0.0~cd4fe982e7b8"
    )
    benchmark = (
        "psr:benchmark-spec:iid-latent-capacity-change-with-transient-expression-"
        "forecasting@1.0.0~f99463d55ba0"
    )
    seed_facts = {
        383001: (
            "f8889305226cbac69874a2a983809e2b12adfdbfb8dd6446dbce932ac02904bb",
            "8097eb52fabd88d36992b2af5e363baab3b5e2333d5701798430b20882ce31b9",
            54,
            0.15088153822037306,
            "39615cfdbe3e54cb2f0f69b567eee8f1bad49b12eb5d772753ba58553b3303f1",
        ),
        383002: (
            "eb6c858e20e3a0cba5a542db605494359df83c15fac54b068ed938866d1398c4",
            "7f4caedb37631f4aab38fa7cc1156b9625a5e71825b31b05b1385e4790c5763b",
            44,
            0.14870723135963548,
            "cb614f4c68075544a0521e9a5cc393ba2761e5a47e714818c2fe31175e3dc4b6",
        ),
        383003: (
            "c8f6bb329ee6b9e37155d95515e071b98d0aacf720f163bbe060804a0ecdef18",
            "e77b5b66e868fcb9345717d913d5bd6bcc17237c0d27ae46bf9cf994b5e5d59f",
            68,
            0.1491499231254783,
            "ea4519bc80bcb8b83b3a257937b6d95452e6e9cf901b62585c4326680b7dad1c",
        ),
    }
    ensemble = (
        "psr:ensemble:public-native-temporal-expert-three-seed-standardized-mean@sha256:"
        "9903ff129182dee5b85146affef6cb44de1e586063977f6f439d693ab5686fb7"
    )
    ensemble_fit = (
        "psr:fitted-instance:public-native-temporal-expert-three-seed-ensemble@sha256:"
        "ff4e475ffeef1c03976c92c5868e75d0afd72672cb2848f0250e707dbd4c7fad"
    )
    ensemble_result_id = (
        "psr:evaluation-result@sha256:"
        "84ccca3c7c53322e1271d07e2578257f8dfcebe14517a1b736898aacc6e93778"
    )

    def check(ok: bool, message: str) -> None:
        if not ok:
            errors.append(message)

    def load(path: str) -> dict:
        try:
            value = json.loads((root / path).read_text(encoding="utf-8"))
            check(isinstance(value, dict), f"invalid Gate-C JSON object: {path}")
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"missing or invalid Gate-C JSON {path}: {error}")
            return {}

    def sha(path: str) -> str:
        try:
            return hashlib.sha256((root / path).read_bytes()).hexdigest()
        except OSError as error:
            errors.append(f"unreadable Gate-C file {path}: {error}")
            return ""

    def matches(value: object, fields: dict[str, object]) -> bool:
        return isinstance(value, dict) and all(value.get(k) == v for k, v in fields.items())

    inv, receipt, run, sums = map(load, (inventory_path, receipt_path, manifest_path, index_path))
    entries = inv.get("entries", [])
    source_hashes = {e.get("path"): e.get("sha256") for e in entries if isinstance(e, dict)}
    checkpoint_members = {f"seed-{seed}/checkpoint.pt" for seed in (383001, 383002, 383003)}
    check(
        inv.get("algorithm") == "SHA-256"
        and len(source_hashes) == 31
        and {path for path in source_hashes if path.endswith(".pt")} == checkpoint_members
        and all(
            source_hashes.get(f"seed-{seed}/checkpoint.pt") == facts[0]
            for seed, facts in seed_facts.items()
        )
        and sha(inventory_path) == inventory_sha,
        "Gate-C source SHA inventory changed",
    )
    check(
        sha(receipt_path) == receipt_sha
        and receipt.get("status") == "PASS"
        and receipt.get("run_id") == "20261008T071545Z-827f338c"
        and receipt.get("verifier_code_sha") == "33e8dcecf49747314c182feb596dadb4527fbddd"
        and receipt.get("bundle_sha256") == bundle_sha,
        "Gate-C verification receipt changed",
    )
    check(
        sums.get("source_bundle_sha256") == bundle_sha
        and sums.get("source_archive_member_count") == 33
        and sums.get("source_inventory_entry_count") == 31,
        "Gate-C source bundle binding changed",
    )
    check(
        sums.get("source_inventory") == {"path": inventory_path, "sha256": inventory_sha}
        and sums.get("verification_receipt")
        == {"path": receipt_path, "sha256": receipt_sha, "status": "PASS"}
        and sums.get("run_manifest") == {"path": manifest_path, "sha256": sha(manifest_path)},
        "Gate-C checksum index binding changed",
    )

    source_fields = {
        "artifact_code_sha": "6039f3a8ee685fe4254ab607b57df28ca38220f6",
        "verifier_code_sha": "33e8dcecf49747314c182feb596dadb4527fbddd",
        "bundle_sha256": bundle_sha,
        "source_inventory_path": inventory_path,
        "source_inventory_sha256": inventory_sha,
        "verification_status": "PASS",
        "verification_receipt_path": receipt_path,
        "verification_receipt_sha256": receipt_sha,
    }
    identity_fields = {
        "model_id": model,
        "training_protocol_id": protocol,
        "benchmark_spec_id": benchmark,
        "benchmark_spec_digest": (
            "sha256:f99463d55ba0902595a1866032ba94b803ac97d9b4985a89e208293da9c7fed0"
        ),
        "dataset_spec_id": (
            "psr:dataset-spec:latent-capacity-transient-iid-sampling-design@1.0.0~1d079eb645ed"
        ),
        "dataset_realization_id": dataset,
        "dataset_realization_digest": (
            "sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad"
        ),
        "evaluation_id": evaluation,
    }
    check(
        run.get("format") == "PSR_PUBLIC_NATIVE_INGESTED_RUN_V1"
        and run.get("run_id") == "20261008T071545Z-827f338c"
        and matches(run.get("source"), source_fields)
        and matches(run.get("scientific_identity"), identity_fields),
        "Gate-C run manifest identities changed",
    )
    split = run.get("internal_selection", {})
    check(
        matches(
            split,
            {
                "fit_row_count": 9984,
                "selection_row_count": 2304,
                "entity_disjoint": True,
                "normalization_fit_row_count": 9984,
                "selection_used_for_normalization": False,
                "normalization_stats_id": (
                    "psr:normalization-stats:public-native-temporal-expert@sha256:"
                    "a8ad5b193e2d0e78ebdc341e550bed5be4b8352bfb72d3328a12add247c6f320"
                ),
            },
        ),
        "Gate-C split/normalization identity changed",
    )
    check(
        run.get("checkpoint_distribution_state") == distribution,
        "Gate-C checkpoint distribution state changed",
    )
    runtime = run.get("runtime_fingerprint", {})
    check(
        runtime.get("gpu_name") == "NVIDIA RTX PRO 6000 Blackwell Server Edition"
        and runtime.get("torch_version") == "2.9.1+cu128"
        and runtime.get("torch_cuda_version") == "12.8"
        and runtime.get("cudnn_version") == 91002
        and runtime.get("python") == "3.12.3"
        and runtime.get("nvidia_driver") == "580.82.07"
        and runtime.get("platform") == "Linux-6.6.122+-x86_64-with-glibc2.39"
        and runtime.get("determinism_controls", {}).get("cross_gpu_bitwise_guarantee") is False,
        "Gate-C runtime fingerprint changed",
    )
    seal = run.get("validation_isolation", {})
    check(
        seal.get("all_seed_checkpoints_sealed") is True
        and seal.get("canonical_validation_scored_before_sealing") is False
        and seal.get("seed_checkpoints_sealed_before_scoring") is True
        and seal.get("canonical_validation_used_for_selection") == [False, False, False]
        and seal.get("checkpoint_seal_sha256") == source_hashes.get("receipts/checkpoint-seal.json")
        and seal.get("training_receipt_sha256") == source_hashes.get("receipts/training-run.json")
        and seal.get("validation_order_receipt_sha256")
        == source_hashes.get("receipts/validation-evaluation.json")
        and seal.get("checkpoints_sealed_at_utc") < seal.get("validation_started_at_utc"),
        "Gate-C checkpoint-seal/validation-isolation evidence changed",
    )

    indexed = {x.get("path"): x for x in sums.get("copied_artifacts", []) if isinstance(x, dict)}
    expected_paths: set[str] = set()
    records = run.get("checkpoints", [])
    check(
        len(records) == 3 and {x.get("seed") for x in records} == set(seed_facts),
        "Gate-C run manifest must bind the three declared seeds",
    )
    for record in records:
        seed = record.get("seed")
        if seed not in seed_facts:
            continue
        checkpoint_sha, fit_sha, epoch, loss, result_sha = seed_facts[seed]
        checkpoint_id = (
            f"psr:checkpoint:public-native-temporal-expert-seed-{seed}@sha256:{checkpoint_sha}"
        )
        fitted_id = (
            f"psr:fitted-instance:public-native-temporal-expert-seed-{seed}@sha256:{fit_sha}"
        )
        check(
            record.get("checkpoint_id") == checkpoint_id
            and record.get("checkpoint_sha256") == checkpoint_sha
            and record.get("fitted_instance_id") == fitted_id
            and record.get("selected_epoch") == epoch
            and record.get("selection_standardized_mse") == loss
            and record.get("canonical_validation_used_for_selection") is False,
            f"Gate-C checkpoint identity/selection changed for seed {seed}",
        )
        for key in (
            "checkpoint_manifest",
            "fitted_instance_manifest",
            "prediction",
            "evaluation_result",
        ):
            item = record.get(key, {})
            path, member = item.get("path"), item.get("source_member")
            expected_paths.add(path)
            digest = sha(path)
            check(
                digest
                == item.get("sha256")
                == item.get("source_sha256")
                == source_hashes.get(member)
                and indexed.get(path, {}).get("sha256") == digest,
                f"Gate-C copied artifact differs from source inventory: {path}",
            )
        checkpoint = load(record["checkpoint_manifest"]["path"])
        fitted = load(record["fitted_instance_manifest"]["path"])
        check(
            checkpoint.get("checkpoint_id") == checkpoint_id
            and checkpoint.get("checkpoint_sha256") == checkpoint_sha
            and checkpoint.get("canonical_validation_used") is False
            and checkpoint.get("model_id") == model
            and checkpoint.get("training_protocol_id") == protocol
            and checkpoint.get("dataset_realization_id") == dataset
            and fitted.get("fitted_instance_id") == fitted_id
            and fitted.get("checkpoint_sha256") == checkpoint_sha
            and fitted.get("model_id") == model
            and fitted.get("training_protocol_id") == protocol
            and fitted.get("dataset_realization_id") == dataset,
            f"Gate-C checkpoint metadata changed for seed {seed}",
        )
        result_id = f"psr:evaluation-result@sha256:{result_sha}"
        result_file = load(record["evaluation_result"]["path"])
        result = result_file.get("result", {})
        pred = record["prediction"]
        check(
            record["evaluation_result"].get("result_id") == result_id
            and result_file.get("result_id") == result_id
            and result.get("evaluation_id") == evaluation
            and result.get("benchmark_id") == benchmark
            and result.get("dataset_realization_id") == dataset
            and result.get("model", {}).get("model_id") == model
            and result.get("training_protocol", {}).get("training_protocol_id") == protocol
            and result.get("fitted_instance", {}).get("fitted_instance_id") == fitted_id
            and result.get("prediction_artifact", {}).get("artifact_id") == pred.get("artifact_id")
            and result.get("prediction_artifact", {}).get("content_sha256")
            == f"sha256:{pred.get('sha256')}"
            and len(result.get("targets", [])) == 3
            and all(len(x.get("metrics", [])) == 4 for x in result.get("targets", [])),
            f"Gate-C EvaluationResult binding changed for seed {seed}",
        )

    ensemble_run = run.get("ensemble", {})
    check(
        ensemble_run.get("ensemble_id") == ensemble
        and ensemble_run.get("fitted_instance_id") == ensemble_fit
        and ensemble_run.get("seed_order") == [383001, 383002, 383003],
        "Gate-C ensemble identity changed",
    )
    ensemble_manifest = load(ensemble_run["ensemble_manifest"]["path"])
    check(
        ensemble_manifest.get("ensemble_id") == ensemble
        and ensemble_manifest.get("ensemble_fitted_instance_id") == ensemble_fit
        and ensemble_manifest.get("model_id") == model
        and ensemble_manifest.get("training_protocol_id") == protocol
        and ensemble_manifest.get("dataset_realization_id") == dataset
        and ensemble_manifest.get("evaluation_result_id") == ensemble_result_id
        and ensemble_manifest.get("seed_order") == [383001, 383002, 383003]
        and ensemble_manifest.get("rule")
        == "equal arithmetic mean in standardized target space; inverse transform once",
        "Gate-C ensemble manifest identity changed",
    )
    for key in ("ensemble_manifest", "prediction", "evaluation_result"):
        item = ensemble_run.get(key, {})
        path, member = item.get("path"), item.get("source_member")
        expected_paths.add(path)
        digest = sha(path)
        check(
            digest == item.get("sha256") == item.get("source_sha256") == source_hashes.get(member)
            and indexed.get(path, {}).get("sha256") == digest,
            f"Gate-C ensemble artifact differs from source inventory: {path}",
        )
    ensemble_result = load(ensemble_run["evaluation_result"]["path"])
    result = ensemble_result.get("result", {})
    pred = ensemble_run.get("prediction", {})
    check(
        ensemble_result.get("result_id") == ensemble_result_id
        and result.get("evaluation_id") == evaluation
        and result.get("benchmark_id") == benchmark
        and result.get("dataset_realization_id") == dataset
        and result.get("model", {}).get("model_id") == model
        and result.get("training_protocol", {}).get("training_protocol_id") == protocol
        and result.get("fitted_instance", {}).get("fitted_instance_id") == ensemble_fit
        and result.get("prediction_artifact", {}).get("artifact_id") == pred.get("artifact_id")
        and result.get("prediction_artifact", {}).get("content_sha256")
        == f"sha256:{pred.get('sha256')}",
        "Gate-C ensemble EvaluationResult binding changed",
    )
    publication_path = (
        "models/checkpoint-manifests/public-native-temporal-expert/checkpoint-publication.json"
    )
    publication = load(publication_path)
    check(
        publication.get("checkpoint_distribution_state") == distribution
        and publication.get("source_bundle_sha256") == bundle_sha
        and publication.get("verification_status") == "PASS"
        and sums.get("checkpoint_publication_index")
        == {"path": publication_path, "sha256": sha(publication_path)},
        "Gate-C checkpoint publication metadata changed",
    )
    metadata_paths = {
        r[k]["path"] for r in records for k in ("checkpoint_manifest", "fitted_instance_manifest")
    }
    metadata_paths.add(ensemble_run["ensemble_manifest"]["path"])
    metadata = {
        x.get("path"): x for x in sums.get("checkpoint_metadata", []) if isinstance(x, dict)
    }
    check(
        set(indexed) == expected_paths
        and set(metadata) == metadata_paths
        and all(metadata[path].get("sha256") == sha(path) for path in metadata_paths),
        "Gate-C checksum index artifact/metadata set changed",
    )

    card_path = "artifacts/model-cards/public-native-temporal-capacity-change.md"
    card = (root / card_path).read_text(encoding="utf-8")
    check("## PUBLIC_NATIVE fitted evidence (IID)" in card, "Gate-C model card section is missing")
    for record in [*records, ensemble_run]:
        result = load(record["evaluation_result"]["path"]).get("result", {})
        for target in result.get("targets", []):
            for metric in target.get("metrics", []):
                check(
                    str(metric.get("value")) in card,
                    f"Gate-C model card omits {target.get('target')} metric",
                )

    package = expected_paths | {
        inventory_path,
        receipt_path,
        manifest_path,
        index_path,
        publication_path,
        card_path,
    }
    forbidden = (
        "drive.google.com",
        "sediment://",
        "/content/",
        "/drive/MyDrive/",
        "file_uri",
        "download_url",
        "1zx9xowz3ofzQY2ox7Sqoes9OMzEo-6Y6",
        "16q0oPzRokiu2rs1FyoidmD_72RYGHyNY",
    )
    for relative in package:
        try:
            text = (root / relative).read_text(encoding="utf-8")
            check(
                not PRIVATE_PATH.search(text) and not any(marker in text for marker in forbidden),
                f"Gate-C public artifact contains private path/Drive reference: {relative}",
            )
        except (OSError, UnicodeDecodeError) as error:
            errors.append(f"Gate-C public artifact is unreadable: {relative}: {error}")
    tracked = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"]).split(bytes([0]))
    check(
        not any(
            Path(item.decode()).suffix.lower() in {".pt", ".pth", ".ckpt", ".safetensors"}
            for item in tracked
            if item
        ),
        "tracked checkpoint bytes are forbidden",
    )
    return errors


def main() -> int:
    try:
        tracked = git_files()
        check_registry()
        rows = check_ledger(tracked)
        check_public_files(git_files("--cached", "--others", "--exclude-standard"))
        for error in verify_gate_c_package():
            fail(error)
    except (OSError, subprocess.CalledProcessError) as error:
        fail(f"repository scan failed: {error}")
        rows = 0
    if ERRORS:
        print("FAIL: public repository integrity scan")
        print("\n".join(f"- {error}" for error in ERRORS))
        return 1
    print(
        f"PASS: 9 benchmark records (8 historical); frozen digest; exports; public safety; "
        f"{rows} rights-ledger rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
