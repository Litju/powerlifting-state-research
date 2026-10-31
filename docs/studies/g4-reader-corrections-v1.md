# Synthetic-pretraining transfer: reader corrections v1

This separately identified current reader notice accompanies the frozen [RES-292 public-native report](../../results/studies/synthetic_pretraining_transfer/public-native/report.md). It corrects navigation and the cell denominator, and directs readers to the immutable RES-510/511 evidence. It does not amend the original report, protocols, scientific identities, predictions, fitted states, or numerical results. Historical G4 metadata and this new public-native experiment remain separate.

## Editorial corrections to the original report

The original introductory protocol and lineage links are one directory level short. Correct destinations are the [frozen protocol](../../studies/synthetic_pretraining_transfer/protocol.json) and [historical lineage](../../studies/synthetic_pretraining_transfer/historical-lineage.md).

The sentence “18 predeclared lift/horizon cells per population” has the wrong denominator. There are three lifts × three horizons = **9 cells per population; 18 combined across populations A and B per contrast**. Six contrasts give 108 pooled cells. The original status table already sums to nine in each population row; no count or numerical table is changed here.

The original no-argument reproduction instruction creates immutable outputs and rejects an already populated checkout. Use the [current verification guidance](../reproducibility.md#study-verification-and-fresh-generation); `--check` verifies existing artifacts through in-memory replay.

## RES-510 · Pooled uncertainty correction

**Proposed inferential replacement; independent scientific approval pending.** Read the versioned [interpretation](../../studies/corrections/RES-510-v1/interpretation.md), [methods](../../studies/corrections/RES-510-v1/methods.md), and exhaustive [comparison table](../../results/corrections/RES-510-v1/comparison.csv). The original bootstrap resampled held-out entities independently within resampled fitting seeds, although all fits share evaluation entities. The corrected crossed bootstrap preserves that shared dependence.

| Interpretation across all 108 pooled cells | Equivalence | Inconclusive | Benefit | Harm |
| --- | ---: | ---: | ---: | ---: |
| Original published pooled | 98 | 9 | 1 | 0 |
| Corrected primary 95% percentile, assumption-qualified | 97 | 10 | 1 | 0 |
| Corrected after frozen Monte Carlo guard | 97 | 11 | 0 | 0 |
| Fixed-five-fit conditional after Monte Carlo guard | 99 | 8 | 1 | 0 |

The primary-percentile result and its guarded decision are distinct. The population-B deadlift/56-day bootstrap-pretraining contrast against PUBLIC_ONLY retains percentile benefit but becomes inconclusive under the Monte Carlo guard. Its fixed-five-fit conditional result retains benefit and answers a different question about those five fits. The population-A deadlift/56-day pseudo-label-pretraining equivalence becomes inconclusive. Point predictions and ΔRMSE are unchanged.

Against COMPUTE_MATCHED_PUBLIC_ONLY, the primary bootstrap-pretraining guarded counts are 17 equivalence and 1 inconclusive over 18 cells: no demonstrated >1 kg advantage within this design. This does not prove that all synthetic pretraining is ineffective. The guard controls numerical Monte Carlo approximation, not family-wise scientific error. Scientific intervals remain approximate per-cell intervals; five fits do not establish random-seed population coverage, and inference is conditional on the original fitting data and upstream synthetic/teacher realization.

## RES-511 · Initialization deviation

The frozen specification requires normal weights and **zero output biases**. The learner instead draws the entire `(59, 3)` matrix from `N(0, 0.01)`, including its last-row biases. All six arms share the same start within each of five seeds, but the executed learner differs from the frozen zero-bias specification. Read the [versioned erratum](../../studies/corrections/RES-511-v1/interpretation.md), [deviation record](../../studies/corrections/RES-511-v1/deviation-record.json), and [initial-bias table](../../results/corrections/RES-511-v1/initial-biases.csv).

No result estimates the unexecuted zero-bias learner or the effect of this deviation. RES-510 applies to the fitted instances actually executed and does not restore protocol conformity. The deviation is confirmed by source and records; independent scientific approval remains pending, and no scientific release approval is asserted. RES-509 remains the recorded scientific-review dependency.

## Evidence and rights

The immutable [RES-510 manifest](../../results/corrections/RES-510-v1/manifest.json) and [RES-511 manifest](../../results/corrections/RES-511-v1/manifest.json) bind the correction evidence. This notice is project-authored CC BY 4.0 documentation; underlying per-artifact notices still apply. See the [verification record](../res299-validation.md) for checks performed without regenerating studies.
