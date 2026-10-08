"""Build/check the output-free RES-274 Colab execution notebook."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks/public-native-temporal-expert-colab.ipynb"
REPOSITORY_URL = "https://github.com/Litju/powerlifting-state-research"

SOURCES = (
    r"""# RES274_CELL: 01_CONFIG
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# Set CODE_SHA to the merged Gate-A commit before running this notebook.
CODE_SHA = ""
USE_GOOGLE_DRIVE = True
DRIVE_OUTPUT_ROOT = ""
if os.environ.get("CUBLAS_WORKSPACE_CONFIG") not in (None, ":4096:8"):
    raise RuntimeError("CUBLAS_WORKSPACE_CONFIG must be :4096:8 before CUDA initialization")
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
RUN_ID = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
print("CODE_SHA is required; training uses only this exact detached commit.")
""",
    r"""# RES274_CELL: 02_OPTIONAL_DRIVE
if USE_GOOGLE_DRIVE:
    from google.colab import drive

    drive.mount("/content/drive")
    DRIVE_BASE = Path("/content/drive/MyDrive")
    configured_root = (
        DRIVE_OUTPUT_ROOT.strip()
        or input(
            "Drive output root under MyDrive (recommended: powerlifting-state-research/res274): "
        ).strip()
    )
    candidate = Path(configured_root).expanduser()
    if candidate.is_absolute():
        RUN_BASE = candidate.resolve()
    else:
        relative_root = candidate
        if relative_root.parts and relative_root.parts[0] == "MyDrive":
            relative_root = Path(*relative_root.parts[1:])
        if ".." in relative_root.parts:
            raise ValueError("Drive output root cannot traverse above MyDrive")
        RUN_BASE = (DRIVE_BASE / relative_root).resolve()
    if not RUN_BASE.is_relative_to(DRIVE_BASE.resolve()):
        raise ValueError("Drive output root must be inside the mounted MyDrive")
else:
    DRIVE_BASE = None
    RUN_BASE = Path("/content/powerlifting-state-research/res274")

REPO_DIR = Path("/content/powerlifting-state-research")
DATASET_ROOT = Path("/content") / f"res274-iid-dataset-{RUN_ID}"
RUN_OUTPUT = RUN_BASE / RUN_ID
BUNDLE_PATH = RUN_BASE / f"res274-{RUN_ID}.zip"
if RUN_OUTPUT.exists() or BUNDLE_PATH.exists():
    raise FileExistsError("the configured run ID already exists")
RUN_OUTPUT.mkdir(parents=True)
print(f"RUN_OUTPUT={RUN_OUTPUT}")
""",
    r"""# RES274_CELL: 03_CLONE_EXACT_SOURCE
if not CODE_SHA or not re.fullmatch(r"[0-9a-fA-F]{40}", CODE_SHA):
    raise ValueError("Set CODE_SHA to the full 40-character merged Gate-A commit SHA")
if REPO_DIR.exists():
    raise FileExistsError(f"source checkout already exists: {REPO_DIR}")
subprocess.run(
    [
        "git",
        "clone",
        "--no-checkout",
        "https://github.com/Litju/powerlifting-state-research",
        str(REPO_DIR),
    ],
    check=True,
)
subprocess.run(["git", "checkout", "--detach", CODE_SHA], cwd=REPO_DIR, check=True)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_DIR, text=True).strip()
worktree = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_DIR, text=True)
if head.lower() != CODE_SHA.lower() or worktree.strip():
    raise RuntimeError("exact CODE_SHA checkout or clean worktree verification failed")
print(f"CODE_SHA={head}")
print("GIT_TREE_STATUS=clean")
""",
    r"""# RES274_CELL: 04_GPU_ENVIRONMENT
uv_bin = shutil.which("uv")
if uv_bin is None:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "uv"], check=True)
    uv_bin = shutil.which("uv")
if uv_bin is None:
    raise RuntimeError("uv installation failed")

