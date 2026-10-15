#!/usr/bin/env python3
"""Check the public registry, rights ledger, generated exports, and repository safety."""

from __future__ import annotations

import base64
import csv
import functools
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date
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
RES297_RECORD = "provenance/RES-297-rights-security-record-v1.json"
RES297_PREDICTION_RIGHTS = "provenance/RES-297-prediction-rights-resolution-v1.json"
RES297_BASELINE = "5893b6261b53faa874af6a77e9b04a47ea421777"
RES297_BASELINE_TREE = "2b116774cfa5ea538eef56a19529b29fb4cd3c2a"
RES297_BASELINE_LEDGER_SHA256 = "c7775772976ea16ddcd2c6ba6597e77ec74521b9cb7596f734d42ee706705e99"
RES297_BASELINE_PATH_COUNT = 641
RES297_GITHUB_OWNER = "Litju"
RES297_GITHUB_REPOSITORY = "powerlifting-state-research"
RES297_PREDICTIONS = {
    "ensemble.predictions.jsonl": (
        "f6fb260feac851845f584bcd96a290ec046234f78a7596221aba5453aecc006d"
    ),
    "seed-383001.predictions.jsonl": (
        "eb1bf322ba1783d0c70f59d13016421736fd6447c2f6827079f713d31332f50c"
    ),
    "seed-383002.predictions.jsonl": (
        "2373889b26646731eafc88907fada38aaf2982d0cfb464b7cfb4f728fb854e89"
    ),
    "seed-383003.predictions.jsonl": (
        "472fe8e81648672af3d93e17caaabe433026ab0d1725e384c370eb35f6d45944"
    ),
}
RES297_CHECKPOINTS = {
    383001: ("f8889305226cbac69874a2a983809e2b12adfdbfb8dd6446dbce932ac02904bb"),
    383002: ("eb6c858e20e3a0cba5a542db605494359df83c15fac54b068ed938866d1398c4"),
    383003: ("c8f6bb329ee6b9e37155d95515e071b98d0aacf720f163bbe060804a0ecdef18"),
}
RES297_OWNER_DECISION_REQUIRED = (
    "Confirm the copyright holder and grant or deny redistribution for this exact SHA-256, "
    "including the already-public Git repository and future source archives. Any grant must be "
    "a hash-bound document in provenance/rights-grants committed with a GitHub-verified "
    "signature authored by Litju."
)
ERRORS: list[str] = []


def fail(message: str) -> None:
    ERRORS.append(message)


def is_verified_owner_commit(payload: object, commit_sha: str) -> bool:
    if not isinstance(payload, dict):
        return False
    author = payload.get("author")
    committer = payload.get("committer")
    commit = payload.get("commit")
    verification = commit.get("verification") if isinstance(commit, dict) else None
    return (
        payload.get("sha") == commit_sha
        and isinstance(author, dict)
        and author.get("login") == RES297_GITHUB_OWNER
        and isinstance(committer, dict)
        and committer.get("login") == RES297_GITHUB_OWNER
        and isinstance(verification, dict)
        and verification.get("verified") is True
        and verification.get("reason") == "valid"
        and isinstance(verification.get("signature"), str)
        and bool(verification["signature"])
        and isinstance(verification.get("payload"), str)
        and bool(verification["payload"])
    )


@functools.lru_cache(maxsize=64)
def verify_owner_grant_commit(commit_sha: str, grant_path: str, grant_sha256: str) -> bool:
    """Authenticate an exact owner grant through GitHub's verified commit signature."""
    if (
        re.fullmatch(r"[0-9a-f]{40}", commit_sha) is None
        or re.fullmatch(r"provenance/rights-grants/[A-Za-z0-9][A-Za-z0-9._-]*\.json", grant_path)
        is None
        or re.fullmatch(r"[0-9a-f]{64}", grant_sha256) is None
    ):
        return False
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "powerlifting-state-research-res297-validator",
    }
    commit_url = (
        f"https://api.github.com/repos/{RES297_GITHUB_OWNER}/"
        f"{RES297_GITHUB_REPOSITORY}/commits/{commit_sha}"
    )
    contents_url = (
        f"https://api.github.com/repos/{RES297_GITHUB_OWNER}/"
        f"{RES297_GITHUB_REPOSITORY}/contents/{urllib.parse.quote(grant_path, safe='/')}"
        f"?ref={commit_sha}"
    )
    try:
        request = urllib.request.Request(commit_url, headers=headers)
        with urllib.request.urlopen(request, timeout=15) as response:
            commit_payload = json.loads(response.read())
        if not is_verified_owner_commit(commit_payload, commit_sha):
            return False
        request = urllib.request.Request(contents_url, headers=headers)
        with urllib.request.urlopen(request, timeout=15) as response:
            file_payload = json.loads(response.read())
        if (
            not isinstance(file_payload, dict)
            or file_payload.get("encoding") != "base64"
            or not isinstance(file_payload.get("content"), str)
        ):
            return False
        grant_bytes = base64.b64decode("".join(file_payload["content"].split()), validate=True)
        return hashlib.sha256(grant_bytes).hexdigest() == grant_sha256
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return False


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
        parts = Path(path).parts
        audit_realization = (
            origin == "GENERATED_PUBLIC_ARTIFACT"
            and parts[:2] == ("results", "audits")
            and len(parts) > 4
            and parts[3] == "realizations"
        )
        expected = (
            "CC-BY-4.0"
            if path.endswith(".md") or path == "LICENSE-DOCS" or audit_realization
            else "MIT"
        )
        if license_scope != expected:
            fail(f"origin ledger license does not match file scope: {path}")
    return len(rows)


