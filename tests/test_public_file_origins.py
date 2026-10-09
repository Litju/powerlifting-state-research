import csv
import subprocess
from pathlib import Path


def test_every_repository_file_has_an_origin_and_license_record() -> None:
    root = Path(__file__).resolve().parents[1]
    ledger = root / "provenance" / "PUBLIC_FILE_ORIGINS.csv"
    with ledger.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    paths = {row["path"] for row in rows}
    tracked = set(
        item.decode("utf-8")
        for item in subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
        ).split(b"\0")
        if item
    )
    assert len(paths) == len(rows)
    assert paths == tracked
    assert all((root / path).is_file() for path in paths)
    assert all(row["origin_class"] for row in rows)
    assert all(row["license_expression"] in {"MIT", "CC-BY-4.0"} for row in rows)
    for row in rows:
        parts = Path(row["path"]).parts
        public_audit_realization = (
            row["origin_class"] == "GENERATED_PUBLIC_ARTIFACT"
            and parts[:2] == ("results", "audits")
            and len(parts) > 4
            and parts[3] == "realizations"
        )
        expected = (
            "CC-BY-4.0"
            if row["path"].endswith(".md")
            or row["path"] == "LICENSE-DOCS"
            or public_audit_realization
            else "MIT"
        )
        assert row["license_expression"] == expected
