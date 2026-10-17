# RES-297 prediction provenance clarification

## Finding

The four tracked prediction files are outputs of the project’s RES-274 PUBLIC_NATIVE temporal-expert run. The generic `evaluate_files` evaluator accepts arbitrary precomputed prediction bytes, so it writes prediction-byte rights as `NOASSERTION` rather than assuming their owner. The frozen EvaluationResults preserve that fallback; their separate outer MIT field covers evaluation metadata. The origin ledger separately classifies each prediction artifact as MIT.

These records disagree about the outputs’ provenance. `NOASSERTION` is the evaluator’s historical fallback, not evidence of an identified third-party restriction. The current provenance evidence is that these files came from the project’s synthetic run.

## Verified outputs and origin

The local prediction bytes were SHA-256 checked against the original [RES-274 source inventory](../results/manifests/public-native-temporal-expert-source-inventory.json) and [run manifest](../results/manifests/public-native-temporal-expert.json). The original [verification receipt](../results/manifests/public-native-temporal-expert-verification-receipt.json) records `PASS` for run `20261008T071545Z-827f338c`, artifact-code SHA `6039f3a8ee685fe4254ab607b57df28ca38220f6`, verifier-code SHA `33e8dcecf49747314c182feb596dadb4527fbddd`, and bundle SHA `fa31764220dbca936275b07965e7b4b4adb146251fc38db063dc5e88de8eaec4`. The run manifest binds the outputs to model `psr:model:public-native-lift-shared-temporal-gru-capacity-change@1.0.0~34d23123138f` and synthetic IID realization `psr:dataset-realization:latent-capacity-transient-iid-production@sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad`. The [dataset card](../artifacts/dataset-cards/iid-latent-capacity-change-with-transient-expression-forecasting.md) and generator identify this as project-generated synthetic data, not real-athlete records.

| Artifact | SHA-256 |
| --- | --- |
| Ensemble | `f6fb260feac851845f584bcd96a290ec046234f78a7596221aba5453aecc006d` |
| Seed 383001 | `eb1bf322ba1783d0c70f59d13016421736fd6447c2f6827079f713d31332f50c` |
| Seed 383002 | `2373889b26646731eafc88907fada38aaf2982d0cfb464b7cfb4f728fb854e89` |
| Seed 383003 | `472fe8e81648672af3d93e17caaabe433026ab0d1725e384c370eb35f6d45944` |

The run lineage identifies no third-party dataset, pretrained model, or contract restricting these outputs, and no IPF or OpenPowerlifting input. The synthetic IID dataset is itself recorded as a project-generated CC-BY-4.0 artifact. The prediction MIT entries and dataset record name the same project contributor group. Authorization to distribute project-owned prediction outputs under MIT is distinct from the attribution requirements of the project-generated CC-BY-4.0 IID dataset; the dataset source, license, and attribution must remain identifiable. This is a provenance finding, not an independent legal ownership determination.

## Rights and GitHub scope

The existing origin ledger assigns MIT to all four outputs and names “Powerlifting State Research contributors.” The repository LICENSE names that collective as copyright holder. The GitHub repository owner (`Litju`) confirmed authorization for these exact outputs in [the PR #33 owner comment](https://github.com/Litju/powerlifting-state-research/pull/33#issuecomment-6228183282) on 2026-10-16. This records the project maintainer's confirmation; it is not independent third-party verification of copyright chain of title.

The four files are already in the public GitHub repository and included in GitHub-generated source archives. The authorized project maintainer recorded the following approval in PR #33 for that existing publication scope:

> I am authorized by the Powerlifting State Research contributors to confirm that the four prediction artifacts listed above may be distributed under MIT in the public GitHub repository and GitHub-generated source archives, with any required attribution to the project’s CC-BY-4.0 synthetic IID dataset.

The statement above was confirmed by the repository owner in PR #33 on 2026-10-16; its scope does not include model-weight distribution or a separate archival package. The three checkpoint files remain private and absent from Git; their existing hashes and original RES-274 integrity evidence remain in the existing manifests and receipt.

## Readiness boundary

- **PORTFOLIO_READINESS (RES-297 scope):** Rights/provenance confirmed for the four already-public prediction artifacts. The project remains subject to ordinary scientific, security, and CI checks. Checkpoint distribution, a DOI, archival packaging, and formal publication are not portfolio prerequisites.
- **FORMAL_ARCHIVAL_RELEASE:** Not qualified by this clarification; it remains a separate future decision.

The frozen EvaluationResults, scientific identities, synthetic-evidence limitations, and existing G1–G4 corrections are unchanged. This clarification does not claim unrelated research or formal-release gates have passed.
