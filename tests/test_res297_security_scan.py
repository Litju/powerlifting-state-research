import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_res297_security_history import (  # noqa: E402
    SecurityScanError,
    parse_gitleaks_report,
    require_clean_gitleaks_report,
)


def test_gitleaks_json_findings_are_counted_and_blocking() -> None:
    assert parse_gitleaks_report("[]") == 0
    report = '[{"RuleID":"fixture","Secret":"[redacted]"}]'
    assert parse_gitleaks_report(report) == 1
    with pytest.raises(SecurityScanError, match="finding"):
        require_clean_gitleaks_report(report, 0)
    with pytest.raises(SecurityScanError, match="invalid JSON"):
        require_clean_gitleaks_report("not json", 0)
