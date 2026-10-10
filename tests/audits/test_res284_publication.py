from pathlib import Path

from powerlifting_state_research.audits.res284_publication import check_publication

ROOT = Path(__file__).resolve().parents[2]


def test_res284_publication_replays_with_verified_sources() -> None:
    check_publication(ROOT)
