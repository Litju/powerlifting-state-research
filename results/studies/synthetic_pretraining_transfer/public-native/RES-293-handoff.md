# RES-293 scientific handoff

RES-292 is a separate NEW_PUBLIC_NATIVE_EXPERIMENT, not a recovery of the
historical G4 result. Its protocol is psr:study:synthetic-pretraining-transfer-public-native@1.0.0~e6209a7185e8
with digest sha256:e6209a7185e826e4b041c7b2aac7b313ae10cc98d83496db5edb528fc20d1e96. The new realization
is psr:dataset-realization:synthetic-pretraining-transfer-public-native@sha256:2162e1085cdd11c5c054b51c410f6ad82882e1739098e3838d486fe912666396.

## Evidence handed off

- 384 empirical bootstrap records were drawn from
  241 unique public fitting donors
  (duplicate fraction 0.372). These copies
  contain BOOTSTRAP_DUPLICATE_LABEL values and are not independent entities.
- A separate donor-copy dataset carries cross-fitted Summary Ridge predictions
  labeled SURROGATE_PSEUDO_LABEL. Those are conditional predictions; they are
  not generating-distribution truth. No novel source-supported rows or
  independently generated source-truth labels were created.
- ORIGINAL_PUBLIC_LABEL rows, held-out truths, donor mappings, and teacher
  folds are retained as distinct artifacts. The learner firewall sealed
  predictions before test scoring.
- Per-seed and pooled entity-paired effects, fit identities, target-wise
  metrics, learning curves, and update/data-exposure accounting are in the
  linked study report and artifact manifest.

The predeclared bootstrap transfer status counts are:

| Contrast | Population | Benefit cells | Harm cells | Equivalent cells | Inconclusive cells |
| --- | --- | ---: | ---: | ---: | ---: |
| SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP − PUBLIC_ONLY | test_population_a | 0 | 0 | 7 | 2 |
| SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP − PUBLIC_ONLY | test_population_b | 1 | 0 | 6 | 2 |
| SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP − COMPUTE_MATCHED_PUBLIC_ONLY | test_population_a | 0 | 0 | 9 | 0 |
| SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP − COMPUTE_MATCHED_PUBLIC_ONLY | test_population_b | 0 | 0 | 8 | 1 |

See [the RES-292 report](report.md),
[paired-transfer-effects.csv](paired-transfer-effects.csv),
[evaluation-results.csv](evaluation-results.csv),
[finite-support-summary.json](finite-support-summary.json), and
[compute-accounting.csv](compute-accounting.csv) for the bound evidence.
The issue's result remains conditional on this fixed learner, support,
realization, and practical margin. A positive result against PUBLIC_ONLY alone
does not establish benefit beyond the compute-matched public-only arm. An
inconclusive or nonbeneficial result does not establish that every synthetic
pretraining method is ineffective.

## Open question for RES-293

If RES-293 tests a source with genuinely novel synthetic support, it must
identify the authorized source of every synthetic label, freeze support and
target-generation rules before fitting, and preserve independent held-out
populations. It should reuse equal-public-label and equal-compute controls,
entity-clustered paired uncertainty, and explicit distinctions between
predictive utility, source-target mismatch, source identification, causal
effects, and real-athlete transfer. This file is a handoff only. RES-293 and
RES-294 remain unchanged, and this handoff executes neither issue.