def validate_res297_rights_record(
    record: object,
    expected_paths: set[str],
    origins: dict[str, dict[str, str]],
    prediction_rights: object | None = None,
    evidence_sources_valid: bool = True,
    verified_owner_commits: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    verified_owner_commits = verified_owner_commits or set()
    if not isinstance(record, dict):
        return ["RES-297 rights record must be a JSON object"]
    if record.get("format") != "PSR_RES_297_RIGHTS_SECURITY_RECORD_V1":
        errors.append("RES-297 rights record format is invalid")
    if record.get("baseline_commit") != RES297_BASELINE:
        errors.append("RES-297 rights record baseline changed")
    baseline_inventory = record.get("baseline_inventory")
    if not isinstance(baseline_inventory, dict) or (
        record.get("baseline_tree") != RES297_BASELINE_TREE
        or baseline_inventory.get("path") != "provenance/PUBLIC_FILE_ORIGINS.csv"
        or baseline_inventory.get("path_count") != RES297_BASELINE_PATH_COUNT
        or baseline_inventory.get("git_tree_paths") != RES297_BASELINE_PATH_COUNT
        or baseline_inventory.get("sha256") != RES297_BASELINE_LEDGER_SHA256
    ):
        errors.append("RES-297 immutable baseline inventory identity changed")
    recorded_on = record.get("recorded_on")
    try:
        record_date = date.fromisoformat(str(recorded_on))
    except ValueError:
        record_date = None
        errors.append("RES-297 record date is missing or invalid")

    raw_artifacts = record.get("hash_decisions")
    if not isinstance(raw_artifacts, list) or any(
        not isinstance(item, dict) for item in raw_artifacts
    ):
        errors.append("RES-297 per-hash decisions must be an array of objects")
        raw_artifacts = []
    artifacts = [item for item in raw_artifacts if isinstance(item, dict)]
    raw_families = record.get("rights_families")
    families = (
        [item for item in raw_families if isinstance(item, dict)]
        if isinstance(raw_families, list)
        else []
    )
    family_map = {
        item["family_id"]: item for item in families if isinstance(item.get("family_id"), str)
    }
    if len(family_map) != len(families) or not families:
        errors.append("RES-297 rights families must have unique identifiers")
    allowed_dispositions = {"CLEARED", "EXCLUDED", "BLOCKED", "UNRESOLVED"}
    for family in families:
        if family.get("rights_disposition") not in allowed_dispositions | {"PARTIAL"}:
            errors.append("RES-297 rights family has an invalid disposition")
    paths = [item.get("path") for item in artifacts]
    string_paths = [path for path in paths if isinstance(path, str)]
    if len(paths) != len(set(string_paths)) or set(string_paths) != expected_paths:
        errors.append("RES-297 per-hash decisions do not exactly cover the baseline inventory")
    source_hashes = {
        source.get("path"): source.get("sha256")
        for source in record.get("rights_source_hashes", [])
        if isinstance(source, dict)
    }

    def validate_authorization(
        authorization: object, item: dict, family: dict, origin: dict | None
    ) -> bool:
        if not isinstance(authorization, dict):
            return False
        raw_evidence = authorization.get("evidence")
        evidence = (
            raw_evidence
            if isinstance(raw_evidence, list)
            else [raw_evidence]
            if isinstance(raw_evidence, dict)
            else []
        )
        if not evidence or any(
            not isinstance(item, dict)
            or not isinstance(item.get("role"), str)
            or not item["role"].strip()
            for item in evidence
        ):
            return False
        evidence_map = {item.get("path"): item.get("sha256") for item in evidence}
        if len(evidence_map) != len(evidence):
            return False
        evidence_paths = set(evidence_map)
        try:
            valid_from = date.fromisoformat(str(authorization.get("valid_from")))
            valid_until_value = authorization.get("valid_until")
            valid_until = (
                date.fromisoformat(str(valid_until_value))
                if valid_until_value is not None
                else None
            )
        except ValueError:
            return False
        if (
            record_date is None
            or authorization.get("artifact_path") != item.get("path")
            or authorization.get("artifact_sha256") != item.get("candidate_sha256")
            or authorization.get("owner_identity") != family.get("rights_owner")
            or authorization.get("license_expression")
            != item.get("rights_license_expression", item.get("license_expression"))
            or not isinstance(authorization.get("authorization_scope"), str)
            or not authorization["authorization_scope"].strip()
            or not isinstance(authorization.get("redistribution_conditions"), str)
            or not authorization["redistribution_conditions"].strip()
            or valid_from > record_date
            or (valid_until is not None and valid_until < record_date)
            or any(
                not isinstance(path, str)
                or Path(path).is_absolute()
                or ".." in Path(path).parts
                or source_hashes.get(path) != digest
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                for path, digest in evidence_map.items()
            )
        ):
            return False
        if (
            origin is not None
            and authorization.get("authority_type") != "OWNER_ATTESTATION"
            and authorization.get("license_expression") != origin.get("license_expression")
        ):
            return False
        authority = authorization.get("authority_type")
        if authority == "PUBLISHED_LICENSE":
            if authorization.get("owner_identity") != "Powerlifting State Research contributors":
                return False
            expected_evidence = {
                "MIT": {"LICENSE"},
                "CC-BY-4.0": {"LICENSE", "LICENSE-DOCS"}
                if str(item.get("path", "")).endswith(".md") or item.get("path") == "LICENSE-DOCS"
                else None,
            }.get(str(item.get("license_expression")))
            return expected_evidence is not None and evidence_paths == expected_evidence
        if authority == "DATASET_RIGHTS_MANIFEST":
            evidence_path = next(iter(evidence_paths)) if len(evidence_paths) == 1 else ""
            return (
                item.get("license_expression") == "CC-BY-4.0"
                and str(evidence_path).endswith("/manifest.json")
                and Path(str(item.get("path", ""))).parent == Path(evidence_path).parent
            )
        if authority == "OWNER_ATTESTATION":
            # The owner document must be independently surfaced as a hashed source record.
            owner_attestation = authorization.get("owner_attestation")
            evidence_path = next(iter(evidence_paths)) if len(evidence_paths) == 1 else ""
            try:
                decision_date = (
                    date.fromisoformat(str(owner_attestation.get("decision_date")))
                    if isinstance(owner_attestation, dict)
                    else None
                )
            except ValueError:
                decision_date = None
            scope = str(authorization.get("authorization_scope", "")).lower()
            public_prediction = str(item.get("path", "")) in {
                "results/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/"
                f"public-native-temporal-expert/{name}"
                for name in RES297_PREDICTIONS
            }
            return (
                evidence_path.startswith("provenance/rights-grants/")
                and evidence_path != item.get("path")
                and isinstance(owner_attestation, dict)
                and bool(owner_attestation.get("decision_id"))
                and owner_attestation.get("rightsholder_identity")
                == authorization.get("owner_identity")
                and owner_attestation.get("authorized_signer_login") == RES297_GITHUB_OWNER
                and bool(owner_attestation.get("authority_basis"))
                and isinstance(owner_attestation.get("verified_commit"), str)
                and owner_attestation.get("verified_commit") in verified_owner_commits
                and decision_date is not None
                and record_date is not None
                and decision_date <= record_date
                and (
                    not public_prediction
                    or ("public repository" in scope and "source archive" in scope)
                )
                and (
                    not str(item.get("path", "")).startswith("psr:checkpoint:")
                    or ("checkpoint" in scope and "public" in scope)
                )
                and (
                    item.get("release_inclusion") is not True
                    or "release bundle" in scope
                    or "release archive" in scope
                )
            )
        return False

    for item in artifacts:
        path = item.get("path")
        if not isinstance(path, str):
            errors.append("RES-297 hash decision has no path")
            continue
        for field in ("sha256", "candidate_sha256"):
            if re.fullmatch(r"[0-9a-f]{64}", str(item.get(field, ""))) is None:
                errors.append(f"RES-297 hash decision has an invalid {field}: {path}")
        if item.get("rights_disposition") not in allowed_dispositions:
            errors.append(f"RES-297 hash decision has an invalid disposition: {path}")
        if item.get("release_inclusion") is True and item.get("rights_disposition") != "CLEARED":
            errors.append(f"unresolved or excluded bytes are authorized for release: {path}")
        family = family_map.get(item.get("rights_family"))
        if not isinstance(family, dict):
            errors.append(f"RES-297 hash decision lacks matching family rights evidence: {path}")
        elif item.get("rights_disposition") == "CLEARED":
            if family.get("rights_disposition") not in {"CLEARED", "PARTIAL"}:
                errors.append(f"cleared hash decision has a non-cleared rights family: {path}")
            if not validate_authorization(
                item.get("rights_authorization"), item, family, origins.get(path)
            ):
                errors.append(f"cleared hash decision lacks a valid hash-bound owner grant: {path}")
        elif family.get("rights_disposition") not in {
            item.get("rights_disposition"),
            "PARTIAL",
        }:
            errors.append(f"RES-297 hash decision lacks matching family rights evidence: {path}")
        origin = origins.get(path)
        if origin is None or any(
            item.get(field) != origin.get(field)
            for field in ("origin_class", "license_expression", "owner")
        ):
            errors.append(f"RES-297 hash decision differs from the current origin ledger: {path}")

    expected_prediction_paths = {
        "results/benchmarks/iid_latent_capacity_change_with_transient_expression_forecasting/"
        f"public-native-temporal-expert/{name}": digest
        for name, digest in RES297_PREDICTIONS.items()
    }
    raw_predictions = record.get("prediction_artifacts")
    predictions = (
        [item for item in raw_predictions if isinstance(item, dict)]
        if isinstance(raw_predictions, list)
        else []
    )
    if not isinstance(prediction_rights, dict) or prediction_rights.get("format") != (
        "PSR_RES_297_PREDICTION_RIGHTS_RESOLUTION_V1"
    ):
        errors.append("RES-297 versioned prediction-rights resolution is missing or invalid")
        prediction_rights = {}
    resolution_rows = prediction_rights.get("artifacts", [])
    resolution_map = (
        {item.get("path"): item for item in resolution_rows if isinstance(item, dict)}
        if isinstance(resolution_rows, list)
        else {}
    )
    prediction_paths = [item.get("path") for item in predictions]
    if len(prediction_paths) != len(
        [path for path in prediction_paths if isinstance(path, str)]
    ) or set(path for path in prediction_paths if isinstance(path, str)) != set(
        expected_prediction_paths
    ):
        errors.append("RES-297 must disposition all four tracked prediction artifacts")
    by_path = {item["path"]: item for item in artifacts if isinstance(item.get("path"), str)}
    for item in predictions:
        path = item.get("path")
        digest = expected_prediction_paths.get(path) if isinstance(path, str) else None
        decision = by_path.get(path)
        rights = item.get("prediction_rights")
        resolution = resolution_map.get(path)
        if item.get("release_inclusion") is True and item.get("rights_disposition") != "CLEARED":
            errors.append(f"unresolved or excluded bytes are authorized for release: {path}")
        if (
            digest is None
            or item.get("sha256") != digest
            or item.get("already_public_git_tracked") is not True
            or not isinstance(resolution, dict)
            or resolution.get("sha256") != digest
            or resolution.get("already_public_git_tracked") is not True
            or resolution.get("public_repository_disposition") != "ALREADY_PUBLIC_GIT_TRACKED"
            or resolution.get("rights_disposition") != item.get("rights_disposition")
            or resolution.get("release_inclusion") != item.get("release_inclusion")
            or not isinstance(decision, dict)
            or resolution.get("rights_license_expression")
            != decision.get("rights_license_expression")
            or not isinstance(rights, dict)
            or rights.get("license_expression") != "NOASSERTION"
            or rights.get("copyright_holder") != "Not asserted"
            or decision.get("sha256") != digest
            or decision.get("rights_disposition") != item.get("rights_disposition")
            or decision.get("release_inclusion") != item.get("release_inclusion")
        ):
            errors.append("RES-297 prediction rights conflict or owner resolution is inconsistent")
        if isinstance(resolution, dict) and item.get("rights_disposition") == "CLEARED":
            if not validate_authorization(
                resolution.get("rights_authorization"),
                {
                    **item,
                    "candidate_sha256": digest,
                    "rights_license_expression": resolution.get("rights_license_expression"),
                },
                family_map.get("temporal_expert_prediction_bytes", {}),
                origins.get(path),
            ):
                errors.append(f"cleared prediction lacks a valid per-hash owner grant: {path}")
        elif isinstance(resolution, dict) and resolution.get("rights_authorization") is not None:
            errors.append(f"unresolved prediction contains an unauthorized grant: {path}")
        if (
            isinstance(resolution, dict)
            and resolution.get("owner_decision_required") != RES297_OWNER_DECISION_REQUIRED
            and item.get("rights_disposition") != "CLEARED"
        ):
            errors.append(
                f"unresolved prediction lacks the precise owner decision required: {path}"
            )
    if set(resolution_map) != set(expected_prediction_paths):
        errors.append(
            "RES-297 prediction-rights sidecar does not cover exactly four prediction hashes"
        )
    expected_resolution_status = (
        "CLEARED"
        if resolution_map
        and all(item.get("rights_disposition") == "CLEARED" for item in resolution_map.values())
        else "UNRESOLVED"
    )
    if prediction_rights.get("rights_status") != expected_resolution_status:
        errors.append("RES-297 prediction-rights sidecar status does not match per-hash decisions")
    trace = prediction_rights.get("source_trace", {})
    prediction_provenance = record.get("prediction_generation_and_provenance", {})
    first_prediction = predictions[0] if predictions else {}
    model_provenance = (
        first_prediction.get("model_provenance", {}) if isinstance(first_prediction, dict) else {}
    )
    if (
        not isinstance(trace, dict)
        or trace.get("generation_receipt") != prediction_provenance.get("generation_receipt")
        or trace.get("dataset_realization_id")
        != prediction_provenance.get("dataset_realization_id")
        or trace.get("dataset_rights") != prediction_provenance.get("dataset_rights")
        or trace.get("model_id") != prediction_provenance.get("model_id")
        or trace.get("training_protocol_id") != prediction_provenance.get("training_protocol_id")
        or trace.get("source_code_and_metadata") != model_provenance.get("source_code_and_metadata")
    ):
        errors.append(
            "RES-297 prediction-rights sidecar provenance trace is incomplete or inconsistent"
        )

    raw_checkpoints = record.get("checkpoint_dispositions")
    checkpoints = (
        [item for item in raw_checkpoints if isinstance(item, dict)]
        if isinstance(raw_checkpoints, list)
        else []
    )
    checkpoint_seeds = [item.get("seed") for item in checkpoints]
    valid_seeds = {seed for seed in checkpoint_seeds if isinstance(seed, int)}
    if len(valid_seeds) != len(checkpoint_seeds) or valid_seeds != set(RES297_CHECKPOINTS):
        errors.append("RES-297 must disposition all three checkpoint hashes")
    checkpoint_family = family_map.get("temporal_expert_checkpoint_weights", {})
    checkpoint_dispositions: list[str] = []
    checkpoint_release_states: list[str] = []
    for item in checkpoints:
        seed = item.get("seed")
        disposition = item.get("rights_disposition")
        released = item.get("weights_release_status")
        checkpoint_dispositions.append(str(disposition))
        checkpoint_release_states.append(str(released))
        if disposition == "CLEARED":
            auth_item = {
                "path": item.get("checkpoint_id"),
                "candidate_sha256": item.get("expected_sha256"),
                "rights_license_expression": item.get("rights_license_expression"),
            }
            if checkpoint_family.get("rights_disposition") not in {
                "CLEARED",
                "PARTIAL",
            } or not validate_authorization(
                item.get("rights_authorization"), auth_item, checkpoint_family, None
            ):
                errors.append(f"cleared checkpoint lacks a valid per-hash owner grant: {seed}")
        elif item.get("rights_authorization") is not None:
            errors.append(f"unresolved checkpoint contains an unauthorized grant: {seed}")
        if (
            not isinstance(seed, int)
            or seed not in RES297_CHECKPOINTS
            or item.get("expected_sha256") != RES297_CHECKPOINTS.get(seed)
            or (item.get("tracked_in_git") is not True and item.get("tracked_in_git") is not False)
            or (
                item.get("externally_available") is not True
                and item.get("externally_available") is not False
            )
            or item.get("bytes_available")
            != (item.get("tracked_in_git") or item.get("externally_available"))
            or (
                item.get("bytes_hash_independently_verified") is not True
                and item.get("bytes_hash_independently_verified") is not False
            )
            or (item.get("bytes_available") and not item.get("bytes_hash_independently_verified"))
            or item.get("redistribution_authorized") != disposition
            or disposition not in {"CLEARED", "UNRESOLVED"}
            or item.get("weights_release_status") not in {"NOT_RELEASED", "RELEASED"}
            or (item.get("weights_release_status") == "RELEASED")
            != (item.get("release_inclusion") is True)
            or (item.get("release_inclusion") is True and disposition != "CLEARED")
            or (
                item.get("release_inclusion") is True
                and not (
                    item.get("bytes_available") is True
                    and item.get("bytes_hash_independently_verified") is True
                )
            )
            or (item.get("tracked_in_git") is True and item.get("release_inclusion") is not True)
            or item.get("byte_count") != 486773
            or not isinstance(item.get("verification_receipt"), dict)
            or item["verification_receipt"].get("status") != "PASS"
            or item["verification_receipt"].get("source_bundle_sha256")
            != "fa31764220dbca936275b07965e7b4b4adb146251fc38db063dc5e88de8eaec4"
            or item["verification_receipt"].get("public_source_inventory")
            != {
                "path": "results/manifests/public-native-temporal-expert-source-inventory.json",
                "sha256": "416a7cfb2f0a7bef3a6865a3649f49859f1108db1f98aafc09529f447855e616",
            }
            or not any(
                evidence.get("seed") == seed
                and evidence.get("sha256") == item.get("expected_sha256")
                and evidence.get("byte_count") == 486773
                for evidence in item["verification_receipt"].get("checkpoint_hashes", [])
                if isinstance(evidence, dict)
            )
        ):
            errors.append(
                f"RES-297 checkpoint availability, integrity, or rights are inconsistent: {seed}"
            )

    expected_checkpoint_rights = (
        "CLEARED"
        if checkpoint_dispositions and all(item == "CLEARED" for item in checkpoint_dispositions)
        else "UNRESOLVED"
        if checkpoint_dispositions and all(item == "UNRESOLVED" for item in checkpoint_dispositions)
        else "PARTIAL"
    )
    expected_checkpoint_release = (
        "RELEASED"
        if checkpoint_release_states
        and all(item == "RELEASED" for item in checkpoint_release_states)
        else "NOT_RELEASED"
        if checkpoint_release_states
        and all(item == "NOT_RELEASED" for item in checkpoint_release_states)
        else "PARTIAL"
    )
    if checkpoint_family.get("rights_disposition") != expected_checkpoint_rights:
        errors.append("RES-297 checkpoint family status does not match per-hash rights")

    checkpoint_search = record.get("checkpoint_bytes_search")
    if not isinstance(checkpoint_search, dict) or (
        checkpoint_search.get("externally_available")
        != all(item.get("externally_available") is True for item in checkpoints)
        or checkpoint_search.get("tracked_in_git")
        != all(item.get("tracked_in_git") is True for item in checkpoints)
        or checkpoint_search.get("actual_hashes_independently_verified")
        != all(item.get("bytes_hash_independently_verified") is True for item in checkpoints)
        or checkpoint_search.get("redistribution_authorized") != expected_checkpoint_rights
        or checkpoint_search.get("weights_release_status") != expected_checkpoint_release
        or checkpoint_search.get("release_inclusion")
        != any(item.get("release_inclusion") is True for item in checkpoints)
        or checkpoint_search.get("source_bundle_sha256")
        != "fa31764220dbca936275b07965e7b4b4adb146251fc38db063dc5e88de8eaec4"
        or checkpoint_search.get("supporting_receipt")
        != {
            "status": "PASS",
            "public_res274_verification_receipt": {
                "path": "results/manifests/public-native-temporal-expert-verification-receipt.json",
                "sha256": "fd11790ea0f4b461f38d6cb96f6fb925ec9917128b53a54e0a6f053197771273",
            },
            "public_source_inventory": {
                "path": "results/manifests/public-native-temporal-expert-source-inventory.json",
                "sha256": "416a7cfb2f0a7bef3a6865a3649f49859f1108db1f98aafc09529f447855e616",
            },
            "independent_hash_verification_recorded_in": (
                "Linear RES-297 F7 verification update, 2026-10-15"
            ),
            "source_bundle_sha256": (
                "fa31764220dbca936275b07965e7b4b4adb146251fc38db063dc5e88de8eaec4"
            ),
            "source_bundle_byte_count": 1885383,
            "checkpoint_hashes": [
                {"seed": seed, "sha256": digest, "byte_count": 486773}
                for seed, digest in sorted(RES297_CHECKPOINTS.items())
            ],
            "private_storage_identifiers_or_paths_disclosed": False,
        }
    ):
        errors.append(
            "RES-297 checkpoint evidence does not separate availability, integrity, and rights"
        )

    counts = record.get("summary")
    if isinstance(counts, dict):
        actual = {
            key: sum(item.get("rights_disposition") == key for item in artifacts)
            for key in ("CLEARED", "EXCLUDED", "BLOCKED", "UNRESOLVED")
        }
        if any(
            counts.get(key, 0) != actual.get(key, 0)
            for key in ("CLEARED", "EXCLUDED", "BLOCKED", "UNRESOLVED")
        ):
            errors.append("RES-297 rights summary does not match per-hash decisions")
    candidate_inventory = record.get("candidate_inventory")
    additions = (
        [
            item
            for item in candidate_inventory.get("new_candidate_files", [])
            if isinstance(item, dict)
        ]
        if isinstance(candidate_inventory, dict)
        and isinstance(candidate_inventory.get("new_candidate_files"), list)
        else []
    )
    addition_paths = [item.get("path") for item in additions]
    if (
        not isinstance(candidate_inventory, dict)
        or len(addition_paths) != len({path for path in addition_paths if isinstance(path, str)})
        or candidate_inventory.get("path_count") != len(expected_paths) + len(additions)
    ):
        errors.append("RES-297 candidate inventory is incomplete or contains duplicate additions")
    for item in additions:
        path = item.get("path")
        family = family_map.get(item.get("rights_family"))
        origin = origins.get(path) if isinstance(path, str) else None
        if (
            not isinstance(path, str)
            or item.get("sha256") is None
            or re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))) is None
            or item.get("rights_disposition") != "CLEARED"
            or item.get("release_inclusion") is not True
            or not isinstance(family, dict)
            or family.get("rights_disposition") != "CLEARED"
            or origin is None
            or any(
                item.get(field) != origin.get(field)
                for field in ("origin_class", "license_expression", "owner")
            )
            or not validate_authorization(
                item.get("rights_authorization"),
                {**item, "candidate_sha256": item.get("sha256")},
                family,
                origin,
            )
        ):
            errors.append(f"new candidate file lacks hash-bound release authority: {path}")
    record_rights = record.get("record_rights")
    if not isinstance(record_rights, dict) or (
        record_rights.get("copyright_holder") != "Powerlifting State Research contributors"
        or record_rights.get("license_expression") != "MIT"
        or record_rights.get("evidence")
        != {
            "path": "LICENSE",
            "sha256": source_hashes.get("LICENSE"),
        }
        or record_rights.get("valid_from") != "2026-10-06"
        or not record_rights.get("redistribution_conditions")
    ):
        errors.append("RES-297 record rights lack hash-bound published-license authority")
    computed_gate = derive_res297_release_gate(
        artifacts,
        prediction_rights,
        additions,
        record_rights,
        checkpoints,
        errors,
        evidence_sources_valid,
    )
    if record.get("candidate_release_gate") != computed_gate:
        errors.append("RES-297 candidate release gate does not match validated rights evidence")
    release_policy = record.get("release_inclusion_policy", {})
    if (
        not isinstance(release_policy, dict)
        or release_policy.get("candidate_release_gate") != computed_gate
    ):
        errors.append("RES-297 release policy gate differs from validated rights evidence")
    return errors


