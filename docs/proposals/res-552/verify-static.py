"""Validate RES-552 documents and source bytes only; never import research code."""

import hashlib
import json
import subprocess
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
assert per_case == a["function_calls_per_case"] == 19800
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
            "independent_review": "NOT_RUN",
        },
        sort_keys=True,
    )
)
