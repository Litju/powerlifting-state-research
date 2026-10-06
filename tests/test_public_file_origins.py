import csv
from pathlib import Path


def test_every_initial_file_has_an_origin_and_license_record() -> None:
    root = Path(__file__).resolve().parents[1]
    ledger = root / "provenance" / "PUBLIC_FILE_ORIGINS.csv"
    with ledger.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    paths = {row["path"] for row in rows}
    assert len(paths) == len(rows)
    assert len(rows) == 204
    assert all((root / path).is_file() for path in paths)
    assert all(row["origin_class"] for row in rows)
    assert all(row["license_expression"] in {"MIT", "CC-BY-4.0"} for row in rows)
    assert all(
        row["license_expression"]
        == ("CC-BY-4.0" if row["path"].endswith(".md") or row["path"] == "LICENSE-DOCS" else "MIT")
        for row in rows
    )
