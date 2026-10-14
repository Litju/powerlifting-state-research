# RES-509 — Independent release-audit preservation boundary

**Review baseline:** `de014231569442c7e83d1774877a8b92a9abc314` (RES-292 / PR #26).  
**Qualification:** `INCOMPLETE` — not a v1.0 release approval.

## Recovered evidence and limitations

The user supplied the **textual** independent release audit dated 2026-10-13. Its preserved text has SHA-256 `309c44d6d0ab088d4bc15247e2b354b08d4f74191a9079abd66eda66fda2a97e`. The text report is retained separately, **not distributed by this repository** pending public-content and provenance review.

The original auditor's 58-command execution ledger, independent G4 calculation script, full sensitivity tables, runtime receipts, history-scan logs, and audit artifact checksum index were not accessible during this RES-509 follow-up. Their status is `NOT_RECOVERED`, not `PASS`; the narrative's claims of independent replay cannot be re-certified from its text alone.

The public GitHub tree at the audit baseline has 615 tracked files, including **all 481 paths** enumerated in `studies/synthetic_pretraining_transfer/frozen-evidence.json`. Path existence is not a byte-for-byte verification. The new executable verifier below qualifies their hashes only when run from a Git checkout containing that baseline commit.

## Immutable material

The RES-292 source-evidence freeze covers 481 paths, including upstream source, prior G1–G3 studies, published RES-284 source and results, and temporal-expert artifacts. The study's original report, protocol, fitted states, sealed predictions, tables, figures, manifests, and SHA-256 index must also remain unchanged. Other result roots are covered by the release preservation verifier for the audit baseline.

| Original publication bundle | Tracked paths at baseline |
| --- | ---: |
| G1 — observation inversion | 14 |
| G2 — target-sufficient structural reconstruction | 28 |
| G3 — public-surrogate reconstruction | 37 |
| G4 — synthetic pretraining transfer | 39 |
| RES-284 — benchmark audit publication | 42 |

The 160 publication-path count includes study/result README files. It is a Git-tree inventory, not the number of manifest-listed experiment artifacts. The source version of `res284_publication.py` and the RES-284 checksum index are frozen dependencies of RES-292: fixing the current RES-284 verifier **in place** would invalidate the original G4 frozen-source check. Use a versioned release verifier and execution-era source resolution instead.

## Read-only validation and expected states

From a full-history clone, use:

```sh
python scripts/verify_release_freeze.py --baseline de014231569442c7e83d1774877a8b92a9abc314 --json-out ../psr-res509-freeze.json
```

The tool also verifies the original G4 manifest’s execution-time source SHA-256 records (including the protocol and learner source). It compares each recorded upstream SHA-256 to the corresponding Git object **at the baseline**, then independently compares every frozen upstream file and all five original publication directories to the candidate worktree. It fails on mutated/missing protected files, added files inside original publication directories, missing baseline objects, or mismatched frozen-manifest hashes. `NOT_RUN` means required Git evidence was unavailable; it is never accepted as a pass.

A successful preservation check is **not** an independent rerun of G1–G4 metrics, corrected G4 uncertainty, rights clearance, or release approval. Those remain separate release-qualification gates.

## Release-review handoff

- `RES-510`: independently adjudicate G4's crossed fitting-seed/held-out-entity uncertainty and publish corrected inference separately.
- `RES-511`: disclose the G4 nonzero-bias initialization deviation without changing executed learner weights.
- `RES-297`: resolve prediction/checkpoint rights and complete history/security qualification.
- `RES-298`: establish full research lock, real RES-284 source-version replay, and heavy release gates.
- `RES-299`–`RES-301`: scientific documentation, archive completeness, citation and v1.0 authorization.

Do not use this preservation receipt to claim any historical G1–G4 outcome was recovered. Do not merge a downstream PR without independent review of frozen-source compatibility.
