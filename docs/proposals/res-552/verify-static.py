"""Validate RES-552 documents and source bytes only; never import research code."""

import hashlib
import json
import subprocess
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASELINE = "b751cf4c9d44301b03861127ed94158d7c93fa3a"
PREFIX = "docs/proposals/res-552/"


def read(name):
    return json.loads((HERE / name).read_text())


def sha(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


p = read("draft-protocol.json")
b = read("baseline-files.json")
s = read("source-identities.json")
k = read("sentinel-keys.json")
assert p["baseline"] == b["baseline_commit"] == s["baseline_commit"] == BASELINE
assert git("rev-parse", BASELINE + "^{tree}") == b["baseline_tree"]
assert set(b["files"]) == set(git("ls-tree", "-r", "--name-only", BASELINE).splitlines())
for name, expected in b["files"].items():
    assert sha((ROOT / name).read_bytes()) == expected, name
# Catch removals, mode-only changes, and changes outside the proposal, too.
for line in git("diff", "--name-status", BASELINE).splitlines():
    fields = line.split("\t")
    assert fields[0] == "A" and fields[1].startswith(PREFIX), line
for line in git("ls-files", "--others", "--exclude-standard").splitlines():
    assert line.startswith(PREFIX), line
assert not p["execution_authorized"]
assert p["status"] == "DRAFT_NON_OPERATIVE"
assert p["phase_a_status"] == "NOT_RUN" and p["phase_b_status"] == "NOT_ADMITTED"
assert set(p["check_status"].values()) == {"NOT_RUN"}
assert p["required_authorization"] == "GO_FOR_G2_NUMERICAL_EXECUTION"
assert len(p["procedures"]) == 3
assert [x["id"] for x in p["procedures"]] == ["original", "candidate_L", "candidate_S"]
assert p["objective"]["priors"] is None
assert p["objective"]["penalized_terminal_eligible"] is False
assert p["cohort"]["noise_scales"] == [1, 2]

# Read selection metadata only. Never use assessments, truth or solver outcomes.
observations = (
    ROOT / "results/studies/target_sufficient_structural_reconstruction/observations.jsonl"
)
metadata = []
for line in observations.read_text().splitlines():
    row = json.loads(line)
    metadata.append(
        {
            name: row[name]
            for name in [
                "entity_id",
                "entity_index",
                "split",
                "history_template_by_lift",
                "declared_plan",
            ]
        }
    )
plans = p["cohort"]["plan_order"]
selected = []
for h in range(4):
    for plan_index in [h, (h + 1) % 4]:
        eligible = [
            row
            for row in metadata
            if row["split"] == "development"
            and row["history_template_by_lift"]["squat"] == h
            and row["declared_plan"] == plans[plan_index]
        ]
        assert len(eligible) == 2

        def key(row):
            digest = hashlib.sha256(
                (p["cohort"]["selection_prefix"] + row["entity_id"]).encode()
            ).hexdigest()
            return digest, row["entity_id"]

        row = min(eligible, key=key)
        assert row["entity_id"] == f"entity-{row['entity_index']:06d}"
        assert [row["history_template_by_lift"][lift] for lift in p["cohort"]["lifts"]] == [
            h,
            (h + 1) % 4,
            (h + 2) % 4,
        ]
        selected.append(
            {
                name: row[name]
                for name in [
                    "entity_id",
                    "entity_index",
                    "history_template_by_lift",
                    "declared_plan",
                ]
            }
            | {"selection_sha256": key(row)[0]}
        )
assert selected == k["entities"]
assert len({row["entity_id"] for row in selected}) == 8
assert [
    row["entity_id"]
    for row in sorted(selected, key=lambda row: (row["selection_sha256"], row["entity_id"]))[:2]
] == k["phase_b_entity_ids"]

r = p["resources"]
a, c = r["phase_a"], r["phase_b"]
assert a["cases"] == len(selected) * len(p["cohort"]["noise_scales"]) == 16
per_case = 4 * 3000 + 2 * 4 * 800 + 1400
for field in ["function_calls_per_case", "gradient_calls_per_case", "model_passes_per_case"]:
    assert per_case == a[field] == 19800, field
contract = r["hard_budget_contract"]
assert contract["phase_a_per_start_each"] == {
    "original": 3000,
    "candidate_L": 800,
    "candidate_S": 800,
}
assert contract["phase_a_diagnostics_per_case_each"] == a["diagnostics_per_case_calls"] == 1400
assert a["baseline_per_start_calls"] == p["procedures"][0]["maxfun"] == 3000
assert (
    a["candidate_per_start_calls"]
    == p["procedures"][1]["maxfun"]
    == p["procedures"][2]["external_max_calls"]
    == 800
)
assert a["starts_per_procedure"] == p["starts"]["count"] == 4
assert a["candidate_procedures"] == len(p["procedures"]) - 1 == 2
phase_a = per_case * 16
phase_b = 2 * 9 * (4 * 800 + 400)
for field in ["total_function_calls", "total_gradient_calls", "total_model_passes"]:
    assert a[field] == phase_a == 316800
    assert c[field] == phase_b == 64800
    assert r["combined"][field] == phase_a + phase_b == 381600
for section in [a, c, r["combined"]]:
    assert section["total_daily_transition_equivalents"] == section["total_model_passes"] * 840
assert a["total_wall_seconds"] == a["total_cpu_seconds"] == 7200
assert c["total_wall_seconds"] == c["total_cpu_seconds"] == 2160
assert r["combined"]["total_wall_seconds"] == r["combined"]["total_cpu_seconds"] == 9360
assert r["cpu_threads_including_blas"] == 1 and r["memory_bytes_process_tree"] == 2147483648
assert p["phase_b"]["grid_offsets_kg"] == [-10, -5, -2, -1, 0, 1, 2, 5, 10]
assert p["phase_b"]["coverage_claim"] is False
assert p["phase_b"]["primary_target"] == "squat.C_223_kg"
# Cross-document tables are rendered from the sole JSON budget authority.
table = "\n".join(
    [
        "| Counter | Per case | Phase A total | Daily-transition ceiling |",
        "| --- | ---: | ---: | ---: |",
        f"| Function | {a['function_calls_per_case']} | {a['total_function_calls']} | — |",
        f"| Gradient | {a['gradient_calls_per_case']} | {a['total_gradient_calls']} | — |",
        f"| Model passes | {a['model_passes_per_case']} | {a['total_model_passes']} "
        f"| {a['total_daily_transition_equivalents']} |",
    ]
)
for document in ["protocol-review.md", "review-checklist.md"]:
    prose = (HERE / document).read_text()
    rendered = prose.split("<!-- phase-a-budget-table -->\n")[1].split(
        "\n<!-- /phase-a-budget-table -->"
    )[0]
    assert rendered == table, document
    assert "19000" not in prose and "19,000" not in prose, document

alt = p["phase_b"]["near_optimal_alternative"]
error_rule = "max(tau_eval(reference),tau_eval(candidate))"
assert alt["per_vector_lower_bound"] == "ell_ref - " + error_rule
assert alt["per_vector_upper_bound"] == "ell_ref + 1e-4"
assert "For EACH i in {0,1}" in (HERE / "protocol-review.md").read_text()
assert "ONE immutable same-case Phase A" in (HERE / "review-checklist.md").read_text()
assert alt["max_reference_summed_nll_increase"] == 1e-4
assert alt["pairwise_only_comparison_allowed"] is False
assert p["phase_b"]["reference_improvement_stop"] == error_rule
assert alt["below_reference_action"].startswith("INCONCLUSIVE_REFERENCE")
assert alt["above_upper_bound_action"].startswith("REJECT_ALTERNATIVE")


def reference_band_status(reference, candidates, errors):
    # Toy decimal scalars test the guard only; no likelihood is evaluated.
    deltas = [Decimal(value) - Decimal(reference) for value in candidates]
    if any(delta < -Decimal(error) for delta, error in zip(deltas, errors, strict=True)):
        return "INCONCLUSIVE_REFERENCE"
    if any(delta > Decimal(str(alt["max_reference_summed_nll_increase"])) for delta in deltas):
        return "REJECT_ALTERNATIVE"
    return "QUALIFIED_BAND_ONLY"


assert reference_band_status("100", ["101", "100"], ["1e-8", "1e-8"]) == "REJECT_ALTERNATIVE"
assert reference_band_status("100", ["100", "101"], ["1e-8", "1e-8"]) == "REJECT_ALTERNATIVE"
assert reference_band_status("100", ["99.999", "100"], ["1e-8", "1e-8"]) == "INCONCLUSIVE_REFERENCE"
assert reference_band_status("100", ["100", "99.999"], ["1e-8", "1e-8"]) == "INCONCLUSIVE_REFERENCE"
assert (
    reference_band_status("100", ["99.99999999", "100.0001"], ["1e-8", "1e-8"])
    == "QUALIFIED_BAND_ONLY"
)

i = p["accepted_iterate_instrumentation"]
assert i["status"] == "NOT_RUN"
assert "NEW_X" in i["events"]["L-BFGS-B"]
assert "major-iteration" in i["events"]["SLSQP"]
assert "six checked states" in i["history"]
assert "INCONCLUSIVE_INSUFFICIENT_HISTORY" in i["early_termination"]
assert "BLOCKED_INSTRUMENTATION" in i["admission"]
assert "do not count" in i["duplicate_coordinates"]
n = p["normalizer_verification"]
assert n["status"] == "NOT_RUN"
assert n["procedure_A"]["domains"] == [
    ["0.4/0.71", "0.4/0.68"],
    ["0.4/0.68", "1/0.71"],
    ["1/0.71", "1/0.68"],
]
assert n["procedure_A"]["epsabs_per_piece"] == 1e-12 / 3
assert n["procedure_A"]["epsrel_per_piece"] == n["procedure_A"]["sum_error_estimates_max"] == 1e-12
assert n["procedure_A"]["limit_per_piece"] == 200
assert n["procedure_B"]["domain"] == [0.68, 0.71]
assert n["procedure_B"]["panel_counts"] == [1, 2, 4]
assert n["procedure_B"]["absolute_successive_difference_max"] == 1e-13
assert n["procedure_B"]["both_successive_differences_required"] is True
assert (
    n["cross_procedure_absolute_max"]
    == n["procedure_A_vs_original_absolute_max"]
    == p["tolerances"]["normalizer_absolute"]
    == 1e-12
)
receipt_text = (HERE / "verification-receipt.json").read_text()
assert not any(path in receipt_text for path in ["/home/", "/Users/", "/tmp/", "C:\\"])
assert all(
    not command.startswith("/")
    for command in read("verification-receipt.json")["verification_commands"]
)

assert set(s["documented_source_drift"]) == {"pyproject.toml", "uv.lock"}
for name, expected in s["execution_source_hashes"].items():
    if name not in s["documented_source_drift"]:
        assert sha((ROOT / name).read_bytes()) == expected, name
    else:
        assert (
            sha(
                subprocess.check_output(
                    ["git", "show", s["res289_execution_commit"] + ":" + name], cwd=ROOT
                )
            )
            == expected
        ), name
for name, expected in s["execution_artifact_hashes"].items():
    assert sha((observations.parent / name).read_bytes()) == expected, name


def canonical_digest(value):
    return sha(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )


assert (
    canonical_digest(s["execution_source_hashes"])
    == s["scientific_identities"]["source_set_digest"]
)
design = ROOT / "studies/target_sufficient_structural_reconstruction/protocol.json"
original_protocol = json.loads(design.read_text())
assert canonical_digest(original_protocol["protocol"]) == original_protocol["protocol_digest"]
original_split = json.loads((observations.parent / "split.json").read_text())
assert (
    canonical_digest(
        {name: original_split[name] for name in ["development_entity_ids", "test_entity_ids"]}
    )
    == original_split["split_digest"]
)

checksums = HERE / "proposal-checksums.json"
if checksums.exists():
    for name, expected in read("proposal-checksums.json")["files"].items():
        assert sha((HERE / name).read_bytes()) == expected, name
print(
    json.dumps(
        {
            "status": "PASS_STATIC_ONLY",
            "baseline_files": len(b["files"]),
            "sentinel_entities": len(selected),
            "phase_a_cases": a["cases"],
            "scientific_execution": "NOT_RUN",
            "independent_re_review": "NOT_RUN",
        },
        sort_keys=True,
    )
)
