"""RES-617: the mechanistic-use contract, its links and current-facing consistency."""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/science/g2-mechanistic-use-contract.md"
MEMO = ROOT / "docs/studies/g2-identifiability-decision.md"
CURRENT_FACING = [
    ROOT / "README.md",
    ROOT / "docs/README.md",
    ROOT / "docs/studies/index.md",
    ROOT / "docs/current-research-state.md",
]
NEGATIONS = re.compile(
    r"\b(not|no|unsupported|cannot|never|inconclusive|without|neither|nor|rather than|"
    r"does not|do not|did not|may not|unsupported)\b",
    re.IGNORECASE,
)
CLAIM = re.compile(
    r"(recover(s|ed|y)?|identif(y|ies|ied|ication)) .{0,60}"
    r"(individual|adaptation|suppression|16-parameter|physiological) .{0,30}parameter",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n", text) if s.strip()]


def test_contract_separates_permitted_from_unsupported_uses() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    permitted = text.split("## Permitted uses")[1].split("## Unsupported uses")[0].lower()
    unsupported = text.split("## Unsupported uses")[1].split("## M1 and M2")[0].lower()
    for topic in (
        "synthetic dynamical simulation",
        "hypothesis exploration",
        "forward-model sensitivity",
        "forecasting comparisons within validated",
    ):
        assert topic in permitted
    for topic in (
        "actual adaptation or suppression state",
        "nonstationary",
        "unique parameter recovery",
        "real-athlete training prescription",
        "causal",
    ):
        assert topic in unsupported
    assert "FULL_G2_IDENTIFICATION_UNSUPPORTED" in text
    m1 = text.split("## M1 and M2")[1].lower()
    assert "not evidence that adaptation parameters are biologically real" in m1
    assert "no demonstrated predictive advantage" in m1


def test_memo_and_contract_link_each_other_and_targets_exist() -> None:
    memo, contract = MEMO.read_text(encoding="utf-8"), CONTRACT.read_text(encoding="utf-8")
    assert "(../science/g2-mechanistic-use-contract.md)" in memo
    assert "(../studies/g2-identifiability-decision.md)" in contract
    for path in (MEMO, CONTRACT):
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", path.read_text(encoding="utf-8")):
            if not target.startswith("http"):
                assert (path.parent / target).resolve().exists(), f"{path.name}: {target}"
    for section in ("## 8. Mechanistic-use contract", "## 9. Remaining scientific limitations"):
        assert section in memo


@pytest.mark.parametrize("path", CURRENT_FACING, ids=lambda p: p.name)
def test_current_facing_documents_link_the_decision_and_make_no_recovery_claim(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "g2-identifiability-decision.md" in text
    for sentence in _sentences(text):
        if CLAIM.search(sentence):
            assert NEGATIONS.search(sentence), (
                f"unqualified mechanistic-recovery claim: {sentence!r}"
            )


def test_the_whole_documentation_tree_has_no_unqualified_recovery_claims() -> None:
    offenders = []
    skip = (
        "docs/studies/g4-reader-corrections-v1.md",
        "docs/science/g2-mechanistic-use-contract.md",  # lists the claims it forbids
        "docs/studies/g2-identifiability-decision.md",  # discusses them as unsupported
    )
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]:
        if path.relative_to(ROOT).as_posix() in skip:
            continue
        for sentence in _sentences(path.read_text(encoding="utf-8")):
            if CLAIM.search(sentence) and not NEGATIONS.search(sentence):
                offenders.append((path.name, sentence[:120]))
    assert offenders == []


def test_frozen_g2_evidence_was_not_modified_by_the_resolution() -> None:
    try:
        base = subprocess.check_output(
            ["git", "merge-base", "HEAD", "origin/main"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", base, "HEAD"], cwd=ROOT, text=True
        ).splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("origin/main is not available")
    frozen = (
        "results/studies/target_sufficient_structural_reconstruction/",
        "studies/target_sufficient_structural_reconstruction/",
        "results/studies/public_surrogate_reconstruction/",
        "results/studies/observation_inversion/",
        "studies/corrections/",
        "results/audits/",
    )
    assert [p for p in changed if p.startswith(frozen)] == []
