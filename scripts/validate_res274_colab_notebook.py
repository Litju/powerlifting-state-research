"""Validate the committed RES-274 notebook as a thin, output-free execution driver."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/public-native-temporal-expert-colab.ipynb"
RUNNER = ROOT / "src/powerlifting_state_research/models/train_temporal_expert.py"
CELL_NAMES = (
    "CONFIG",
    "MANDATORY_DRIVE",
    "CLONE_EXACT_SOURCE",
    "GPU_ENVIRONMENT",
    "RUNTIME_RECEIPT",
    "DETERMINISTIC_RUNTIME",
    "REGENERATE_CANONICAL_DATASET",
    "VERIFY_FROZEN_PROTOCOL",
    "PRODUCTION_TRAINING",
    "SEAL_ALL_SEED_CHECKPOINTS",
    "CANONICAL_VALIDATION",
    "THREE_SEED_ENSEMBLE",
    "TARGET_WISE_SUMMARY",
    "ARTIFACT_PERSISTENCE",
    "COMPRESSED_BUNDLE",
    "FINAL_VERIFIER",
)


def validate(path: Path = NOTEBOOK) -> None:
    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid notebook JSON: {error}") from error
    if notebook.get("nbformat") != 4 or notebook.get("nbformat_minor", 0) < 5:
        raise ValueError("notebook must use nbformat 4.5 or later")
    cells = notebook.get("cells")
    if not isinstance(cells, list) or len(cells) != len(CELL_NAMES):
        raise ValueError("notebook must contain exactly the 16 ordered Gate-A cells")
    sources: list[str] = []
    for index, cell in enumerate(cells, start=1):
        if cell.get("cell_type") != "code":
            raise ValueError("all execution-driver cells must be code cells")
        if cell.get("execution_count") is not None or cell.get("outputs") != []:
            raise ValueError("committed notebook must have null execution counts and no outputs")
        source = cell.get("source")
        if not isinstance(source, list) or not all(isinstance(line, str) for line in source):
            raise ValueError(f"cell {index} has malformed source")
        text = "".join(source)
        marker = f"# RES274_CELL: {index:02d}_{CELL_NAMES[index - 1]}"
        if not text.startswith(marker):
            raise ValueError(f"cell {index} is out of order or missing marker {marker}")
        sources.append(text)
    all_source = "\n".join(sources)
    if any(
        marker in all_source
        for marker in (
            "USE_GOOGLE_DRIVE",
            "DRIVE_OUTPUT_ROOT",
            "DRIVE_BASE",
            "RUN_BASE",
            'Path("/content/powerlifting-state-research/res274")',
            "input(",
            "files.download",
        )
    ):
        raise ValueError("production notebook must require Drive without optional/local controls")
    if "RUN_OUTPUT.mkdir(" in sources[1]:
        raise ValueError("RUN_OUTPUT must remain absent until the runtime receipt is written")
    if 'REPO_DIR = Path("/content/powerlifting-state-research")' in all_source:
        raise ValueError("source checkout collides with the old output-root path")
    if 'DATASET_ROOT = Path("/content") / f"res274-iid-dataset-{RUN_ID}"' not in sources[1]:
        raise ValueError("canonical dataset must be regenerated at a separate ephemeral path")

    required_by_cell = {
        1: ('CODE_SHA = ""', 'RUN_ID = f"{datetime.now(UTC).strftime', "uuid.uuid4().hex[:8]"),
        2: (
            'drive.mount("/content/drive")',
            'DRIVE_MOUNT = Path("/content/drive")',
            'MY_DRIVE = DRIVE_MOUNT / "MyDrive"',
            "if not MY_DRIVE.is_dir()",
            'DRIVE_PROJECT_ROOT = MY_DRIVE / "powerlifting-state-research"',
            'RES274_DRIVE_ROOT = DRIVE_PROJECT_ROOT / "res274"',
            'RUNS_ROOT = RES274_DRIVE_ROOT / "runs"',
            'BUNDLES_ROOT = RES274_DRIVE_ROOT / "bundles"',
            "RUNS_ROOT.mkdir(parents=True, exist_ok=True)",
            "BUNDLES_ROOT.mkdir(parents=True, exist_ok=True)",
            "RUN_OUTPUT = RUNS_ROOT / RUN_ID",
            'BUNDLE_PATH = BUNDLES_ROOT / f"res274-{RUN_ID}.zip"',
            "if RUN_OUTPUT.exists() or BUNDLE_PATH.exists()",
            "NamedTemporaryFile(",
            "drive_probe.read_bytes() != drive_probe_payload",
            "drive_probe.unlink(missing_ok=True)",
            'print("DRIVE_PERSISTENCE=READY")',
        ),
        3: (
            'REPO_DIR = Path("/content/psr-src")',
            "git",
            "clone",
            "https://github.com/Litju/powerlifting-state-research",
            '"--detach", CODE_SHA',
            '"status", "--porcelain"',
            "REPO_DIR.resolve().is_relative_to(RES274_DRIVE_ROOT.resolve())",
        ),
        4: (
            '"sync", "--locked", "--all-groups"',
            '"--reinstall-package"',
            "https://download.pytorch.org/whl/cu128",
            "torch==2.9.1",
            "torch.cuda.is_available()",
            "VENV_PYTHON",
        ),
        5: (
            "dependency_fingerprint",
            "torch_cuda_version",
            "cudnn_version",
            "gpu_memory_bytes",
            "git_tree_status",
        ),
        6: (
            "configure_determinism",
            "declared_training_seeds",
            "cross_gpu_bitwise_guarantee",
        ),
        7: (
            "latent_capacity_change_with_transient_expression_forecasting",
            '"--output"',
            '"--manifest"',
            "DATASET_QUALIFICATION",
        ),
        8: (
            "public-native-temporal-expert.json",
            "TRAINING_PROTOCOL_ID",
            "DATASET_QUALIFICATION",
            "internal_selection_split_id",
            "internal_fit_row_count",
        ),
        9: ('"train"', "train_temporal_expert", "--runtime-receipt", "CODE_SHA"),
        10: (
            "checkpoint-seal.json",
            "383001",
            "383002",
            "383003",
            "ALL_SEED_CHECKPOINTS_SEALED=1",
        ),
        11: ('"evaluate-seeds"', "train_temporal_expert"),
        12: ('"ensemble"', "train_temporal_expert"),
        13: ('"summary"', "train_temporal_expert"),
        14: (
            '"runtime"',
            '"training-protocol"',
            '"dataset"',
            '"split"',
            '"normalization"',
            '"seed-383001"',
            '"seed-383002"',
            '"seed-383003"',
            '"ensemble"',
            '"receipts"',
            "RUN_OUTPUT.resolve().is_relative_to(RUNS_ROOT.resolve())",
            "BUNDLE_PATH.resolve().is_relative_to(BUNDLES_ROOT.resolve())",
        ),
        15: ('"bundle"', "BUNDLE_PATH", "BUNDLE_PATH.exists()"),
        16: (
            '"verify"',
            '"--drive-res274-root"',
            "RUN_OUTPUT.resolve().is_relative_to(RUNS_ROOT.resolve())",
            "BUNDLE_PATH.resolve().is_relative_to(BUNDLES_ROOT.resolve())",
            "REPO_DIR.resolve().is_relative_to(RES274_DRIVE_ROOT.resolve()) is False",
            "if not source_is_outside_drive",
            "not RUN_OUTPUT.is_dir() or not BUNDLE_PATH.is_file()",
            "CODE_SHA",
        ),
    }
    for index, required in required_by_cell.items():
        if any(text not in sources[index - 1] for text in required):
            raise ValueError(f"cell {index} is missing required Gate-A behavior")

    if not RUNNER.is_file() or "ALL_SEED_CHECKPOINTS_SEALED=1" not in RUNNER.read_text(
        encoding="utf-8"
    ):
        raise ValueError("notebook training/sealing entry point is missing")
    if "RES274_COLAB_RUN=PASS" not in RUNNER.read_text(encoding="utf-8"):
        raise ValueError("final repository verifier does not print its explicit PASS status")
    runner_source = RUNNER.read_text(encoding="utf-8")
    if any(
        marker not in runner_source
        for marker in (
            '"/content/drive/MyDrive/powerlifting-state-research/res274"',
            'Path("/content/psr-src")',
            "PUBLIC_NATIVE production artifacts must be written directly to Drive",
            "RUN_OUTPUT must be directly beneath the required Drive runs directory",
            "BUNDLE_PATH must be directly beneath the required Drive bundles directory",
            "bundle file differs from run artifact",
        )
    ):
        raise ValueError("repository verifier does not enforce Drive paths and bundle bytes")
    if any(marker in all_source for marker in ("ALI383", "ALI386", "inference_checkpoint.pt")):
        raise ValueError("notebook contains a historical checkpoint or adapter reference")
    if any(
        digest in all_source
        for digest in (
            "b41fd12298fffb44d86087198fbfec1151acef4f34d6446a8f40e249da1984fb",
            "6169d437ff152ecb75c5d3d9f2bc7b84d522d059e191faf10798bba8c81899a5",
            "7d2994106ae0ee33a44973f8550836ac099fdbf59c253d533da4f3c0424ad0c0",
        )
    ):
        raise ValueError("notebook embeds a historical checkpoint hash")
    if any(
        path_marker in all_source for path_marker in ("/home/", "/Users/", "/mnt/", "C:\\Users\\")
    ):
        raise ValueError("notebook contains a private or user-specific absolute path")
    secret_patterns = (
        r"sk-[A-Za-z0-9]{20,}",
        r"gh[pousr]_[A-Za-z0-9]{20,}",
        r"AIza[A-Za-z0-9_-]{30,}",
        r"(?i)Bearer\s+[A-Za-z0-9._-]{16,}",
    )
    if any(re.search(pattern, all_source) for pattern in secret_patterns):
        raise ValueError("notebook may contain an embedded credential or token")
    if "uv run" in all_source:
        raise ValueError("notebook must use the explicit environment Python after CUDA replacement")
    if any(
        marker in all_source
        for marker in ("torch.optim", "loss.backward(", "optimizer.step(", "for epoch in")
    ):
        raise ValueError("notebook must invoke repository training code, not implement training")
    if (
        "training_protocol_id" not in all_source.lower()
        or "RES274_COLAB_RUN=PASS" not in RUNNER.read_text(encoding="utf-8")
    ):
        raise ValueError("protocol verification or final run verifier is missing")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, default=NOTEBOOK)
    args = parser.parse_args()
    try:
        validate(args.notebook)
    except ValueError as error:
        parser.exit(1, f"FAIL: {error}\n")
    print("PASS: RES-274 Colab notebook structure and safety checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
