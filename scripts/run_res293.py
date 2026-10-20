"""Qualification, freeze, one-shot execution, and analysis for RES-293 v0.2."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
import scipy
import torch

from powerlifting_state_research.contracts.serialization import canonical_json_bytes
from powerlifting_state_research.studies import res293_representation_information as study

ROOT = Path(__file__).resolve().parents[1]
STUDY_HOME = ROOT / "studies/res293_representation_learner_information"
QUALIFICATION = STUDY_HOME / "qualification"
RESULTS = ROOT / "results/studies/res293_representation_learner_information"
STATE_ROOT = ROOT / "models/checkpoints/res293-definition-b"
RUN_ID = "res293-definition-b-fixed-campaign-20261020"
GIB = 1024**3
F_MEMORY_CEILING_BYTES = 12 * GIB
PROCESS_RSS_CEILING_BYTES = 16 * GIB
HOST_MEMORY_RESERVE_BYTES = 2 * GIB
BASELINE_HEAD = "9f928748909f0d49860808c592c567e0e33bf021"
LOCK_SHA256 = "1fb0aba23cc139f4f6c4781755907f5a207be97554479b77837f50fa047c3748"
THREAD_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
SOURCE_FILES = (
    "scripts/run_res293.py",
    "scripts/res293_fit_worker.py",
    "src/powerlifting_state_research/studies/res293_representation_information.py",
    "tests/studies/test_res293_representation_information.py",
    "src/powerlifting_state_research/models/comparators.py",
    "src/powerlifting_state_research/models/temporal_expert.py",
    "src/powerlifting_state_research/models/train_temporal_expert.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dataset.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/evaluate.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/interventions.py",
    "src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/observations.py",
    "src/powerlifting_state_research/evaluation/metrics.py",
    "src/powerlifting_state_research/evaluation/prediction.py",
    "pyproject.toml",
    "uv.lock",
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> bytes:
    payload = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object at {path}")
    return value


def _project_root() -> Path:
    return ROOT.resolve()


def _system_memory() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, raw = line.split(":", 1)
        if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
            values[f"{key}_bytes"] = int(raw.split()[0]) * 1024
    return values


def _available_cpu_ids() -> list[int]:
    if hasattr(os, "sched_getaffinity"):
        return sorted(os.sched_getaffinity(0))
    return list(range(os.cpu_count() or 1))


def _resource_limits() -> dict[str, object]:
    memory = _system_memory()
    cgroup_path = None
    for line in Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines():
        fields = line.split(":", 2)
        if len(fields) == 3 and fields[0] == "0" and fields[1] == "":
            cgroup_path = fields[2]
            break
    ancestors: list[dict[str, object]] = []
    finite_memory_limits: list[int] = []
    finite_cpu_limits: list[float] = []
    if cgroup_path is not None:
        components = [part for part in cgroup_path.strip("/").split("/") if part]
        for length in range(len(components), -1, -1):
            directory = Path("/sys/fs/cgroup").joinpath(*components[:length])
            record: dict[str, object] = {"path": str(directory)}
            for name in (
                "memory.max",
                "memory.high",
                "memory.current",
                "cpu.max",
                "cpuset.cpus.effective",
            ):
                path = directory / name
                try:
                    value = path.read_text(encoding="utf-8").strip()
                except OSError:
                    continue
                record[name] = value
                if name == "memory.max" and value != "max":
                    try:
                        finite_memory_limits.append(int(value))
                    except ValueError:
                        pass
                if name == "cpu.max":
                    parts = value.split()
                    if len(parts) == 2 and parts[0] != "max":
                        try:
                            quota, period = int(parts[0]), int(parts[1])
                            if quota > 0 and period > 0:
                                finite_cpu_limits.append(quota / period)
                        except ValueError:
                            pass
            ancestors.append(record)
    wsl2 = "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()
    total_bytes = memory.get("MemTotal_bytes")
    cgroup_limit = min(finite_memory_limits) if finite_memory_limits else None
    finite_cgroup_headroom = [
        int(record["memory.max"]) - int(record["memory.current"])
        for record in ancestors
        if isinstance(record.get("memory.max"), str)
        and record["memory.max"].isdigit()
        and isinstance(record.get("memory.current"), str)
        and record["memory.current"].isdigit()
    ]
    cgroup_headroom = min(finite_cgroup_headroom) if finite_cgroup_headroom else None
    effective_limit = (
        min(total_bytes, cgroup_limit)
        if total_bytes is not None and cgroup_limit is not None
        else total_bytes
        if cgroup_path is not None
        else None
    )
    effective_headroom = (
        min(total_bytes, cgroup_headroom)
        if total_bytes is not None and cgroup_headroom is not None
        else total_bytes
        if cgroup_path is not None
        else None
    )
    return {
        "available_ram_bytes": memory.get("MemAvailable_bytes"),
        "kernel_visible_total_memory_bytes": total_bytes,
        "wsl2_guest": wsl2,
        "wsl_guest_memory_limit_bytes": total_bytes if wsl2 else None,
        "unified_cgroup_path": cgroup_path,
        "cgroup_ancestors": ancestors,
        "finite_cgroup_memory_limit_bytes": cgroup_limit,
        "finite_cgroup_memory_headroom_bytes": cgroup_headroom,
        "finite_cgroup_cpu_quota_cores": min(finite_cpu_limits) if finite_cpu_limits else None,
        "effective_memory_limit_bytes": effective_limit,
        "effective_memory_headroom_bytes": effective_headroom,
        "effective_memory_limit_known": effective_headroom is not None,
        "effective_memory_limit_source": (
            "minimum of WSL2 guest MemTotal and finite cgroup memory.max"
            if wsl2 and cgroup_limit is not None
            else "WSL2 guest MemTotal"
            if wsl2
            else "minimum of kernel MemTotal and finite cgroup memory.max"
            if cgroup_limit is not None
            else "kernel MemTotal"
        ),
        "cgroup_limit_discovery_complete": cgroup_path is not None,
    }


def memory_admission(
    projected_peak_rss_bytes: int | float | None,
    available_ram_bytes: int | None,
    effective_memory_headroom_bytes: int | None,
) -> dict[str, object]:
    """Admit a measured F projection with OS reserve; do not reserve the RSS ceiling itself."""
    projection_valid = (
        projected_peak_rss_bytes is not None
        and math.isfinite(float(projected_peak_rss_bytes))
        and projected_peak_rss_bytes >= 0
    )
    limits_known = available_ram_bytes is not None and effective_memory_headroom_bytes is not None
    required_bytes = (
        int(projected_peak_rss_bytes) + HOST_MEMORY_RESERVE_BYTES if projection_valid else None
    )
    checks: dict[str, bool | None] = {
        "f_projection_present_and_finite": projection_valid,
        "projected_peak_within_f_gate": (
            None
            if not projection_valid
            else int(projected_peak_rss_bytes) <= F_MEMORY_CEILING_BYTES
        ),
        "projected_peak_within_hard_process_ceiling": (
            None
            if not projection_valid
            else int(projected_peak_rss_bytes) <= PROCESS_RSS_CEILING_BYTES
        ),
        "available_ram_covers_projection_plus_host_reserve": (
            None
            if not projection_valid or available_ram_bytes is None
            else available_ram_bytes >= required_bytes
        ),
        "host_container_limit_covers_projection_plus_host_reserve": (
            None
            if not projection_valid or effective_memory_headroom_bytes is None
            else effective_memory_headroom_bytes >= required_bytes
        ),
    }
    if not projection_valid or not limits_known:
        status = "NOT_QUALIFIED"
    elif not all(check is True for check in checks.values()):
        status = "FAIL"
    else:
        status = "PASS"
    return {
        "status": status,
        "projected_peak_rss_bytes": None if not projection_valid else int(projected_peak_rss_bytes),
        "available_ram_bytes": available_ram_bytes,
        "effective_memory_headroom_bytes": effective_memory_headroom_bytes,
        "host_os_reserve_bytes": HOST_MEMORY_RESERVE_BYTES,
        "required_available_ram_and_limit_bytes": required_bytes,
        "f_projected_memory_ceiling_bytes": F_MEMORY_CEILING_BYTES,
        "hard_process_rss_ceiling_bytes": PROCESS_RSS_CEILING_BYTES,
        "checks": checks,
    }


def preliminary_memory_admission(resource_snapshot: dict[str, object]) -> dict[str, object]:
    return {
        "status": "PENDING_UNTIL_F_PROJECTION",
        "available_ram_bytes": resource_snapshot.get("available_ram_bytes"),
        "effective_memory_limit_bytes": resource_snapshot.get("effective_memory_limit_bytes"),
        "effective_memory_headroom_bytes": resource_snapshot.get("effective_memory_headroom_bytes"),
        "hard_process_rss_ceiling_bytes": PROCESS_RSS_CEILING_BYTES,
        "f_projected_memory_ceiling_bytes": F_MEMORY_CEILING_BYTES,
        "host_os_reserve_bytes": HOST_MEMORY_RESERVE_BYTES,
        "available_ram_threshold_not_applied_before_F": True,
    }


def _environment_receipt() -> dict[str, object]:
    thread_environment = {name: os.environ.get(name) for name in THREAD_VARS}
    thread_ok = all(value == "1" for value in thread_environment.values())
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    lock_sha = _sha256(ROOT / "uv.lock")
    memory = _system_memory()
    resource_limits = _resource_limits()
    disk = shutil.disk_usage(ROOT)
    cpu_ids = _available_cpu_ids()
    cpu_model = "unknown"
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.lower().startswith("model name"):
            cpu_model = line.split(":", 1)[1].strip()
            break
    lock_check = subprocess.run(
        ["uv", "lock", "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    checks = {
        "python": platform.python_implementation() == "CPython"
        and sys.version_info[:3] == (3, 12, 13),
        "numpy": np.__version__ == "2.4.4",
        "torch": torch.__version__ == "2.9.1+cpu",
        "scipy": scipy.__version__ == "1.18.1",
        "cpu_only": not torch.cuda.is_available() and torch.version.cuda is None,
        "single_thread_environment": thread_ok,
        "single_thread_runtime": torch.get_num_threads() == 1
        and torch.get_num_interop_threads() == 1,
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "locked_dependencies": lock_sha == LOCK_SHA256 and lock_check.returncode == 0,
        "memory_info_available": (
            memory.get("MemAvailable_bytes", 0) > 0 and memory.get("MemTotal_bytes", 0) > 0
        ),
        "effective_memory_limit_identified": resource_limits["effective_memory_limit_known"]
        is True,
        "temporary_disk_reserved": disk.free >= 10 * 1024**3,
        "visible_cpu": len(cpu_ids) >= 1,
    }
    return {
        "format": "PSR_RES293_ENVIRONMENT_RECEIPT_V1",
        "status": "PASS" if all(checks.values()) else "FAILED",
        "checks": checks,
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "numpy": np.__version__,
        "torch": torch.__version__,
        "scipy": scipy.__version__,
        "torch_cuda_available": torch.cuda.is_available(),
        "torch_version_cuda": torch.version.cuda,
        "torch_num_threads": torch.get_num_threads(),
        "torch_num_interop_threads": torch.get_num_interop_threads(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "thread_environment": thread_environment,
        "uv_version": subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, check=True
        ).stdout.strip(),
        "uv_lock_sha256": lock_sha,
        "uv_lock_check_exit_code": lock_check.returncode,
        "uv_lock_check_output": (lock_check.stdout + lock_check.stderr).strip(),
        "os": platform.platform(),
        "cpu_model": cpu_model,
        "visible_cpu_ids": cpu_ids,
        "memory": memory,
        "memory_resources": resource_limits,
        "memory_admission": preliminary_memory_admission(resource_limits),
        "disk_root_bytes": {"total": disk.total, "used": disk.used, "free": disk.free},
        "compute_device": "CPU only; one process, one CPU affinity, one thread",
        "network_access_for_fit_worker": "unshared network namespace",
    }


def _thread_env() -> dict[str, str]:
    return {
        **os.environ,
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
        "PYTHONNOUSERSITE": "1",
    }


def _junit_receipt(path: Path) -> dict[str, object]:
    root = ET.parse(path).getroot()
    cases = []
    for case in root.iter("testcase"):
        status = "PASS"
        if case.find("failure") is not None or case.find("error") is not None:
            status = "FAIL"
        cases.append(
            {
                "name": case.attrib.get("name", "unknown"),
                "classname": case.attrib.get("classname", ""),
                "seconds": float(case.attrib.get("time", "0")),
                "status": status,
            }
        )
    return {
        "format": "PSR_RES293_FEATURE_TEST_RECEIPT_V1",
        "status": "PASS" if cases and all(item["status"] == "PASS" for item in cases) else "FAILED",
        "test_count": len(cases),
        "passed": sum(item["status"] == "PASS" for item in cases),
        "failed": sum(item["status"] != "PASS" for item in cases),
        "tests": cases,
        "junit_xml_sha256": _sha256(path),
    }


def _bwrap_command(
    *,
    cache_root: Path,
    output_dir: Path,
    command: str,
    payload_path: Path | None = None,
    output_file: str | None = None,
) -> list[str]:
    repo = _project_root()
    worker = (ROOT / "scripts/res293_fit_worker.py").resolve()
    venv = Path(sys.prefix).resolve()
    cmd = [
        "/usr/bin/bwrap",
        "--die-with-parent",
        "--unshare-net",
        "--clearenv",
        "--ro-bind",
        "/",
        "/",
        "--dev",
        "/dev",
        "--tmpfs",
        "/run",
        "--dir",
        "/run/work",
        "--dir",
        "/run/venv",
        "--ro-bind",
        str(venv),
        "/run/venv",
        "--ro-bind",
        str(worker),
        "/run/worker.py",
    ]
    if payload_path is not None:
        cmd.extend(("--ro-bind", str(payload_path), "/run/work/input.npz"))
    cmd.extend(
        (
            "--dir",
            "/run/work/output",
            "--bind",
            str(output_dir),
            "/run/work/output",
            "--tmpfs",
            str(repo),
            "--tmpfs",
            str(cache_root),
        )
    )
    cmd.extend(
        (
            "--chdir",
            "/run/work",
            "--setenv",
            "PATH",
            "/run/venv/bin:/usr/bin:/bin",
            "--setenv",
            "HOME",
            "/run",
            "--setenv",
            "TMPDIR",
            "/run",
        )
    )
    for name, value in _thread_env().items():
        if name in {*THREAD_VARS, "CUBLAS_WORKSPACE_CONFIG", "PYTHONNOUSERSITE"}:
            cmd.extend(("--setenv", name, value))
    cmd.extend(("/run/venv/bin/python", "-I", "/run/worker.py", command))
    if command == "probe":
        cmd.extend(("--output", f"/run/work/output/{output_file or 'probe.json'}"))
    elif command == "execute":
        cmd.extend(
            (
                "--payload",
                "/run/work/input.npz",
                "--output",
                "/run/work/output",
                "--run-id",
                RUN_ID,
            )
        )
    else:
        raise ValueError(f"unsupported fit worker command {command}")
    return ["/usr/bin/timeout", "-k", "10s", "21600s", *cmd]


def _run_isolated_worker(
    *,
    output_dir: Path,
    command: str,
    payload_path: Path | None = None,
    output_file: str | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"isolated worker output is not empty: {output_dir}")
    cache_root = Path.home() / ".cache/psr-res293-isolated"
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(tempfile.mkdtemp(prefix=f"{command}-", dir=cache_root))
    cache_output = cache_dir / "output"
    cache_output.mkdir()
    cache_payload: Path | None = None
    if payload_path is not None:
        cache_payload = cache_dir / "input.npz"
        shutil.copyfile(payload_path, cache_payload)
    cpu_id = min(_available_cpu_ids())
    command_line = [
        "taskset",
        "-c",
        str(cpu_id),
        *_bwrap_command(
            cache_root=cache_root,
            output_dir=output_dir,
            command=command,
            payload_path=cache_payload,
            output_file=output_file,
        ),
    ]
    wall_start = time.perf_counter()
    try:
        result = subprocess.run(
            command_line,
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=_thread_env(),
            check=False,
        )
        elapsed = time.perf_counter() - wall_start
        for path in cache_output.iterdir():
            if path.is_file():
                shutil.copyfile(path, output_dir / path.name)
        if result.returncode != 0:
            failure = {
                "format": "PSR_RES293_ISOLATED_WORKER_FAILURE_V1",
                "command": command,
                "exit_code": result.returncode,
                "elapsed_wall_seconds": elapsed,
                "stdout": result.stdout[-8_000:],
                "stderr": result.stderr[-8_000:],
            }
            _write_json(output_dir / "worker-failure.json", failure)
            raise RuntimeError(f"isolated {command} worker failed with exit {result.returncode}")
    finally:
        shutil.rmtree(cache_dir)
    return {
        "command": command,
        "exit_code": result.returncode,
        "cpu_affinity": [cpu_id],
        "wall_seconds": elapsed,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "network_namespace_isolated": True,
        "repository_source_hidden": True,
        "environment_inherited_from_host": False,
    }


def _write_csv_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def prefit(scratch: Path, data_root: Path) -> None:
    if scratch.exists() and any(scratch.iterdir()):
        raise FileExistsError(f"pre-fit scratch directory is not empty: {scratch}")
    scratch.mkdir(parents=True, exist_ok=True)
    QUALIFICATION.mkdir(parents=True, exist_ok=True)
    env = _environment_receipt()
    _write_json(QUALIFICATION / "environment.json", env)
    if env["status"] != "PASS":
        receipt = {
            "format": "PSR_RES293_PREFIT_QUALIFICATION_V1",
            "status": "FAILED",
            "failed_gate": "E_environment",
            "environment_receipt_sha256": _sha256(QUALIFICATION / "environment.json"),
        }
        _write_json(QUALIFICATION / "pre-fit-qualification.json", receipt)
        raise RuntimeError("E environment gate failed; preserved receipt and stopped")

    pytest_xml = scratch / "feature-tests.xml"
    pytest_cmd = [
        "uv",
        "run",
        "--locked",
        "--no-sync",
        "pytest",
        "-q",
        "tests/studies/test_res293_representation_information.py",
        f"--junitxml={pytest_xml}",
    ]
    test_start = time.perf_counter()
    test_run = subprocess.run(
        pytest_cmd,
        cwd=ROOT,
        env=_thread_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    test_seconds = time.perf_counter() - test_start
    if not pytest_xml.is_file():
        feature_tests: dict[str, object] = {
            "format": "PSR_RES293_FEATURE_TEST_RECEIPT_V1",
            "status": "FAILED",
            "test_count": 0,
            "passed": 0,
            "failed": 1,
            "pytest_exit_code": test_run.returncode,
            "stdout": test_run.stdout[-8_000:],
            "stderr": test_run.stderr[-8_000:],
            "elapsed_wall_seconds": test_seconds,
        }
    else:
        feature_tests = _junit_receipt(pytest_xml)
        feature_tests["pytest_exit_code"] = test_run.returncode
        feature_tests["elapsed_wall_seconds"] = test_seconds
        feature_tests["stdout"] = test_run.stdout.strip()
        feature_tests["stderr"] = test_run.stderr.strip()
    _write_json(QUALIFICATION / "feature-tests.json", feature_tests)
    if feature_tests["status"] != "PASS" or test_run.returncode != 0:
        _write_json(
            QUALIFICATION / "pre-fit-qualification.json",
            {
                "format": "PSR_RES293_PREFIT_QUALIFICATION_V1",
                "status": "FAILED",
                "failed_gate": "Q_feature_tests",
                "environment_receipt_sha256": _sha256(QUALIFICATION / "environment.json"),
                "feature_test_receipt_sha256": _sha256(QUALIFICATION / "feature-tests.json"),
            },
        )
        raise RuntimeError("Q feature-parity/invariance gate failed; preserved receipt and stopped")

    data_start = time.perf_counter()
    try:
        qualified = study.qualify_canonical_data(data_root)
    except Exception as error:
        failure = {
            "format": "PSR_RES293_DATA_QUALIFICATION_FAILURE_V1",
            "status": "FAILED",
            "error_type": type(error).__name__,
            "error": str(error),
            "elapsed_wall_seconds": time.perf_counter() - data_start,
        }
        _write_json(QUALIFICATION / "data-qualification-failure.json", failure)
        _write_json(
            QUALIFICATION / "pre-fit-qualification.json",
            {
                "format": "PSR_RES293_PREFIT_QUALIFICATION_V1",
                "status": "FAILED",
                "failed_gate": "D_canonical_data",
                "data_failure_sha256": _sha256(QUALIFICATION / "data-qualification-failure.json"),
            },
        )
        raise RuntimeError("D data gate failed; preserved evidence and stopped") from error
    data_parse_seconds = time.perf_counter() - data_start
    study.write_qualification_receipts(qualified, scratch / "data")
    for name in ("data-qualification.json", "split-membership.json", "stratum-counts.csv"):
        shutil.copyfile(scratch / "data" / name, QUALIFICATION / name)

    stage_start = time.perf_counter()
    try:
        staged = study.prepare_fit_payload(qualified, scratch)
    except Exception as error:
        _write_json(
            QUALIFICATION / "input-staging-failure.json",
            {
                "format": "PSR_RES293_INPUT_STAGING_FAILURE_V1",
                "error_type": type(error).__name__,
                "error": str(error),
            },
        )
        _write_json(
            QUALIFICATION / "pre-fit-qualification.json",
            {
                "format": "PSR_RES293_PREFIT_QUALIFICATION_V1",
                "status": "FAILED",
                "failed_gate": "Q_input_staging",
                "data_receipt_sha256": _sha256(QUALIFICATION / "data-qualification.json"),
                "input_staging_failure_sha256": _sha256(
                    QUALIFICATION / "input-staging-failure.json"
                ),
            },
        )
        raise RuntimeError("Q input staging failed; preserved receipt and stopped") from error
    stage_seconds = time.perf_counter() - stage_start
    staged_receipt = dict(staged)
    staged_receipt["payload"] = "temporary fit-input.npz; excluded from repository evidence"
    staged_receipt["elapsed_wall_seconds"] = stage_seconds
    _write_json(QUALIFICATION / "input-staging-receipt.json", staged_receipt)
    shutil.copyfile(scratch / "normalization.json", QUALIFICATION / "normalization.json")
    del qualified

    probe_dir = scratch / "probe"
    try:
        worker_probe = _run_isolated_worker(
            output_dir=probe_dir,
            command="probe",
            output_file="probe.json",
        )
    except Exception as error:
        failure_path = probe_dir / "worker-failure.json"
        if failure_path.is_file():
            worker_failure_sha256 = _sha256(failure_path)
        else:
            worker_failure_sha256 = None
        resource_snapshot = _resource_limits()
        unavailable_probe = {
            "format": "PSR_RES293_FEASIBILITY_PROBE_V1",
            "status": "NOT_QUALIFIED",
            "projected_peak_rss_bytes": None,
            "memory_admission": memory_admission(
                None,
                cast(int | None, resource_snapshot["available_ram_bytes"]),
                cast(int | None, resource_snapshot["effective_memory_headroom_bytes"]),
            ),
            "memory_resources_at_F": resource_snapshot,
            "worker_failure_sha256": worker_failure_sha256,
            "error_type": type(error).__name__,
            "error": str(error),
        }
        _write_json(QUALIFICATION / "feasibility-probe.json", unavailable_probe)
        _write_json(
            QUALIFICATION / "pre-fit-qualification.json",
            {
                "format": "PSR_RES293_PREFIT_QUALIFICATION_V1",
                "status": "FAILED",
                "failed_gate": "F_isolated_feasibility_probe",
                "environment_receipt_sha256": _sha256(QUALIFICATION / "environment.json"),
                "data_receipt_sha256": _sha256(QUALIFICATION / "data-qualification.json"),
                "feature_test_receipt_sha256": _sha256(QUALIFICATION / "feature-tests.json"),
                "input_staging_receipt_sha256": _sha256(
                    QUALIFICATION / "input-staging-receipt.json"
                ),
                "feasibility_probe_sha256": _sha256(QUALIFICATION / "feasibility-probe.json"),
                "worker_failure_sha256": worker_failure_sha256,
                "error_type": type(error).__name__,
                "error": str(error),
            },
        )
        raise RuntimeError("F isolated probe failed; preserved receipts and stopped") from error
    raw_probe = _read_json(probe_dir / "probe.json")
    probe = dict(raw_probe)
    preprocess_projection = 3.0 * (data_parse_seconds + stage_seconds) + 600.0
    post_projection = float(raw_probe["projected_post_analysis_seconds"]) + 3.0 * data_parse_seconds
    verify_projection = 600.0
    qualification_projection = 3.0 * test_seconds + 300.0
    fit_projection = float(raw_probe["projected_campaign_fit_seconds"])
    total_projection = (
        preprocess_projection
        + post_projection
        + verify_projection
        + qualification_projection
        + fit_projection
    )
    data_peak_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    peak_rss_kib = raw_probe.get("peak_rss_kib")
    analysis_workspace_bytes = raw_probe.get("analysis_workspace_bytes")
    if (
        not isinstance(peak_rss_kib, (int, float))
        or not math.isfinite(float(peak_rss_kib))
        or not isinstance(analysis_workspace_bytes, int)
        or analysis_workspace_bytes < 0
    ):
        projected_peak_rss_bytes = None
        worker_peak_bytes = None
    else:
        worker_peak_bytes = int(peak_rss_kib) * 1024
        # The worker peak already includes staged features, optimizer states, and analysis arrays.
        projected_peak_rss_bytes = data_peak_bytes + worker_peak_bytes
    memory_resources_at_f = _resource_limits()
    memory_admission_receipt = memory_admission(
        projected_peak_rss_bytes,
        cast(int | None, memory_resources_at_f["available_ram_bytes"]),
        cast(int | None, memory_resources_at_f["effective_memory_headroom_bytes"]),
    )
    memory_checks = cast(dict[str, bool | None], memory_admission_receipt["checks"])
    feature_payload_bytes = int(staged["payload_bytes"])
    prediction_disk_bound = 30 * (3_072 + 2_304) * 512
    state_disk_bound = 30 * 1_000_000
    temp_disk_bound = (
        2 * feature_payload_bytes + 2 * prediction_disk_bound + 2 * state_disk_bound + 512 * 1024**2
    )
    gate_checks = {
        "each_fit_projection_l_seconds": float(raw_probe["projected_fit_l_seconds"]) <= 180,
        "each_fit_projection_n_seconds": float(raw_probe["projected_fit_n_seconds"]) <= 180,
        "fit_campaign_projection": fit_projection <= 5_400,
        "preprocess_projection": preprocess_projection <= 3_600,
        "post_projection": post_projection <= 7_200,
        "verification_projection": verify_projection <= 1_800,
        "qualification_projection": qualification_projection <= 1_800,
        "total_cpu_and_wall_projection": total_projection <= 21_600,
        "projected_peak_rss_at_or_below_12_gib": (
            memory_checks["projected_peak_within_f_gate"] is True
        ),
        "projected_peak_rss_at_or_below_16_gib_hard_cap": (
            memory_checks["projected_peak_within_hard_process_ceiling"] is True
        ),
        "available_ram_at_least_projection_plus_2_gib": (
            memory_checks["available_ram_covers_projection_plus_host_reserve"] is True
        ),
        "effective_host_container_limit_at_least_projection_plus_2_gib": (
            memory_checks["host_container_limit_covers_projection_plus_host_reserve"] is True
        ),
        "memory_admission_qualified": memory_admission_receipt["status"] == "PASS",
        "temporary_output_disk_bound": temp_disk_bound <= 10 * 1024**3,
        "cpu_only_and_isolated_probe": worker_probe["network_namespace_isolated"] is True,
        "all_30_fits_budgeted_once": True,
    }
    probe.update(
        {
            "status": "PASS" if all(gate_checks.values()) else "FAILED",
            "worker_receipt": worker_probe,
            "data_parse_seconds": data_parse_seconds,
            "feature_stage_seconds": stage_seconds,
            "projected_preprocess_seconds": preprocess_projection,
            "projected_post_analysis_seconds": post_projection,
            "projected_verification_seconds": verify_projection,
            "projected_qualification_seconds": qualification_projection,
            "projected_total_cpu_seconds": total_projection,
            "projected_total_wall_seconds": total_projection,
            "projected_peak_rss_bytes": projected_peak_rss_bytes,
            "memory_admission": memory_admission_receipt,
            "memory_resources_at_F": memory_resources_at_f,
            "memory_bound_bytes": {
                "data_and_feature_prep_process_peak": data_peak_bytes,
                "fit_worker_probe_peak": worker_peak_bytes,
                "analysis_workspace_measured_bound": analysis_workspace_bytes,
                "analysis_workspace_included_in_worker_peak": True,
                "sum": projected_peak_rss_bytes,
            },
            "temporary_output_disk_bound_bytes": temp_disk_bound,
            "temporary_output_disk_components_bytes": {
                "feature_payload_copies": 2 * feature_payload_bytes,
                "predictions_at_512_bytes_per_row_two_copies": 2 * prediction_disk_bound,
                "private_states_at_1mb_each_two_copies": 2 * state_disk_bound,
                "additional_sealing_reserve": 512 * 1024**2,
            },
            "gate_checks": gate_checks,
        }
    )
    _write_json(QUALIFICATION / "feasibility-probe.json", probe)
    checks_passed = all(gate_checks.values())
    prefit_receipt = {
        "format": "PSR_RES293_PREFIT_QUALIFICATION_V1",
        "status": "PASS" if checks_passed else "FAILED",
        "run_id": RUN_ID,
        "protocol_source": (
            "RES-293 v0.2, accepted data-acquisition clarification, and one pre-freeze "
            "engineering amendment separating projected RSS from host reserve"
        ),
        "gates": {
            "D_exact_data_access_split_and_768_strata": "PASS",
            "E_locked_cpu_environment_and_host": env["status"],
            "Q_T1_to_T8_and_context_redundancy": feature_tests["status"],
            "F_outcome_blind_resource_probe": probe["status"],
        },
        "data_receipt_sha256": _sha256(QUALIFICATION / "data-qualification.json"),
        "split_receipt_sha256": _sha256(QUALIFICATION / "split-membership.json"),
        "normalization_receipt_sha256": _sha256(QUALIFICATION / "normalization.json"),
        "input_staging_receipt_sha256": _sha256(QUALIFICATION / "input-staging-receipt.json"),
        "environment_receipt_sha256": _sha256(QUALIFICATION / "environment.json"),
        "feature_test_receipt_sha256": _sha256(QUALIFICATION / "feature-tests.json"),
        "feasibility_probe_sha256": _sha256(QUALIFICATION / "feasibility-probe.json"),
        "outcome_blind": True,
        "fitted_models": 0,
        "predictions_or_scores_created": False,
        "evaluation_truth_summaries_exported": False,
        "resource_projections_seconds": {
            "fit_campaign": fit_projection,
            "preprocess": preprocess_projection,
            "post_analysis": post_projection,
            "verification": verify_projection,
            "qualification": qualification_projection,
            "total": total_projection,
        },
        "memory_admission": memory_admission_receipt,
        "memory_resources_at_F": memory_resources_at_f,
        "gate_checks": gate_checks,
    }
    _write_json(QUALIFICATION / "pre-fit-qualification.json", prefit_receipt)
    if not checks_passed:
        raise RuntimeError("F resource qualification failed; all receipts preserved and stopped")


def _protocol_payload() -> dict[str, object]:
    sources = {name: _sha256(ROOT / name) for name in SOURCE_FILES}
    receipt_names = (
        "data-qualification.json",
        "split-membership.json",
        "stratum-counts.csv",
        "normalization.json",
        "input-staging-receipt.json",
        "environment.json",
        "feature-tests.json",
        "feasibility-probe.json",
        "pre-fit-qualification.json",
        "memory-gate-repair-amendment.json",
    )
    receipts = {name: _sha256(QUALIFICATION / name) for name in receipt_names}
    data = _read_json(QUALIFICATION / "data-qualification.json")
    normalization = _read_json(QUALIFICATION / "normalization.json")
    feasibility = _read_json(QUALIFICATION / "feasibility-probe.json")
    return {
        "format": "PSR_RES293_EXECUTABLE_PROTOCOL_V1",
        "source_proposals": [
            "RES-293 v0.1 exact definitions",
            "RES-293 v0.2 replacement rules R1-R4",
            "RES-293 current issue-description data-acquisition clarification",
            (
                "one pre-freeze engineering amendment: memory admission uses F projection plus "
                "host reserve"
            ),
        ],
        "study_slug": "res293-representation-learner-information-exploratory",
        "revision": "v0.2-executable",
        "base_commit": BASELINE_HEAD,
        "data": {
            "mode": data["canonical_bytes_mode"],
            "dataset_spec_id": data["dataset_spec_id"],
            "benchmark_spec_id": data["benchmark_spec_id"],
            "realization_id": data["realization_id"],
            "realization_digest": data["realization_digest"],
            "manifest_digest": data["manifest_digest"],
            "manifest_file_sha256": data["manifest_file_sha256"],
            "train_sha256": data["train_sha256"],
            "validation_sha256": data["validation_sha256"],
            "schema_identity": data["schema_identity"],
            "rights": data["rights"],
            "generator_source_sha256": data["generator_source_sha256"],
            "generator_configuration_sha256": data["generator_configuration_sha256"],
            "generator_seeds": [26901, 26902, 26903, 26904, 26905],
            "generation_repeated": False,
        },
        "split": {
            "train_rows": 12_288,
            "fit_rows": 9_984,
            "development_rows": 2_304,
            "validation_rows": 3_072,
            "fit_row_ids_sha256": data["fit_row_ids_sha256"],
            "development_row_ids_sha256": data["development_row_ids_sha256"],
            "validation_row_ids_sha256": data["validation_row_ids_sha256"],
            "split_digest": data["split_digest"],
            "split_rule": (
                "plan x horizon x three-history-template; hash(row_id), then row_id; "
                "floor(n/5) selection"
            ),
            "strata": 768,
            "per_stratum": {"train": 16, "fit": 13, "development": 3, "validation": 4},
            "exact_membership_verified": True,
        },
        "task": {
            "origin_day": 224,
            "history_last_day": 223,
            "horizons_days": [14, 28, 56],
            "targets": list(study.EXPECTED_TARGETS),
            "target_definition": "C_t[224+h-1] - C_t[223], kg",
            "prior_evaluation_outcomes_inspected": True,
            "interpretation": (
                "exploratory conditional on the fixed synthetic realization and analyzed seeds"
            ),
        },
        "information_boundary": {
            "allowed": [
                "three lifts in squat, bench_press, deadlift order",
                "32 dated observations through day 223",
                "assessment_kg",
                "prescribed_load_kg",
                "velocity_mps",
                "derived relative load and within-history differences",
                "historical schedule dose, intensity, and product",
                "declared future plan, origin, and horizon",
            ],
            "forbidden_predictors": [
                "row_id or entity_id",
                "latent or simulated state",
                "future realized observations/performance",
                "target fields or evaluation truth",
                "generator equations or authority sidecars",
                "donor keys or model-registry scores",
            ],
            "fitter_input": (
                "fit labels plus standardized fit/development/validation features and row keys only"
            ),
            "development_validation_labels_in_fitter_payload": False,
            "training_process": (
                "single isolated process; repository hidden; network namespace unshared"
            ),
        },
        "feature_definitions": {
            "first_stage_channels": [
                "assessment",
                "prescribed_load",
                "velocity",
                "prescribed_load/assessment",
                "assessment_delta; first value zero",
                "velocity_delta; first value zero",
            ],
            "first_stage_stats": (
                "fit entities only; per lift/channel; float64; population SD floor 1e-6"
            ),
            "schedule_scales": ["dose/1.2", "intensity/1.0", "dose*intensity/1.2"],
            "summary_S": (
                "127 features: per lift, six channels x first/last/mean/population SD/OLS slope; "
                "schedule x mean/recent-four/latest; ten context features"
            ),
            "ordered_O": (
                "874 features: 3 lifts x 32 dates x 9 channels in lift/date/channel order; "
                "ten context features"
            ),
            "context_order": [
                "origin_day/224",
                "horizon_days/56",
                "future_dose/1.2",
                "future_intensity",
                "future_dose*intensity/1.2",
                "full_declared_plan_duration/56",
                "cessation",
                "continue",
                "step_down",
                "step_up",
            ],
            "second_stage_stats": (
                "fit rows only; per active feature; float64; population SD floor 1e-6; "
                "standardized values cast to float32"
            ),
            "packed_width": 874,
            "summary_slots": {"history": [0, 116], "padding": [117, 863], "context": [864, 873]},
            "padding_value": "canonical positive float32 zero",
            "C5_mask": "zero standardized history slots 0:864; retain context",
            "C6_mask": (
                "zero 60 summary slots 39*lift+5*channel+summary for channels 0,1,3,4; "
                "retain velocity, velocity delta, schedule, context"
            ),
            "mask_applied_after_standardization": True,
            "context_support": normalization["context_support"],
            "canonical_feature_source": {
                "summary": sources["src/powerlifting_state_research/models/comparators.py"],
                "ordered_input": sources[
                    "src/powerlifting_state_research/models/temporal_expert.py"
                ],
            },
        },
        "configurations": [
            {"id": "C1", "input": "S full", "learner": "L affine 874->3"},
            {"id": "C2", "input": "O full", "learner": "L affine 874->3"},
            {"id": "C3", "input": "S full fixed reference", "learner": "N 874->32 ReLU->3"},
            {"id": "C4", "input": "O full", "learner": "N 874->32 ReLU->3"},
            {"id": "C5", "input": "S context only", "learner": "N 874->32 ReLU->3"},
            {
                "id": "C6",
                "input": "S assessment/load group omitted",
                "learner": "N 874->32 ReLU->3",
            },
        ],
        "training": {
            "initialization_seeds": [293201, 293202, 293203, 293204, 293205],
            "batch_order_seeds": [293301, 293302, 293303, 293304, 293305],
            "pairing": "same initialization and batch order within learner family and seed",
            "weights": "independent N(0,0.01), layer order, dedicated CPU torch Generator",
            "biases": "all exact zero; saved in initial-state receipt",
            "optimizer": (
                "AdamW lr=0.003, betas=(0.9,0.999), eps=1e-8; "
                "decay 1e-4 weights only; zero bias decay"
            ),
            "batch_size": 256,
            "batch_sampling": "one CPU torch randperm per epoch, no replacement, 39 batches/epoch",
            "epochs": 60,
            "updates_per_fit": 2_340,
            "fit_count": 30,
            "target_standardization": (
                "fit-only per target; population SD floor 1e-6; inverse transformed to kg once"
            ),
            "loss": "mean squared error over rows and three standardized targets",
            "checkpoint": (
                "final epoch only; no best checkpoint, early stopping, or development selection"
            ),
            "training_loss_diagnostics_epochs": [1, 10, 20, 30, 40, 50, 60],
            "compute": (
                "CPU only; one process; one CPU affinity; one compute thread; "
                "deterministic algorithms"
            ),
        },
        "model_parameter_counts": {"L": 2_625, "N": 28_099},
        "estimand_and_analysis": {
            "primary_risk": (
                "arithmetic mean of five seed-specific validation RMSEs; not ensemble RMSE"
            ),
            "canonical_metrics": ["RMSE", "MAE", "R2", "SRE population SD"],
            "primary_contrasts_per_lift": [
                "C2-C1",
                "C4-C3",
                "C3-C1",
                "C4-C2",
                "(C4-C3)-(C2-C1)",
                "C3-C5",
                "C3-C6",
            ],
            "primary_contrast_count": 21,
            "report_all_per_seed_contrasts": True,
            "uncertainty": {
                "kind": "descriptive first-order shared-entity Rademacher multiplier envelope",
                "strata": 768,
                "entities_per_stratum": 4,
                "finite_stratum_factor": "sqrt(4/3)",
                "draws": 20_000,
                "seed": 293901,
                "chunk_size": 100,
                "same_entity_weights_across_family": True,
                "maximum_over": 21,
                "quantile": 0.95,
                "quantile_method": "NumPy quantile method=higher",
                "label": "sampling coverage not qualified; percentile is not a confidence level",
                "withdrawn_claims": [
                    "calibrated coverage",
                    "significance and p-values",
                    "material benefit or harm",
                    "equivalence",
                    "resolved superiority",
                ],
                "zero_or_nonfinite_rmse_rule": (
                    "retain all finite point contrasts; joint envelope unsupported; "
                    "no floor or omitted contrast"
                ),
                "all_zero_multiplier_rule": "do not publish a zero-width envelope",
                "excluded_uncertainty": [
                    "training data",
                    "split",
                    "fit-seed population",
                    "model-form",
                    "post-selection",
                ],
            },
        },
        "claim_scope": {
            "positive_claim": (
                "observed differences between these fixed finite-budget training procedures"
            ),
            "does_not_establish": [
                "nonlinear architecture is necessary or load-bearing",
                "an optimal or strong simple-model frontier",
                "information-theoretic necessity or an independent velocity sensor mechanism",
                "global identification or latent source recovery",
                "human-athlete validity or causal coaching efficacy",
                "historical cross-version numeric rankings",
                "calibrated superiority or independent confirmation",
            ],
            "negative_null_and_inconclusive_findings_preserved": True,
            "no_margin_or_post_outcome_classification": True,
        },
        "qualification_receipt_sha256": receipts,
        "qualified_source_file_sha256": sources,
        "environment": {
            "python": "CPython 3.12.13",
            "numpy": "2.4.4",
            "torch": "2.9.1+cpu",
            "scipy": "1.18.1; not used by uncertainty calculation",
            "uv_lock_sha256": LOCK_SHA256,
            "resource_gates": feasibility["gate_checks"],
            "memory_admission": feasibility["memory_admission"],
            "memory_resources_at_F": feasibility["memory_resources_at_F"],
            "projections_seconds": {
                "fit_campaign": feasibility["projected_campaign_fit_seconds"],
                "preprocess": feasibility["projected_preprocess_seconds"],
                "post_analysis": feasibility["projected_post_analysis_seconds"],
                "verification": feasibility["projected_verification_seconds"],
                "qualification": feasibility["projected_qualification_seconds"],
                "total": feasibility["projected_total_wall_seconds"],
            },
            "hard_ceilings": {
                "per_fit_wall_seconds": 180,
                "campaign_cpu_seconds": 21_600,
                "campaign_wall_seconds": 21_600,
                "projected_peak_rss_bytes": F_MEMORY_CEILING_BYTES,
                "process_peak_rss_bytes": PROCESS_RSS_CEILING_BYTES,
                "host_os_memory_reserve_bytes": HOST_MEMORY_RESERVE_BYTES,
                "temporary_output_disk_bytes": 10 * 1024**3,
            },
            "no_gpu_or_paid_compute": True,
        },
        "artifact_and_stop_contract": {
            "states_and_development_validation_predictions_sealed_before_truth_join": True,
            "private_state_distribution": "withheld; state SHA-256 retained, no checkpoint release",
            "prediction_artifacts": "canonical JSONL keyed by row_id, exact full split key set",
            "analysis_truth_access": (
                "only after 30 final states and all development/validation predictions hash-verify"
            ),
            "one_shot_campaign": True,
            "retries_or_replacement_seeds": "prohibited",
            "failure": (
                "preserve partial receipt and stop; no evaluation unless all 30 fits are sealed"
            ),
            "baseline_main_head": BASELINE_HEAD,
        },
    }


def freeze_protocol() -> None:
    branch = _git(["git", "branch", "--show-current"])
    head = _git(["git", "rev-parse", "HEAD"])
    if branch != "res-293-res-294-definition-b-completion" or head != BASELINE_HEAD:
        raise RuntimeError(
            "protocol freeze must be created on the isolated research branch at the audited head"
        )
    prefit = _read_json(QUALIFICATION / "pre-fit-qualification.json")
    if prefit.get("status") != "PASS":
        raise RuntimeError("cannot freeze RES-293 before all D/E/Q/F qualification gates pass")
    payload = _protocol_payload()
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    protocol = {
        "protocol_id": (
            f"psr:study-protocol:res293-representation-learner-information@1.0.0~{digest[:12]}"
        ),
        "protocol_digest": f"sha256:{digest}",
        "payload": payload,
    }
    protocol_bytes = _write_json(STUDY_HOME / "protocol.json", protocol)
    freeze_record = {
        "format": "PSR_RES293_PROTOCOL_FREEZE_V1",
        "status": "FROZEN",
        "frozen_at_utc": _utc_now(),
        "protocol_id": protocol["protocol_id"],
        "protocol_digest": protocol["protocol_digest"],
        "protocol_file_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
        "baseline_head": BASELINE_HEAD,
        "branch_required": "res-293-res-294-definition-b-completion",
        "source_file_sha256": payload["qualified_source_file_sha256"],
        "qualification_receipt_sha256": payload["qualification_receipt_sha256"],
        "engineering_amendments": [
            {
                "id": 1,
                "path": (
                    "studies/res293_representation_learner_information/qualification/"
                    "memory-gate-repair-amendment.json"
                ),
                "sha256": _sha256(QUALIFICATION / "memory-gate-repair-amendment.json"),
                "scope": "memory admission only; unchanged scientific settings",
            }
        ],
        "dataset_realization_digest": study.REALIZATION_DIGEST,
        "train_sha256": study.TRAIN_SHA256,
        "validation_sha256": study.VALIDATION_SHA256,
        "split_digest": study.SPLIT_DIGEST,
        "uv_lock_sha256": LOCK_SHA256,
        "fit_count": 30,
        "protocol_changes_after_first_fit": "prohibited; versioned amendment required",
    }
    _write_json(STUDY_HOME / "protocol-freeze.json", freeze_record)


def _git(command: list[str]) -> str:
    return subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _verify_frozen_source() -> tuple[dict[str, Any], dict[str, Any], str, str]:
    protocol = _read_json(STUDY_HOME / "protocol.json")
    freeze = _read_json(STUDY_HOME / "protocol-freeze.json")
    payload = protocol["payload"]
    actual_digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    if protocol.get("protocol_digest") != f"sha256:{actual_digest}":
        raise RuntimeError("frozen protocol content digest mismatch")
    if _sha256(STUDY_HOME / "protocol.json") != freeze.get("protocol_file_sha256"):
        raise RuntimeError("frozen protocol file hash mismatch")
    for name, expected in freeze["source_file_sha256"].items():
        if _sha256(ROOT / name) != expected:
            raise RuntimeError(f"qualified source bytes changed after freeze: {name}")
    for name, expected in freeze["qualification_receipt_sha256"].items():
        if _sha256(QUALIFICATION / name) != expected:
            raise RuntimeError(f"qualification receipt changed after freeze: {name}")
    head = _git(["git", "rev-parse", "HEAD"])
    tree = _git(["git", "rev-parse", "HEAD^{tree}"])
    branch = _git(["git", "branch", "--show-current"])
    status = _git(["git", "status", "--porcelain"])
    if branch != "res-293-res-294-definition-b-completion" or status:
        raise RuntimeError("execution requires the isolated clean research branch")
    if _git(["git", "rev-parse", "HEAD^"]) != BASELINE_HEAD:
        raise RuntimeError("protocol freeze commit must directly follow the audited baseline HEAD")
    return protocol, freeze, head, tree


def _copy_prediction_artifacts(run_dir: Path, result_dir: Path, seal: dict[str, Any]) -> None:
    prediction_dir = result_dir / "predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    for fit in seal["fits"]:
        for item in (fit["state_artifact"], *fit["prediction_artifacts"].values()):
            source = run_dir / item["file"]
            if _sha256(source) != item["sha256"]:
                raise RuntimeError(f"sealed artifact changed before preservation: {source.name}")
            if item["file"].endswith(".state.npz"):
                destination = STATE_ROOT / item["file"]
            else:
                destination = prediction_dir / item["file"]
            if destination.exists():
                raise FileExistsError(f"one-shot output already exists: {destination}")
            shutil.copyfile(source, destination)
            if _sha256(destination) != item["sha256"]:
                raise RuntimeError(f"preserved artifact hash mismatch: {destination.name}")
        fit_receipt = run_dir / f"{fit['config']}-seed-{fit['initialization_seed']}.fit.json"
        fit_directory = result_dir / "fits"
        fit_directory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fit_receipt, fit_directory / fit_receipt.name)
    shutil.copyfile(run_dir / "training-loss.csv", result_dir / "training-loss.csv")


def execute(scratch: Path, result_dir: Path) -> None:
    protocol, freeze, head, tree = _verify_frozen_source()
    if _sha256(ROOT / "uv.lock") != LOCK_SHA256:
        raise RuntimeError("uv.lock changed after pre-fit qualification")
    prefit_receipt = _read_json(QUALIFICATION / "pre-fit-qualification.json")
    feasibility = _read_json(QUALIFICATION / "feasibility-probe.json")
    if (
        prefit_receipt.get("status") != "PASS"
        or feasibility.get("status") != "PASS"
        or feasibility.get("memory_admission", {}).get("status") != "PASS"
    ):
        raise RuntimeError("execution requires passing frozen D/E/Q/F receipts")
    env = _environment_receipt()
    if env["status"] != "PASS":
        _write_json(scratch / "execution-environment-failure.json", env)
        raise RuntimeError("execution environment no longer passes the frozen E gate")
    current_resources = _resource_limits()
    execution_admission = memory_admission(
        feasibility.get("projected_peak_rss_bytes"),
        cast(int | None, current_resources.get("available_ram_bytes")),
        cast(int | None, current_resources.get("effective_memory_headroom_bytes")),
    )
    admission_receipt = {
        "format": "PSR_RES293_PRE_FIT_MEMORY_ADMISSION_V1",
        "checked_at_utc": _utc_now(),
        "protocol_id": protocol["protocol_id"],
        "f_projection_receipt_sha256": _sha256(QUALIFICATION / "feasibility-probe.json"),
        "memory_resources_at_launch": current_resources,
        **execution_admission,
    }
    if execution_admission["status"] != "PASS":
        _write_json(scratch / "execution-admission-failure.json", admission_receipt)
        raise RuntimeError("pre-fit memory admission failed; no fit launched and receipt preserved")
    payload_path = scratch / "fit-input.npz"
    stage_receipt = _read_json(QUALIFICATION / "input-staging-receipt.json")
    if not payload_path.is_file() or _sha256(payload_path) != stage_receipt["payload_bytes_sha256"]:
        raise RuntimeError("staged fit-only input payload is missing or changed")
    if scratch.joinpath("execution-started.json").exists():
        raise FileExistsError("the one-shot RES-293 campaign has already started")
    if result_dir.exists() and any(result_dir.iterdir()):
        raise FileExistsError("RES-293 result directory is not empty")
    scratch.mkdir(parents=True, exist_ok=True)
    execution_start = {
        "format": "PSR_RES293_EXECUTION_AUTHORITY_V1",
        "run_id": RUN_ID,
        "started_at_utc": _utc_now(),
        "protocol_id": protocol["protocol_id"],
        "protocol_digest": protocol["protocol_digest"],
        "protocol_file_sha256": freeze["protocol_file_sha256"],
        "freeze_commit": head,
        "freeze_tree": tree,
        "branch": _git(["git", "branch", "--show-current"]),
        "baseline_head": BASELINE_HEAD,
        "train_sha256": study.TRAIN_SHA256,
        "validation_sha256": study.VALIDATION_SHA256,
        "split_digest": study.SPLIT_DIGEST,
        "fit_payload_semantic_sha256": stage_receipt["payload_sha256"],
        "fit_payload_file_sha256": stage_receipt["payload_bytes_sha256"],
        "configurations": ["C1", "C2", "C3", "C4", "C5", "C6"],
        "initialization_seeds": [293201, 293202, 293203, 293204, 293205],
        "batch_seeds": [293301, 293302, 293303, 293304, 293305],
        "declared_fit_count": 30,
        "truth_join_status": "closed",
        "memory_admission": admission_receipt,
    }
    _write_json(scratch / "execution-started.json", execution_start)
    worker_dir = scratch / "worker-output"
    worker_receipt = _run_isolated_worker(
        output_dir=worker_dir,
        command="execute",
        payload_path=payload_path,
    )
    seal = study.verify_sealed_run(worker_dir, expected_run_id=RUN_ID)
    with np.load(payload_path, allow_pickle=False) as archive:
        expected_validation_ids = tuple(
            str(item) for item in archive["validation_row_ids"].tolist()
        )
        expected_development_ids = tuple(
            str(item) for item in archive["development_row_ids"].tolist()
        )
    for fit in seal["fits"]:
        for split, ids in (
            ("validation", expected_validation_ids),
            ("development", expected_development_ids),
        ):
            artifact_path = worker_dir / fit["prediction_artifacts"][split]["file"]
            predictions = study.parse_prediction_jsonl(artifact_path.read_bytes())
            if tuple(row.row_id for row in predictions) != ids:
                raise RuntimeError(f"sealed {split} prediction keys differ from staged membership")
        if fit["epochs"] != 60 or fit["updates"] != 2_340 or not fit["final_epoch_only"]:
            raise RuntimeError(
                "sealed fit differs from the frozen epoch/update/checkpoint contract"
            )
        if fit["bias_initialization"]["nonzero_count"] != 0:
            raise RuntimeError("sealed fit violated zero-bias initialization")
    _copy_prediction_artifacts(worker_dir, result_dir, seal)
    result_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(worker_dir / "seal-manifest.json", result_dir / "seal-manifest.json")
    execution_receipt = {
        "format": "PSR_RES293_EXECUTION_RECEIPT_V1",
        "status": "30_FITS_SEALED",
        "run_id": RUN_ID,
        "protocol_id": protocol["protocol_id"],
        "protocol_digest": protocol["protocol_digest"],
        "freeze_commit": head,
        "freeze_tree": tree,
        "baseline_head": BASELINE_HEAD,
        "train_sha256": study.TRAIN_SHA256,
        "validation_sha256": study.VALIDATION_SHA256,
        "split_digest": study.SPLIT_DIGEST,
        "fit_count": 30,
        "configuration_count": 6,
        "seed_count": 5,
        "epochs_per_fit": 60,
        "updates_per_fit": 2_340,
        "elapsed_fit_cpu_seconds": seal["elapsed_cpu_seconds"],
        "elapsed_fit_wall_seconds": seal["elapsed_wall_seconds"],
        "peak_rss_kib": seal["peak_rss_kib"],
        "worker_isolation_receipt": worker_receipt,
        "seal_manifest_sha256": _sha256(worker_dir / "seal-manifest.json"),
        "seal_manifest": "seal-manifest.json",
        "prediction_artifact_count": 60,
        "sealed_state_count": 30,
        "checkpoint_distribution": "withheld; local ignored state files only",
        "evaluation_truth_opened": False,
        "fits": [
            {
                "config": fit["config"],
                "seed": fit["initialization_seed"],
                "initial_state_sha256": fit["initial_state_sha256"],
                "final_state_sha256": fit["final_state_sha256"],
                "state_file_sha256": fit["state_artifact"]["sha256"],
                "validation_prediction_sha256": fit["prediction_artifacts"]["validation"]["sha256"],
                "development_prediction_sha256": fit["prediction_artifacts"]["development"][
                    "sha256"
                ],
                "parameter_count": fit["parameter_count"],
                "biases_exact_zero": fit["bias_initialization"]["nonzero_count"] == 0,
                "epochs": fit["epochs"],
                "updates": fit["updates"],
                "cpu_seconds": fit["cpu_seconds"],
                "wall_seconds": fit["wall_seconds"],
            }
            for fit in seal["fits"]
        ],
    }
    _write_json(result_dir / "execution-receipt.json", execution_receipt)
    seal_hash = _sha256(worker_dir / "seal-manifest.json")
    if seal_hash != execution_receipt["seal_manifest_sha256"]:
        raise RuntimeError("prediction/state seal changed before evaluation")
    analysis_receipt = study.analyze_sealed_run(
        worker_dir,
        result_dir,
        expected_run_id=RUN_ID,
    )
    if analysis_receipt["status"] != "COMPLETE":
        raise RuntimeError("sealed analysis did not produce all 21 primary contrasts")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prefit_parser = subparsers.add_parser("prefit")
    prefit_parser.add_argument("--scratch", type=Path, required=True)
    prefit_parser.add_argument("--data-root", type=Path, default=study.DEFAULT_DATA_ROOT)
    subparsers.add_parser("freeze")
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--scratch", type=Path, required=True)
    execute_parser.add_argument("--results", type=Path, default=RESULTS)
    args = parser.parse_args()
    if args.command == "prefit":
        prefit(args.scratch.resolve(), args.data_root.resolve())
    elif args.command == "freeze":
        freeze_protocol()
    else:
        execute(args.scratch.resolve(), args.results.resolve())


if __name__ == "__main__":
    main()