# The lock intentionally selects CPU PyTorch for CI. Replace only that wheel here.
subprocess.run(
    [uv_bin, "sync", "--locked", "--all-groups", "--python", "3.12"],
    cwd=REPO_DIR,
    check=True,
)
VENV_PYTHON = REPO_DIR / ".venv/bin/python"
subprocess.run(
    [
        uv_bin,
        "pip",
        "install",
        "--python",
        str(VENV_PYTHON),
        "--reinstall-package",
        "torch",
        "--index-url",
        "https://download.pytorch.org/whl/cu128",
        "torch==2.9.1",
    ],
    cwd=REPO_DIR,
    check=True,
)
gpu_probe = (
    "import torch; "
    "print('torch.__version__=', torch.__version__); "
    "print('torch.cuda.is_available()=', torch.cuda.is_available()); "
    "print('torch.version.cuda=', torch.version.cuda); "
    "print('torch.backends.cudnn.version()=', torch.backends.cudnn.version()); "
    "assert torch.__version__.startswith('2.9.1+cu128'); "
    "assert torch.cuda.is_available() and torch.version.cuda == '12.8'; "
    "assert torch.backends.cudnn.version() is not None"
)
subprocess.run([str(VENV_PYTHON), "-c", gpu_probe], cwd=REPO_DIR, check=True)
print("CUDA_TRAINING_ENVIRONMENT=READY")
""",
    r"""# RES274_CELL: 05_RUNTIME_RECEIPT
RUNTIME_RECEIPT_PATH = RUN_OUTPUT / "runtime/runtime-receipt.json"
RUNTIME_RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
runtime_program = (
    "import hashlib,importlib.metadata as im,json,platform,subprocess,sys,torch; "
    "from pathlib import Path; "
    "code_sha=sys.argv[1]; output=Path(sys.argv[2]); "
    "head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(); "
    "status=subprocess.check_output(['git','status','--porcelain'],text=True).strip(); "
    "assert head.lower()==code_sha.lower() and not status; "
    "gpu=torch.cuda.get_device_properties(0); "
    "driver=subprocess.run(['nvidia-smi','--query-gpu=driver_version',"
    "'--format=csv,noheader'],capture_output=True,text=True); "
    "deps=sorted((str(d.metadata['Name']),d.version) for d in im.distributions() "
    "if d.metadata.get('Name')); "
    "dependency_fingerprint='sha256:'+hashlib.sha256(json.dumps(deps,sort_keys=True,"
    "separators=(',',':')).encode()).hexdigest(); "
    "receipt={'format':'PSR_RUNTIME_RECEIPT_V1','code_sha':head,'git_tree_status':'clean',"
    "'python':platform.python_version(),'package_version':im.version('powerlifting-state-research'),"
    "'torch_version':torch.__version__,'torch_build':torch.version.git_version,"
    "'torch_cuda_version':torch.version.cuda,'cudnn_version':torch.backends.cudnn.version(),"
    "'gpu_name':gpu.name,'gpu_memory_bytes':gpu.total_memory,"
    "'nvidia_driver':driver.stdout.splitlines()[0] if driver.returncode==0 else None,"
    "'platform':platform.platform(),'dependency_fingerprint':dependency_fingerprint,"
    "'determinism_controls':None}; "
    "output.write_text(json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\\n',"
    "encoding='utf-8'); "
    "print(json.dumps(receipt,indent=2,sort_keys=True))"
)
subprocess.run(
    [str(VENV_PYTHON), "-c", runtime_program, CODE_SHA, str(RUNTIME_RECEIPT_PATH)],
    cwd=REPO_DIR,
    check=True,
)
""",
    r"""# RES274_CELL: 06_DETERMINISTIC_RUNTIME
determinism_program = (
    "import json,sys; from pathlib import Path; "
    "from powerlifting_state_research.models.training import "
    "PUBLIC_NATIVE_TEMPORAL_EXPERT_PROTOCOL as protocol; "
    "from powerlifting_state_research.models.train_temporal_expert import configure_determinism; "
    "path=Path(sys.argv[1]); receipt=json.loads(path.read_text(encoding='utf-8')); "
    "seeds=list(protocol.seeds); "
    "receipt['determinism_controls']={'initial_configuration':configure_determinism(seeds[0]),"
    "'declared_training_seeds':seeds,'cross_gpu_bitwise_guarantee':False}; "
    "path.write_text(json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\\n',"
    "encoding='utf-8'); "
    "print(json.dumps(receipt['determinism_controls'],indent=2,sort_keys=True))"
)
subprocess.run(
    [str(VENV_PYTHON), "-c", determinism_program, str(RUNTIME_RECEIPT_PATH)],
    cwd=REPO_DIR,
    check=True,
)
print("Bit-identical training across different GPU models or drivers is not guaranteed.")
""",
    r"""# RES274_CELL: 07_REGENERATE_CANONICAL_DATASET
