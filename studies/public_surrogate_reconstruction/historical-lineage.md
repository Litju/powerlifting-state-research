# Surviving historical G3 evidence

## Identity and purpose

The surviving registry entry names “Public-surrogate reconstruction; retrospective study.” Its aliases are G3 / ALI-543 and pl_study_g3_public_surrogate. The entry classifies it as a research study, not a benchmark version. The historical-source registry attaches the G3 alias to the latent-capacity benchmark specimen alongside G0–G4.

These are metadata findings. They do not recover G3's original question, protocol, participants, methods, model identities, outputs, or results. The old result-home README explicitly says no historical report or result artifact is reproduced. Its “PROVEN” bootstrap label describes repository classification and is not scientific evidence.

## Evidence classification

| Claim or artifact | Classification | Surviving public source | Limit |
|---|---|---|---|
| Study name, retrospective purpose, study-home slug, G3 and ALI-543 aliases | HISTORICALLY_VERIFIED metadata | studies registry entry in src/powerlifting_state_research/studies/registry.py | Does not establish an executed study |
| G3 alias attached to the historical latent-capacity benchmark | HISTORICALLY_VERIFIED provenance metadata | attached_audit_aliases in src/powerlifting_state_research/provenance/historical_sources.py | Does not establish G3-specific methods or results |
| Historical study and result homes contain no G3 report or result bundle | HISTORICALLY_VERIFIED repository state at starting main | studies/public_surrogate_reconstruction/README.md and results/studies/public_surrogate_reconstruction/README.md | Absence from the public home is not evidence of success or failure elsewhere |
| Parent benchmark semantics and participant-visible contract | HISTORICAL_REPORTED public projection | M2–M5 benchmark and data contracts listed in frozen-evidence.json | Parent contracts are assumptions for this new study, not recovered G3 methods |
| Original G3 protocol, dataset bytes, learner, fitted model, predictions, evaluation, uncertainty, or numerical results | UNSUPPORTED_BY_EVIDENCE | No rights-cleared G3-specific artifacts survive in the public study/result homes | No historical experiment is reconstructed or rescored |
| RES-290 results in this directory | NEW_PUBLIC_NATIVE_EXPERIMENT | Protocol, realization, fit, evaluation, and manifest named in results/studies/public_surrogate_reconstruction/manifest.json | Independent study; not historical reproduction |

The G3-specific historical references recovered here are the registry aliases and parent benchmark attachment; no original G3 issue, protocol, or report link survives in the public study home. Handoff context is available in [RES-287](https://linear.app/alignerr-cmj/issue/RES-287/publish-observation-inversion-and-latent-state-observability) and [its public PR #22](https://github.com/Litju/powerlifting-state-research/pull/22), [RES-289](https://linear.app/alignerr-cmj/issue/RES-289/publish-structural-reconstruction-and-system-identification-study) and [its public PR #23](https://github.com/Litju/powerlifting-state-research/pull/23), and the current [RES-290 issue](https://linear.app/alignerr-cmj/issue/RES-290/publish-public-surrogate-reconstruction-study). RES-289's RES-290 handoff asks that RES-290 keep prediction, state observability, parameter identifiability, and causal identification separate. RES-287's handoff states that G1's original measurements and methods are absent. Neither handoff supplies historical G3 outcomes.

No historical G3 score is compared with the new public-native results. Historical private code, data, model weights, reports, and Git objects are not inputs.

## Lineage used for this study

RES-287 is an independent public-native observation-inversion experiment. Its G1 home retains metadata but no historical quantitative result. Its study identity is psr:study:observation-inversion-public-native@1.0.0~906ce39f2a2c and its protocol digest is sha256:906ce39f2a2ca296b35fa2ea97d5ca1eed033bb3b675f9da186aafc434dfdda9.

RES-289 is an independent public-native structural-reconstruction experiment. Its G2 home retains metadata but no historical quantitative result. Its study identity is psr:study:target-sufficient-structural-reconstruction-public-native@1.0.0~12aafcbac716, its protocol digest is sha256:12aafcbac716350e46002178918fe1ee08f65c2f76167368f7ed6cb4a8e0f405, and its realization is psr:study-realization:target-sufficient-structural-reconstruction-public-native@sha256:345de0028b7beeefdc355bf7112565bad2d5675e5bbed3a5c5901371436b5af1.

These identities and the exact source-file hashes are frozen in frozen-evidence.json. Their scores are not inputs, targets, baselines, or comparators for RES-290.
