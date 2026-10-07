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
    assert all(
        row["license_expression"]
        == ("CC-BY-4.0" if row["path"].endswith(".md") or row["path"] == "LICENSE-DOCS" else "MIT")
        for row in rows
    )
