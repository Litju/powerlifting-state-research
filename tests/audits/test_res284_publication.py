import hashlib
from pathlib import Path

import pytest

from powerlifting_state_research.audits import res284_publication as publication

ROOT = Path(__file__).resolve().parents[2]


def test_res284_publication_replays_with_verified_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    # Replay the frozen ledger source version while the live ledger grows by append only.
    ledger = ROOT / "provenance/PUBLIC_FILE_ORIGINS.csv"
    source = ledger.read_bytes()[:99236]
    expected = "sha256:e9fb6962b6447174e62498dc7d29359c75a3a8ea084b849b88acb584487328b9"
    assert "sha256:" + hashlib.sha256(source).hexdigest() == expected
    original_sha256 = publication._sha256

    def frozen_source_sha256(path: Path) -> str:
        return expected if path == ledger else original_sha256(path)

    monkeypatch.setattr(publication, "_sha256", frozen_source_sha256)
    publication.check_publication(ROOT)
