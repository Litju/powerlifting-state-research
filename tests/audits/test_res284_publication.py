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


@pytest.mark.parametrize("damage", ["altered", "missing"])
def test_res284_verifier_rejects_altered_or_missing_files(tmp_path: Path, damage: str) -> None:
    relative = "results/audits/res284-publication/report.md"
    expected = b"original publication bytes\n"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(expected)
    records = {relative: VERIFIER._digest(expected)}

    VERIFIER._verify_hashes(tmp_path, records, "publication")
    if damage == "altered":
        target.write_bytes(b"altered publication bytes\n")
    else:
        target.unlink()

    with pytest.raises(VERIFIER.VerificationError):
        VERIFIER._verify_hashes(tmp_path, records, "publication")
