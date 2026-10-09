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
from powerlifting_state_research.contracts.serialization import (  # noqa: E402
    require_scientific_id,
    sha256_record,
)
from powerlifting_state_research.evaluation.identity import (  # noqa: E402
    EVALUATION_ID,
    METRIC_IDENTITIES,
    TARGETS,
)
from powerlifting_state_research.evaluation.prediction import (  # noqa: E402
    PREDICTION_SCHEMA_ID,
    parse_prediction_jsonl,
)
from powerlifting_state_research.exports import check_exports  # noqa: E402
from powerlifting_state_research.models.comparators import MODEL_SPECS  # noqa: E402
from powerlifting_state_research.models.training import (  # noqa: E402
    COMPARATOR_TRAINING_PROTOCOL_DIGEST,
    COMPARATOR_TRAINING_PROTOCOL_ID,
)
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


def verify_res275_comparator_package(root: Path = ROOT) -> list[str]:
    """Verify frozen RES-275 identities, result bindings, and every indexed byte."""
    errors: list[str] = []
    protocol_path = "artifacts/training-protocols/public-native-comparator-suite.json"
    registry_path = "artifacts/registries/public-native-comparator-registry.json"
    run_path = "results/manifests/public-native-comparator-suite.json"
    index_path = "results/manifests/public-native-comparator-suite-checksums.json"
    metrics_path = "results/tables/public-native-comparator-frontier.csv"
    fitted_root = "models/fitted-instances/public-native-comparator-suite"
    output_root = (
        "results/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/"
        "public-native-comparator-suite"
    )
    benchmark_id = (
        "psr:benchmark-spec:iid-latent-capacity-change-with-transient-expression-"
        "forecasting@1.0.0~f99463d55ba0"
    )
    benchmark_digest = "sha256:f99463d55ba0902595a1866032ba94b803ac97d9b4985a89e208293da9c7fed0"
    dataset_id = (
        "psr:dataset-realization:latent-capacity-transient-iid-production@sha256:"
        "2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad"
    )
    dataset_digest = "sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad"
    train_sha256 = "914dc51fcf9a0dca30224a8093431e97fe29272bf830160bf46a78396026d550"
    validation_sha256 = "0d7bd0c9291e7af5627ec18e2b82025aa1f5f3d46de07d502f7df90eace24b9a"
    seeds = (383001, 383002, 383003)

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    def load(path: str) -> dict:
        try:
            value = json.loads((root / path).read_text(encoding="utf-8"))
            check(isinstance(value, dict), f"invalid RES-275 JSON object: {path}")
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"missing or invalid RES-275 JSON {path}: {error}")
            return {}

    def file_sha(path: str) -> str:
        try:
            return hashlib.sha256((root / path).read_bytes()).hexdigest()
        except OSError as error:
            errors.append(f"unreadable RES-275 artifact {path}: {error}")
            return ""

    protocol_file, registry, run, index = map(
        load, (protocol_path, registry_path, run_path, index_path)
    )
    protocol = protocol_file.get("protocol", {})
    check(
        protocol_file.get("training_protocol_id") == COMPARATOR_TRAINING_PROTOCOL_ID
        and protocol_file.get("protocol_digest") == COMPARATOR_TRAINING_PROTOCOL_DIGEST
        and sha256_record(protocol) == COMPARATOR_TRAINING_PROTOCOL_DIGEST,
        "RES-275 typed protocol identity or digest changed",
    )
    check(
        protocol.get("benchmark_id") == benchmark_id
        and protocol.get("benchmark_digest") == benchmark_digest
        and protocol.get("dataset_realization_id") == dataset_id
        and protocol.get("dataset_realization_digest") == dataset_digest
        and protocol.get("train_sha256") == train_sha256
        and protocol.get("validation_sha256") == validation_sha256
        and protocol.get("evaluation_id") == EVALUATION_ID
        and tuple(protocol.get("metric_ids", ()))
        == tuple(item.metric_id for item in METRIC_IDENTITIES)
        and tuple(protocol.get("seeds", ())) == seeds,
        "RES-275 protocol no longer binds the frozen RES-271 identities and seeds",
    )
    validation_isolation = protocol.get("validation_isolation", {})
    check(
        validation_isolation.get("training_loader")
        == "opens and validates canonical train.jsonl only"
        and validation_isolation.get("validation_purpose")
        == "one canonical RES-271 evaluation; no tuning or revisions",
        "RES-275 protocol validation-isolation rule changed",
    )
    check(
        run.get("format") == "PSR_RES275_STANDARDIZED_COMPARATOR_RUN_V1"
        and run.get("status") == "PASS"
        and run.get("protocol_id") == COMPARATOR_TRAINING_PROTOCOL_ID
        and run.get("benchmark_id") == benchmark_id
        and run.get("benchmark_digest") == benchmark_digest
        and run.get("dataset_realization_id") == dataset_id
        and run.get("dataset_realization_digest") == dataset_digest
        and run.get("train_sha256") == train_sha256
        and run.get("train_row_count") == 12_288
        and run.get("validation_sha256") == validation_sha256
        and run.get("validation_row_count") == 3_072
        and run.get("evaluation_id") == EVALUATION_ID,
        "RES-275 run manifest identity changed",
    )
    isolation = run.get("validation_isolation", {})
    split = run.get("fit_selection_split", {})
    check(
        isolation.get("training_loader_opened_validation") is False
        and isolation.get("fit_artifacts_sealed_before_validation_access") is True
        and isolation.get("canonical_validation_used_for_selection_or_revision") is False
        and isolation.get("evaluation_after_seal") is True
        and split.get("fit_row_count") == 9_984
        and split.get("selection_row_count") == 2_304
        and split.get("split_digest")
        == "sha256:9cccd9014e03d9f497f41dd91686307f2315ec19fe8c9b43bab908ac3e8f0b25"
        and split.get("entity_disjoint") is True
        and split.get("support_preserved") is True,
        "RES-275 fit seal or validation-isolation evidence is incomplete",
    )
    check(
        run.get("source", {}).get("worktree_status") == "clean",
        "RES-275 training source was not a clean committed checkout",
    )

    registry_comparators = registry.get("comparators", [])
    expected_models = {item.method: item for item in MODEL_SPECS}
    actual_methods = {item.get("method") for item in registry_comparators if isinstance(item, dict)}
    check(
        registry.get("format") == "PSR_STANDARDIZED_COMPARATOR_REGISTRY_V1"
        and registry.get("training_protocol_id") == COMPARATOR_TRAINING_PROTOCOL_ID
        and registry.get("benchmark_id") == benchmark_id
        and registry.get("dataset_realization_id") == dataset_id
        and registry.get("evaluation_id") == EVALUATION_ID
        and actual_methods == set(expected_models),
        "RES-275 comparator registry is incomplete or uses a different identity",
    )

    output_paths: set[str] = set()
    for item in registry_comparators:
        if not isinstance(item, dict):
            continue
        method = str(item.get("method"))
        spec = expected_models.get(method)
        check(
            spec is not None
            and item.get("model_id") == spec.model_id
            and item.get("classification") == "NEW_STANDARDIZED_COMPARATOR"
            and item.get("training_protocol_id") == COMPARATOR_TRAINING_PROTOCOL_ID
            and (root / str(item.get("model_card", ""))).is_file(),
            f"RES-275 comparator identity/classification mismatch: {method}",
        )
        if spec is None:
            continue
        runs = item.get("runs", [])
        check(
            len(runs) == len(seeds)
            and {run_item.get("seed") for run_item in runs if isinstance(run_item, dict)}
            == set(seeds),
            f"RES-275 comparator seed registry is incomplete: {method}",
        )
        for run_item in runs:
            if not isinstance(run_item, dict):
                continue
            fitted_path = str(run_item.get("fitted_instance_path", ""))
            prediction_path = str(run_item.get("prediction_path", ""))
            result_path = str(run_item.get("evaluation_result_path", ""))
            output_paths.update((fitted_path, prediction_path, result_path))
            check(
                fitted_path.startswith(f"{fitted_root}/")
                and prediction_path.startswith(f"{output_root}/")
                and result_path.startswith(f"{output_root}/"),
                f"RES-275 artifact path escaped its public result home: {method}",
            )
            fitted_sha = file_sha(fitted_path)
            prediction_sha = file_sha(prediction_path)
            result_sha = file_sha(result_path)
            expected_fitted_id = (
                f"psr:fitted-instance:{spec.slug}-seed-{run_item.get('seed')}@sha256:{fitted_sha}"
            )
            check(
                fitted_sha
                == str(run_item.get("fitted_instance_sha256", "")).removeprefix("sha256:")
                and expected_fitted_id == run_item.get("fitted_instance_id"),
                f"RES-275 fitted-instance content identity mismatch: {fitted_path}",
            )
            fitted = load(fitted_path)
            check(
                fitted.get("model_id") == item.get("model_id")
                and fitted.get("classification") == "NEW_STANDARDIZED_COMPARATOR"
                and fitted.get("training_protocol_id") == COMPARATOR_TRAINING_PROTOCOL_ID
                and fitted.get("training_sha256") == train_sha256
                and fitted.get("seed") == run_item.get("seed")
                and fitted.get("fit_row_count") == 9_984
                and fitted.get("selection_row_count") == 2_304,
                f"RES-275 fitted state is not bound to the frozen fit split: {fitted_path}",
            )
            try:
                predictions = parse_prediction_jsonl((root / prediction_path).read_bytes())
                result = json.loads((root / result_path).read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError) as error:
                errors.append(f"invalid RES-275 prediction/result pair {prediction_path}: {error}")
                continue
            result_id = f"psr:evaluation-result@{sha256_record(result)}"
            prediction = result.get("prediction_artifact", {})
            result_fitted = result.get("fitted_instance", {})
            metrics = result.get("metric_identities", [])
            expected_prediction_id = (
                f"psr:prediction-artifact:{prediction.get('artifact_id')}@"
                f"{sha256_record(prediction)}"
            )
            check(
                len(predictions) == 3_072
                and prediction_sha
                == str(run_item.get("prediction_sha256", "")).removeprefix("sha256:")
                and result_sha
                == str(run_item.get("evaluation_result_sha256", "")).removeprefix("sha256:")
                and result_id == run_item.get("evaluation_result_id")
                and result.get("model", {}).get("model_id") == item.get("model_id")
                and result.get("training_protocol", {}).get("training_protocol_id")
                == COMPARATOR_TRAINING_PROTOCOL_ID
                and result_fitted.get("fitted_instance_id") == run_item.get("fitted_instance_id")
                and result_fitted.get("content_sha256") == f"sha256:{fitted_sha}"
                and result.get("benchmark_id") == benchmark_id
                and result.get("benchmark_spec_digest") == benchmark_digest
                and result.get("dataset_realization_id") == dataset_id
                and result.get("dataset_realization_digest") == dataset_digest
                and result.get("evaluation_id") == EVALUATION_ID
                and result.get("status") == "COMPLETE"
                and {metric.get("metric_id") for metric in metrics if isinstance(metric, dict)}
                == {metric.metric_id for metric in METRIC_IDENTITIES}
                and not result.get("aggregations")
                and not result.get("stratifications")
                and not result.get("uncertainty"),
                f"RES-275 EvaluationResult binding mismatch: {result_path}",
            )
            check(
                prediction.get("content_sha256") == f"sha256:{prediction_sha}"
                and prediction.get("output_schema_identity") == PREDICTION_SCHEMA_ID
                and prediction.get("row_count") == 3_072
                and prediction.get("rights", {}).get("license_expression") == "MIT"
                and result.get("rights", {}).get("license_expression") == "MIT"
                and run_item.get("prediction_artifact_identity") == expected_prediction_id,
                f"RES-275 prediction-artifact identity mismatch: {prediction_path}",
            )
            check(
                {target.get("target") for target in result.get("targets", [])} == set(TARGETS)
                and all(
                    {metric.get("metric") for metric in target.get("metrics", [])}
                    == {identity.metric.value for identity in METRIC_IDENTITIES}
                    for target in result.get("targets", [])
                ),
                f"RES-275 target-wise metrics are incomplete: {result_path}",
            )

    immutable = registry.get("immutable_res274_reference", {})
    expert_identities = {
        "model_id": (
            "psr:model:public-native-lift-shared-temporal-gru-capacity-change@1.0.0~34d23123138f"
        ),
        "training_protocol_id": (
            "psr:training-protocol:public-native-temporal-expert@1.0.0~dc47230f3465"
        ),
        "classification": "RES-274_IMMUTABLE_PUBLIC_NATIVE_EXPERT",
        "prediction_and_result_hashes_verified": True,
    }
    check(
        all(immutable.get(key) == value for key, value in expert_identities.items())
        and immutable.get("result_paths"),
        "RES-274 immutable expert continuity record changed",
    )
    expert_hashes = run.get("immutable_res274_artifacts", {})
    for path, digest in expert_hashes.items():
        check(file_sha(str(path)) == digest, f"RES-274 expert artifact changed: {path}")

    try:
        with (root / metrics_path).open(newline="", encoding="utf-8") as file:
            metric_rows = list(csv.DictReader(file))
        check(len(metric_rows) == 66, "RES-275 per-seed target metrics table must contain 66 rows")
        check(
            all(
                row.get("rmse_kg") and row.get("mae_kg") and row.get("r2") and row.get("sre_ddof0")
                for row in metric_rows
            ),
            "RES-275 target metric table contains a missing canonical metric",
        )
    except (OSError, csv.Error) as error:
        errors.append(f"invalid RES-275 target metrics table: {error}")

    entries = index.get("entries", [])
    indexed: dict[str, str] = {
        str(entry.get("path")): str(entry.get("sha256"))
        for entry in entries
        if isinstance(entry, dict)
    }
    check(
        index.get("format") == "PSR_SHA256_INDEX_V1"
        and index.get("algorithm") == "SHA-256"
        and len(indexed) == len(entries),
        "RES-275 checksum index format or path set is invalid",
    )
    for path, digest in indexed.items():
        check(file_sha(path) == digest, f"RES-275 checksum mismatch: {path}")
    split_path = str(split.get("path", ""))
    seal_path = str(isolation.get("seal_path", ""))
    seal = load(seal_path) if seal_path else {}
    check(
        split_path in indexed
        and indexed.get(split_path) == str(split.get("sha256", "")).removeprefix("sha256:")
        and seal_path in indexed
        and indexed.get(seal_path) == str(isolation.get("seal_sha256", "")).removeprefix("sha256:")
        and seal.get("canonical_validation_accessed") is False
        and seal.get("protocol_id") == COMPARATOR_TRAINING_PROTOCOL_ID
        and len(seal.get("fitted_instances", [])) == len(MODEL_SPECS) * len(seeds)
        and all(
            item.get("training_validation_accessed") is False
            for item in seal.get("fitted_instances", [])
            if isinstance(item, dict)
        ),
        "RES-275 split/seal artifact hashes or validation-isolation fields changed",
    )
    check(
        indexed.get(run_path) == file_sha(run_path)
        and index.get("run_manifest_sha256") == f"sha256:{file_sha(run_path)}"
        and len(output_paths) == len(MODEL_SPECS) * len(seeds) * 3
        and len(indexed) == 4 + 2 + len(output_paths) + len(expert_hashes)
        and {path for path in output_paths if path} <= indexed.keys()
        and {protocol_path, registry_path, metrics_path} <= indexed.keys(),
        "RES-275 checksum index omits a required manifest, model, prediction, or result",
    )
    check(
        registry.get("target_metrics_path") == metrics_path
        and split.get("sha256")
        and isolation.get("seal_path") in indexed,
        "RES-275 protocol/registry artifact binding changed",
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
        for error in verify_res275_comparator_package():
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
    print("PASS: RES-275 comparator registry, validation isolation, and artifact hashes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
