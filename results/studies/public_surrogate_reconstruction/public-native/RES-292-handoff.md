# RES-292 scientific handoff

This is a handoff only. RES-292 was not executed.

RES-290 study: psr:study:public-surrogate-reconstruction-public-native@1.0.0~e71ab192551c
Protocol digest: sha256:e71ab192551cb8c80ad28402a11441546a94672bd72375f9f41b29dd86c5480e
Realization: psr:dataset-realization:public-surrogate-reconstruction-public-native@sha256:d6543d9fe0143d1fbb0134d6bb841b5e7c72cc01bc4a9e9901c632d574ac56ac
Realization digest: sha256:d6543d9fe0143d1fbb0134d6bb841b5e7c72cc01bc4a9e9901c632d574ac56ac
Evaluation: res290-public-surrogate-evaluation-v1

## Carried-forward evidence

- Historical G3 survives as metadata only: name, aliases, retrospective purpose, and parent-benchmark attachment. Original G3 protocol, rows, model, and quantitative results remain unsupported.
- RES-287 and RES-289 are separate public-native studies. Their outputs were read as lineage only and were not fit data, scoring truth, or historical score comparators.
- RES-290 enforces learner/authority separation with a strict stdin payload, no held-out targets, an isolated process, runtime guards, and entity-disjoint training/development/test populations.
- The empirical resampler generates donor copies. Summary Ridge and sequence RFF Ridge estimate conditional means and do not generate observable records.
- Matched plan response results apply only to authority-generated synthetic entities under declared plan support. No real-world causal or structural-equivalence claim follows.
- Sequence RFF had higher predictive RMSE than Summary Ridge in 27/27 paired cells (27 resolved); Summary Ridge was worse than the empirical mean in 9 cells and inconclusive in 18.
- The study did not demonstrate an observationally similar conditional-model pair with different response surfaces; that structural non-identification question remains inconclusive.

## Result pointers

- empirical_finite_support_resampler_v1 test-A per-lift/horizon RMSE values in kg: 3.258, 3.764, 4.725, 1.883, 3.632, 3.323, 3.973, 4.894, 6.063
- sequence_rff_ridge_v1 test-A per-lift/horizon RMSE values in kg: 6.636, 7.518, 9.397, 5.029, 6.671, 6.808, 9.118, 10.375, 10.939
- summary_ridge_v1 test-A per-lift/horizon RMSE values in kg: 3.432, 3.970, 5.845, 2.503, 3.811, 3.641, 4.092, 5.144, 6.286
- Predictive, matched-response, noise, support, and observable-distribution results are bound in the realization manifest and study report under results/studies/public_surrogate_reconstruction/public-native/.
- The G3 reconstruction did not identify the source generator. Observational similarity and predictive utility remain separate from structural equivalence and system identification.

## Suggested next boundary

If RES-292 studies whether surrogate families that agree on public observables can differ in internal response, predeclare a separate protocol, use new authority-matched held-out populations, keep source truth outside learner fitting, and treat observational similarity as an operational finite-sample criterion rather than proof of mechanism equivalence.