if DATASET_ROOT.exists():
    raise FileExistsError(f"refusing to reuse existing dataset directory: {DATASET_ROOT}")
subprocess.run(
    [
        str(VENV_PYTHON),
        "-m",
        "powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting",
        "--output",
        str(DATASET_ROOT),
        "--manifest",
        str(DATASET_ROOT / "manifest.json"),
    ],
    cwd=REPO_DIR,
    check=True,
)
print(f"DATASET_ROOT={DATASET_ROOT}")
qualification = subprocess.run(
    [
        str(VENV_PYTHON),
        "-m",
        "powerlifting_state_research.models.train_temporal_expert",
        "inspect",
        "--dataset-root",
        str(DATASET_ROOT),
        "--code-sha",
        CODE_SHA,
    ],
    cwd=REPO_DIR,
    check=True,
    capture_output=True,
    text=True,
)
DATASET_QUALIFICATION = json.loads(qualification.stdout)
print(json.dumps(DATASET_QUALIFICATION, indent=2, sort_keys=True))
""",
    r"""# RES274_CELL: 08_VERIFY_FROZEN_PROTOCOL
protocol_manifest = json.loads(
    (REPO_DIR / "artifacts/training-protocols/public-native-temporal-expert.json").read_text(
        encoding="utf-8"
    )
)
if protocol_manifest["training_protocol_id"] != DATASET_QUALIFICATION["TRAINING_PROTOCOL_ID"]:
    raise RuntimeError("committed training protocol does not match dataset qualification")
if DATASET_QUALIFICATION["seeds"] != [383001, 383002, 383003]:
    raise RuntimeError("the committed protocol does not declare exactly the frozen three seeds")
if (
    DATASET_QUALIFICATION["internal_selection_split_id"]
    != protocol_manifest["protocol"]["internal_selection_split_id"]
):
    raise RuntimeError("the TRAIN-internal split differs from its committed identity")
if DATASET_QUALIFICATION["fit_count"] != protocol_manifest["protocol"]["internal_fit_row_count"]:
    raise RuntimeError("the committed fit row count differs from dataset qualification")
if (
    DATASET_QUALIFICATION["selection_count"]
    != protocol_manifest["protocol"]["internal_selection_row_count"]
):
    raise RuntimeError("the committed selection row count differs from dataset qualification")
print(json.dumps(DATASET_QUALIFICATION, indent=2, sort_keys=True))
""",
    r"""# RES274_CELL: 09_PRODUCTION_TRAINING
subprocess.run(
    [
        str(VENV_PYTHON),
        "-m",
        "powerlifting_state_research.models.train_temporal_expert",
        "train",
        "--dataset-root",
        str(DATASET_ROOT),
        "--output-root",
        str(RUN_OUTPUT),
        "--runtime-receipt",
        str(RUNTIME_RECEIPT_PATH),
        "--code-sha",
        CODE_SHA,
    ],
    cwd=REPO_DIR,
    check=True,
)
""",
    r"""# RES274_CELL: 10_SEAL_ALL_SEED_CHECKPOINTS
seal = json.loads((RUN_OUTPUT / "receipts/checkpoint-seal.json").read_text(encoding="utf-8"))
expected_seeds = [383001, 383002, 383003]
if seal["declared_seeds"] != expected_seeds or not seal["all_seed_checkpoints_sealed"]:
    raise RuntimeError("checkpoint seal does not contain the exact frozen seed set")
if seal["canonical_validation_scored"]:
    raise RuntimeError("canonical validation was scored before the checkpoint seal")
for record in seal["seed_checkpoints"]:
    seed = record["training_seed"]
    checkpoint = RUN_OUTPUT / f"seed-{seed}/checkpoint.pt"
    checkpoint_manifest = json.loads(
        (RUN_OUTPUT / f"seed-{seed}/checkpoint-manifest.json").read_text(encoding="utf-8")
    )
    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if checkpoint_sha != checkpoint_manifest["checkpoint_sha256"]:
        raise RuntimeError(f"checkpoint hash mismatch for seed {seed}")
    print(
        f"seed={seed} best_internal_selection_epoch={record['best_internal_selection_epoch']} "
        f"selection_loss={record['best_internal_selection_loss']:.10g} "
        f"checkpoint_id={record['checkpoint_id']} checkpoint_sha256={checkpoint_sha}"
    )
