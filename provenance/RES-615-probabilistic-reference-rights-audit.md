# RES-615 rights audit and route decision

**Decision: Route B.** The original numerical M10–M12 probabilistic components cannot be redistributed on the recorded permissions, so RES-615 builds a new public reference that does not reproduce them. This is a record-based provenance assessment, not legal advice. It decides access, use, modification and redistribution separately for each artifact. A matching checksum, a local file, the repository MIT license or project ownership does not by itself establish any of them.

## What was checked

- The only public redistribution grant for model bytes is [`model-artifact-redistribution.md`](model-artifact-redistribution.md). It names three RES-274 GRU checkpoints, 30 RES-293 fitted states and their listed training metadata. It states that it "grants no rights in any historical or third-party material".
- The [normalization clarification](normalization-and-rights-clarification.md) states the grant "does not extend to private uncertainty coefficients or group factors".
- The [public probabilistic study summary](../docs/studies/probabilistic-capacity-forecasting.md) and the [reproduction table](../docs/reproducibility.md#public-and-restricted-reproduction) mark fitted H parameters, group factors, scoring adapters, cohorts and scenario evidence as restricted.
- The private original run indexes were inspected locally for rights labels. They label the GRU "owner-cleared" and the evidence and outputs "private". No retained record grants the H, c, G, adapter, prediction or cohort files any public license. Some records use a generic "MIT" shorthand for dataset rights; the artifact-specific dataset record is CC-BY-4.0, and the shorthand is not relied upon.
- No private bytes, parameters, factors or predictions were copied into this repository.

## Per-artifact decision

| Artifact | Access | Use | Modification | Redistribution | Decision |
| --- | --- | --- | --- | --- | --- |
| Three RES-274 GRU checkpoints (SHA-256 pinned in the protocol) | public | yes | not needed | yes, MIT, named in the 2026-10-22 owner authorization | **Reused** |
| RES-274 normalization statistics (actual file bytes) | public | yes | not needed | yes, MIT artifact entry; frozen summary-hash conflict preserved | **Reused** |
| Public generator source | public | yes | not needed | yes, MIT | **Reused** with new seeds |
| Canonical IID dataset rows | public, CC-BY-4.0 with attribution | not needed | n/a | n/a | Not used |
| New FIT / CAL_C / CAL_G / TEST cohorts | regenerated from frozen seeds | yes | n/a | rows not committed; aggregate outputs only (MIT) | **Generated at runtime** |
| Original H and H_GT ridge coefficients and standardization | private | no public use | none | no grant | **Excluded** |
| Original B1 scales, development c multipliers, G factors | private | no public use | none | no grant (not named in the authorization) | **Excluded** |
| Original scoring, prediction and generator adapters | private | no public use | none | no grant; contain transient source paths | **Excluded** |
| Original cohorts, truth, predictions, evaluations, receipts | private | no public use | none | no grant | **Excluded** |
| Linear snapshots, independent audit, review dossier | private | no public use | none | no grant | **Excluded** |
| Public methods and aggregate summary | public (CC-BY-4.0) | citation | frozen | already public | Referenced only |

## Route decision

Route A needs positive rights for the fitted parameters and exact historical scoring identities. They are not recorded, so Route A is not available. No effort is spent recovering them.

Route B uses only cleared bytes: the three released GRU checkpoints and normalization statistics, and the public generator. It reimplements the publicly documented procedures independently and mints a new identity. All identities, seeds and constants are frozen in [`protocol.json`](../results/references/public-probabilistic-latent-capacity-change-v1/protocol.json) before any scientific run.

## Differences from the original program

The new reference is not a reproduction of the original studies' results.

- Fresh cohorts and seeds: different rows, so no original score, coefficient or factor is expected to match.
- Independent implementation of the public equations, written without access to the private adapters.
- Four roles (FIT, CAL_C, CAL_G, TEST) of the documented sizes; the B0 baseline, the controlled-shift scenarios and the paired bootstrap are not run.
- Original GRU outputs were produced on GPU; this reference is CPU-only, within the recorded RES-274 CPU tolerance.
- The truncation rule is applied only to the cessation plan of the simulated latent capacity change.

The reference identity must never be used for historical M11 or M12 scores, and original evidence digests must never be attached to its outputs.
