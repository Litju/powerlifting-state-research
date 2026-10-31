#!/usr/bin/env python3
"""Require a clean, parsed Gitleaks report for the reachable Git history."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITLEAKS_VERSION = "8.18.4"


class SecurityScanError(RuntimeError):
    """The Gitleaks scan or its JSON report is invalid or contains findings."""


def parse_gitleaks_report(report: str) -> int:
    try:
        findings = json.loads(report)
    except json.JSONDecodeError as error:
        raise SecurityScanError("Gitleaks produced invalid JSON") from error
    if not isinstance(findings, list) or any(not isinstance(item, dict) for item in findings):
        raise SecurityScanError("Gitleaks report must be a JSON array of findings")
    return len(findings)


def require_clean_gitleaks_report(report: str, exit_code: int) -> None:
    finding_count = parse_gitleaks_report(report)
    if finding_count:
        raise SecurityScanError(f"Gitleaks reported {finding_count} finding(s)")
    if exit_code:
        raise SecurityScanError("Gitleaks scan failed")


def verify_gitleaks() -> None:
    version = subprocess.run(["gitleaks", "version"], capture_output=True, check=False, text=True)
    if version.returncode or version.stdout.strip() != GITLEAKS_VERSION:
        raise SecurityScanError(f"Gitleaks {GITLEAKS_VERSION} is required")

    history = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        capture_output=True,
        check=False,
        cwd=ROOT,
        text=True,
    )
    if history.returncode or history.stdout.strip() != "false":
        raise SecurityScanError("full candidate history is required; shallow clones are rejected")

    with tempfile.TemporaryDirectory(prefix="psr-gitleaks-") as temporary_directory:
        report_path = Path(temporary_directory) / "report.json"
        result = subprocess.run(
            [
                "gitleaks",
                "detect",
                f"--source={ROOT}",
                "--log-opts=HEAD",  # All candidate ancestors, excluding unrelated branch histories.
                "--redact=100",
                "--report-format=json",
                f"--report-path={report_path}",
                "--exit-code=0",
                "--log-level=error",
                "--no-banner",
            ],
            capture_output=True,
            check=False,
            cwd=ROOT,
            text=True,
        )
        if not report_path.is_file():
            raise SecurityScanError("Gitleaks did not write its JSON report")
        require_clean_gitleaks_report(report_path.read_text(encoding="utf-8"), result.returncode)


def main() -> int:
    try:
        verify_gitleaks()
    except (OSError, SecurityScanError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: Gitleaks {GITLEAKS_VERSION} JSON report has zero findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