print("ALL_SEED_CHECKPOINTS_SEALED=1")
""",
    r"""# RES274_CELL: 11_CANONICAL_VALIDATION
subprocess.run(
    [
        str(VENV_PYTHON),
        "-m",
        "powerlifting_state_research.models.train_temporal_expert",
        "evaluate-seeds",
        "--dataset-root",
        str(DATASET_ROOT),
        "--output-root",
        str(RUN_OUTPUT),
        "--runtime-receipt",
        str(RUNTIME_RECEIPT_PATH),
        "--code-sha",
        CODE_SHA,
    ],
    cwd=REPO_DIR,
    check=True,
)
""",
    r"""# RES274_CELL: 12_THREE_SEED_ENSEMBLE
subprocess.run(
    [
        str(VENV_PYTHON),
        "-m",
        "powerlifting_state_research.models.train_temporal_expert",
        "ensemble",
        "--dataset-root",
        str(DATASET_ROOT),
        "--output-root",
        str(RUN_OUTPUT),
        "--runtime-receipt",
        str(RUNTIME_RECEIPT_PATH),
        "--code-sha",
        CODE_SHA,
    ],
    cwd=REPO_DIR,
    check=True,
)
""",
    r"""# RES274_CELL: 13_TARGET_WISE_SUMMARY
subprocess.run(
    [
        str(VENV_PYTHON),
        "-m",
        "powerlifting_state_research.models.train_temporal_expert",
        "summary",
        "--output-root",
        str(RUN_OUTPUT),
    ],
    cwd=REPO_DIR,
    check=True,
)
""",
    r"""# RES274_CELL: 14_ARTIFACT_PERSISTENCE
required_directories = (
    "runtime",
    "training-protocol",
    "dataset",
    "split",
    "normalization",
    "seed-383001",
    "seed-383002",
    "seed-383003",
    "ensemble",
    "receipts",
)
missing = [name for name in required_directories if not (RUN_OUTPUT / name).is_dir()]
if missing:
    raise RuntimeError(f"run artifact persistence is incomplete: {missing}")
if USE_GOOGLE_DRIVE and not RUN_OUTPUT.is_relative_to(DRIVE_BASE.resolve()):
    raise RuntimeError("run output is not under the configured Google Drive root")
print(f"ARTIFACT_PERSISTENCE_ROOT={RUN_OUTPUT}")
print("Run artifacts are written directly to the configured durable root.")
""",
    r"""# RES274_CELL: 15_COMPRESSED_BUNDLE
subprocess.run(
    [
        str(VENV_PYTHON),
        "-m",
        "powerlifting_state_research.models.train_temporal_expert",
        "bundle",
        "--output-root",
        str(RUN_OUTPUT),
        "--bundle-path",
        str(BUNDLE_PATH),
        "--code-sha",
        CODE_SHA,
    ],
    cwd=REPO_DIR,
    check=True,
)
if not USE_GOOGLE_DRIVE:
    from google.colab import files

    files.download(str(BUNDLE_PATH))
""",
    r"""# RES274_CELL: 16_FINAL_VERIFIER
subprocess.run(
    [
        str(VENV_PYTHON),
        "-m",
        "powerlifting_state_research.models.train_temporal_expert",
        "verify",
        "--dataset-root",
        str(DATASET_ROOT),
        "--output-root",
        str(RUN_OUTPUT),
        "--bundle-path",
        str(BUNDLE_PATH),
        "--code-sha",
        CODE_SHA,
    ],
    cwd=REPO_DIR,
    check=True,
)
""",
)


def notebook() -> dict[str, object]:
    return {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "id": f"res274-cell-{index:02d}",
                "metadata": {"tags": [f"res274-cell-{index:02d}"]},
                "outputs": [],
                "source": source.rstrip("\n").splitlines(keepends=True),
            }
            for index, source in enumerate(SOURCES, start=1)
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = (json.dumps(notebook(), ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != content:
            parser.exit(1, "FAIL: RES-274 Colab notebook is stale or missing\n")
        print("PASS: generated RES-274 Colab notebook")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(content)
    print(OUTPUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