def baseline_paths_from_ledger_prefix(data: bytes) -> set[str]:
    """Recover the 641-path baseline from its hash-pinned ledger prefix in shallow CI."""
    lines = data.splitlines(keepends=True)
    prefix = b"".join(lines[: RES297_BASELINE_PATH_COUNT + 1])
    if hashlib.sha256(prefix).hexdigest() != RES297_BASELINE_LEDGER_SHA256:
        raise ValueError("baseline origin-ledger prefix SHA-256 does not match")
    rows = list(csv.DictReader(io.StringIO(prefix.decode("utf-8"))))
    paths = {row.get("path", "") for row in rows}
    if len(rows) != RES297_BASELINE_PATH_COUNT or len(paths) != RES297_BASELINE_PATH_COUNT:
        raise ValueError("baseline origin-ledger prefix is incomplete or duplicated")
    return paths


def derive_res297_release_gate(
    artifacts: list[dict],
    prediction_rights: object,
    additions: list[dict] | None = None,
    record_rights: object = None,
    checkpoints: list[dict] | None = None,
    validation_errors: list[str] | None = None,
    evidence_sources_valid: bool = True,
) -> str:
    """The public-repository gate fails closed for any tracked artifact without validated rights."""
    if validation_errors or not evidence_sources_valid or not isinstance(prediction_rights, dict):
        return "NO-GO"
    rows = prediction_rights.get("artifacts", [])
    if not isinstance(rows, list):
        return "NO-GO"
    tracked_rows = [*artifacts, *(row for row in rows if isinstance(row, dict)), *(additions or [])]
    if (
        not isinstance(record_rights, dict)
        or record_rights.get("license_expression") != "MIT"
        or any(item.get("rights_disposition") != "CLEARED" for item in tracked_rows)
        or any(
            (item.get("tracked_in_git") is True or item.get("release_inclusion") is True)
            and item.get("rights_disposition") != "CLEARED"
            for item in (checkpoints or [])
        )
    ):
        return "NO-GO"
    return "GO"


