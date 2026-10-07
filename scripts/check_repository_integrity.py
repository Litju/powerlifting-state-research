#!/usr/bin/env python3
"""Check the public registry, rights ledger, generated exports, and repository safety."""

from __future__ import annotations

import csv
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


def main() -> int:
    try:
        tracked = git_files()
        check_registry()
        rows = check_ledger(tracked)
        check_public_files(git_files("--cached", "--others", "--exclude-standard"))
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
