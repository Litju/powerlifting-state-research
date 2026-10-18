import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verify_res284_execution.py"
SPEC = importlib.util.spec_from_file_location("verify_res284_execution", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFIER
SPEC.loader.exec_module(VERIFIER)


def _write(root: Path, relative: str, content: bytes) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def test_corrupted_publication_bytes_fail(tmp_path: Path) -> None:
    index_bytes = b"execution-era index\n"
    relative = f"{VERIFIER.OUTPUT_DIR}/report.md"
    expected = b"original publication bytes\n"
    _write(tmp_path, VERIFIER.INDEX_PATH, index_bytes)
    _write(tmp_path, relative, expected)
    records = {relative: VERIFIER._digest(expected)}

    VERIFIER._verify_current_outputs(tmp_path, index_bytes, records)
    _write(tmp_path, relative, b"corrupted publication bytes\n")
    with pytest.raises(VERIFIER.VerificationError):
        VERIFIER._verify_current_outputs(tmp_path, index_bytes, records)


def test_missing_historical_source_evidence_fails(tmp_path: Path) -> None:
    records = {"src/powerlifting_state_research/source.py": VERIFIER._digest(b"source")}

    with pytest.raises(VERIFIER.VerificationError, match="missing evidence file"):
        VERIFIER._verify_hashes(tmp_path, records, "execution-era source")


def test_current_source_drift_is_reported_without_changing_historical_evidence(
    tmp_path: Path,
) -> None:
    historical = tmp_path / "historical"
    current = tmp_path / "current"
    old_ledger = b"path,origin\nold,source\n"
    _write(historical, VERIFIER.LEDGER_PATH, old_ledger)
    _write(current, VERIFIER.LEDGER_PATH, old_ledger + b"new,source\n")
    old_source = b"original analysis source\n"
    _write(historical, "src/analysis.py", old_source)
    _write(current, "src/analysis.py", b"updated analysis source\n")
    records = {
        VERIFIER.LEDGER_PATH: VERIFIER._digest(old_ledger),
        "src/analysis.py": VERIFIER._digest(old_source),
    }

    changes = VERIFIER._current_source_changes(current, historical, records)

    assert {path: state for path, state, _ in changes} == {
        VERIFIER.LEDGER_PATH: "APPENDED_AFTER_EXECUTION",
        "src/analysis.py": "CHANGED",
    }