def check_res297_rights_record(tracked: set[str]) -> None:
    evidence_error_start = len(ERRORS)
    verified_owner_commits: set[str] = set()
    try:
        record = json.loads((ROOT / RES297_RECORD).read_text(encoding="utf-8"))
        prediction_rights = json.loads(
            (ROOT / RES297_PREDICTION_RIGHTS).read_text(encoding="utf-8")
        )
        with (ROOT / "provenance/PUBLIC_FILE_ORIGINS.csv").open(
            newline="", encoding="utf-8"
        ) as file:
            origins = {row["path"]: row for row in csv.DictReader(file)}
    except (OSError, KeyError, json.JSONDecodeError) as error:
        fail(f"RES-297 rights record is missing or invalid: {error}")
        return
    try:
        prefix_paths = baseline_paths_from_ledger_prefix(
            (ROOT / "provenance/PUBLIC_FILE_ORIGINS.csv").read_bytes()
        )
        baseline_ref = subprocess.run(
            ["git", "-C", str(ROOT), "cat-file", "-e", f"{RES297_BASELINE}^{{commit}}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if baseline_ref.returncode:
            baseline_paths = prefix_paths
        else:
            baseline_paths = {
                line.decode("utf-8")
                for line in subprocess.check_output(
                    [
                        "git",
                        "-C",
                        str(ROOT),
                        "ls-tree",
                        "-r",
                        "--name-only",
                        "-z",
                        RES297_BASELINE,
                    ]
                ).split(b"\0")
                if line
            }
            if baseline_paths != prefix_paths:
                fail("RES-297 baseline tree does not match the hash-pinned origin-ledger prefix")
        expected_additions = tracked - baseline_paths - {RES297_RECORD}
        raw_additions = record.get("candidate_inventory", {}).get("new_candidate_files", [])
        recorded_additions = {item.get("path") for item in raw_additions if isinstance(item, dict)}
        if recorded_additions != expected_additions:
            fail("RES-297 candidate inventory does not reconcile new Git-tracked files")
        source_hashes = {
            item.get("path"): item.get("sha256")
            for item in record.get("rights_source_hashes", [])
            if isinstance(item, dict)
        }
        for path, digest in source_hashes.items():
            if not isinstance(path, str) or not isinstance(digest, str):
                fail("RES-297 rights source hash entry is incomplete")
                continue
            try:
                actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            except OSError:
                actual = ""
            if actual != digest:
                fail(f"RES-297 rights evidence source hash mismatch: {path}")

        def verify_authorization_source(item: dict) -> None:
            authorization = item.get("rights_authorization")
            if not isinstance(authorization, dict):
                return
            item_path = item.get("path", item.get("checkpoint_id"))
            item_sha = item.get("candidate_sha256", item.get("sha256", item.get("expected_sha256")))
            raw_evidence = authorization.get("evidence")
            evidence = (
                raw_evidence
                if isinstance(raw_evidence, list)
                else [raw_evidence]
                if isinstance(raw_evidence, dict)
                else []
            )
            for source in evidence:
                if not isinstance(source, dict):
                    continue
                source_path = source.get("path")
                if not isinstance(source_path, str):
                    continue
                try:
                    payload = (ROOT / source_path).read_bytes()
                except OSError:
                    fail(f"RES-297 owner authority evidence is unavailable: {source_path}")
                    continue
                if authorization.get("authority_type") == "PUBLISHED_LICENSE":
                    text = payload.decode("utf-8", "replace")
                    expected = authorization.get("license_expression")
                    role = source.get("role")
                    valid = False
                    if expected == "MIT":
                        valid = (
                            source_path == "LICENSE"
                            and "MIT License" in text
                            and "Copyright (c) 2026 Powerlifting State Research contributors"
                            in text
                            and "Permission is hereby granted" in text
                            and role == "license_and_rightsholder"
                        )
                    elif expected == "CC-BY-4.0" and role == "rightsholder_identity":
                        valid = (
                            source_path == "LICENSE"
                            and "Copyright (c) 2026 Powerlifting State Research contributors"
                            in text
                        )
                    elif expected == "CC-BY-4.0" and role == "license_and_scope":
                        valid = (
                            source_path == "LICENSE-DOCS"
                            and "Project-authored Markdown documentation" in text
                            and "CC-BY-4.0" in text
                        )
                    if not valid:
                        fail(f"RES-297 published license does not support its grant: {source_path}")
                elif authorization.get("authority_type") == "DATASET_RIGHTS_MANIFEST":
                    try:
                        manifest = json.loads(payload)
                    except json.JSONDecodeError:
                        manifest = {}
                    rights = manifest.get("rights", {}) if isinstance(manifest, dict) else {}
                    if (
                        rights.get("copyright_holder") != authorization.get("owner_identity")
                        or rights.get("license_expression")
                        != authorization.get("license_expression")
                        or rights.get("redistribution_status")
                        != authorization.get("redistribution_conditions")
                    ):
                        fail(
                            f"RES-297 dataset rights manifest contradicts its grant: {source_path}"
                        )
                    if item.get("path") != source_path:
                        artifact_hashes = manifest.get("artifact_hashes", [])
                        stem = Path(str(item.get("path", ""))).stem
                        matching = [
                            entry
                            for entry in artifact_hashes
                            if isinstance(entry, dict) and entry.get("artifact_id") == stem
                        ]
                        if len(matching) != 1 or matching[0].get("sha256") != item.get(
                            "candidate_sha256", item.get("sha256")
                        ):
                            fail(
                                f"RES-297 dataset manifest does not bind this artifact: "
                                f"{item.get('path')}"
                            )
                elif authorization.get("authority_type") == "OWNER_ATTESTATION":
                    try:
                        grant = json.loads(payload)
                    except json.JSONDecodeError:
                        grant = {}
                    attestation = authorization.get("owner_attestation")
                    if (
                        not isinstance(grant, dict)
                        or grant.get("format") != "PSR_OWNER_RIGHTS_GRANT_V1"
                        or not isinstance(attestation, dict)
                        or grant.get("decision_id") != attestation.get("decision_id")
                        or grant.get("rightsholder_identity")
                        != attestation.get("rightsholder_identity")
                        or grant.get("authorized_signer_login")
                        != attestation.get("authorized_signer_login")
                        or grant.get("authority_basis") != attestation.get("authority_basis")
                        or grant.get("decision_date") != attestation.get("decision_date")
                        or grant.get("artifact_path") != item_path
                        or grant.get("artifact_sha256") != authorization.get("artifact_sha256")
                        or grant.get("artifact_sha256") != item_sha
                        or grant.get("owner_identity") != authorization.get("owner_identity")
                        or grant.get("license_expression")
                        != authorization.get("license_expression")
                        or grant.get("authorization_scope")
                        != authorization.get("authorization_scope")
                        or grant.get("valid_from") != authorization.get("valid_from")
                        or grant.get("valid_until") != authorization.get("valid_until")
                        or grant.get("redistribution_conditions")
                        != authorization.get("redistribution_conditions")
                    ):
                        fail(f"RES-297 owner grant document contradicts its binding: {source_path}")
                    elif isinstance(attestation, dict) and verify_owner_grant_commit(
                        str(attestation.get("verified_commit", "")),
                        source_path,
                        str(source.get("sha256", "")),
                    ):
                        verified_owner_commits.add(str(attestation["verified_commit"]))
                    else:
                        fail(
                            "RES-297 owner grant lacks an authenticated owner signature: "
                            f"{source_path}"
                        )

        for item in record.get("hash_decisions", []):
            if isinstance(item, dict):
                verify_authorization_source(item)
        for item in raw_additions:
            if isinstance(item, dict):
                verify_authorization_source(item)
        for item in record.get("checkpoint_dispositions", []):
            if isinstance(item, dict):
                verify_authorization_source(item)
        for item in prediction_rights.get("artifacts", []):
            if isinstance(item, dict):
                verify_authorization_source(item)
                prediction_path = item.get("path")
                result_ref = item.get("evaluation_result")
                if not isinstance(prediction_path, str) or not isinstance(result_ref, dict):
                    fail("RES-297 prediction sidecar lacks prediction or EvaluationResult identity")
                    continue
                prediction_sha = hashlib.sha256((ROOT / prediction_path).read_bytes()).hexdigest()
                result_path = result_ref.get("path")
                result_sha = (
                    hashlib.sha256((ROOT / result_path).read_bytes()).hexdigest()
                    if isinstance(result_path, str)
                    else ""
                )
                try:
                    evaluation = json.loads((ROOT / str(result_path)).read_text(encoding="utf-8"))
                    evaluation_result = evaluation["result"]
                    prediction_rights_claim = evaluation_result["prediction_artifact"]["rights"]
                    evaluation_rights_claim = evaluation_result["rights"]
                except (OSError, KeyError, TypeError, json.JSONDecodeError):
                    evaluation_result = {}
                    prediction_rights_claim = {}
                    evaluation_rights_claim = {}
                if (
                    prediction_sha != item.get("sha256")
                    or result_sha != result_ref.get("sha256")
                    or prediction_rights_claim.get("license_expression") != "NOASSERTION"
                    or prediction_rights_claim.get("copyright_holder") != "Not asserted"
                    or evaluation_rights_claim.get("license_expression") != "MIT"
                ):
                    fail(
                        "RES-297 prediction/EvaluationResult rights source changed: "
                        f"{prediction_path}"
                    )
        source_inventory = json.loads(
            (
                ROOT / "results/manifests/public-native-temporal-expert-source-inventory.json"
            ).read_text(encoding="utf-8")
        )
        source_entries = {
            entry.get("path"): entry
            for entry in source_inventory.get("entries", [])
            if isinstance(entry, dict)
        }
        gate_receipt = json.loads(
            (
                ROOT / "results/manifests/public-native-temporal-expert-verification-receipt.json"
            ).read_text(encoding="utf-8")
        )
        if gate_receipt.get("status") != "PASS" or gate_receipt.get("bundle_sha256") != (
            "fa31764220dbca936275b07965e7b4b4adb146251fc38db063dc5e88de8eaec4"
        ):
            fail("RES-297 public RES-274 verification receipt is inconsistent")
        for seed, expected in RES297_CHECKPOINTS.items():
            entry = source_entries.get(f"seed-{seed}/checkpoint.pt", {})
            if entry.get("sha256") != expected or entry.get("size_bytes") != 486773:
                fail(
                    "RES-297 checkpoint evidence differs from the public source inventory: "
                    f"seed {seed}"
                )
        current_hashes = {
            item.get("path"): hashlib.sha256(
                (ROOT / str(item.get("path"))).read_bytes()
            ).hexdigest()
            for item in raw_additions
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
        if any(
            item.get("sha256") != current_hashes.get(item.get("path")) for item in raw_additions
        ):
            fail("RES-297 candidate addition SHA-256 does not match current bytes")
    except (
        OSError,
        subprocess.CalledProcessError,
        TypeError,
        AttributeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        fail(f"RES-297 candidate inventory could not be checked: {error}")
        baseline_paths = set()
    expected_paths = baseline_paths
    for error in validate_res297_rights_record(
        record,
        expected_paths,
        origins,
        prediction_rights,
        evidence_sources_valid=len(ERRORS) == evidence_error_start,
        verified_owner_commits=verified_owner_commits,
    ):
        fail(error)


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
    validation_isolation = dict(protocol.get("validation_isolation", []))
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
        tracked = git_files("--cached", "--others", "--exclude-standard")
        check_registry()
        rows = check_ledger(tracked)
        check_public_files(tracked)
        check_res297_rights_record(tracked)
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
