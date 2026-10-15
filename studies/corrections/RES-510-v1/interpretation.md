# RES-510 v1 — G4 inferential correction

**Status: proposed inferential replacement; external scientific approval pending.**
RES-509 remains open, PR #27 remains draft, and scientific v1.0 remains NO-GO.

All 108 pooled cells are included once. Every original point estimate, published interval,
decision and scientific identity is retained in [comparison.csv](../../../results/corrections/RES-510-v1/comparison.csv).
All 324 separately identified 50,000-replicate runs are in [bootstrap-runs.csv](../../../results/corrections/RES-510-v1/bootstrap-runs.csv).
The exact method was frozen before the complete campaign; see [methods.md](methods.md).

## Exhaustive classification comparison

| Classification track | Equivalence | Inconclusive | Benefit | Harm |
| --- | ---: | ---: | ---: | ---: |
| Original published pooled | 98 | 9 | 1 | 0 |
| Primary corrected 95% percentile, assumption-qualified | 97 | 10 | 1 | 0 |
| Corrected after frozen Monte Carlo guard | 97 | 11 | 0 | 0 |
| Fixed-five-fit conditional after Monte Carlo guard | 99 | 8 | 1 | 0 |

## Changed scientific classifications

These are changes in the Monte Carlo guarded, assumption-qualified per-cell classification.
The ordinary primary 95% percentile classification remains separately visible.

| Cell and contrast | ΔRMSE kg | Original 95% / status | Corrected primary 95% / percentile status | Final guarded status |
| --- | ---: | --- | --- | --- |
| test_population_a / deadlift / 56d / SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL vs PUBLIC_ONLY | -0.888168482 | [-0.973756048, -0.794375720] PRACTICAL_EQUIVALENCE | [-1.035626335, -0.723571211] INCONCLUSIVE | INCONCLUSIVE |
| test_population_b / deadlift / 56d / SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP vs PUBLIC_ONLY | -1.253587263 | [-1.389616413, -1.107255401] PRACTICAL_BENEFIT | [-1.472792861, -1.004156470] PRACTICAL_BENEFIT | INCONCLUSIVE |

## Primary bootstrap-pretraining conclusion

Bootstrap-pretraining comparisons against PUBLIC_ONLY and COMPUTE_MATCHED_PUBLIC_ONLY
are distinct primary contrasts; the pseudo-label arm remains a separate secondary analysis.

Against PUBLIC_ONLY: 18 cells; guarded statuses {'PRACTICAL_EQUIVALENCE': 13, 'INCONCLUSIVE': 5}.

Against COMPUTE_MATCHED_PUBLIC_ONLY: 18 cells; guarded statuses {'PRACTICAL_EQUIVALENCE': 17, 'INCONCLUSIVE': 1}.

There is no demonstrated >1 kg primary bootstrap-pretraining advantage over the
compute-matched control in these cells. This preserves the bounded absence of evidence
for load-bearing pretraining beyond equal compute; it does not prove universal failure.

Population B / deadlift / 56d has ΔRMSE −1.253587263 kg against PUBLIC_ONLY,
but +0.058763639 kg against COMPUTE_MATCHED_PUBLIC_ONLY. Its first crossed interval
against PUBLIC_ONLY narrowly ends below −1 kg. The predeclared Monte Carlo guard
prevents calling the random-fit conclusion resolved. The fixed-five-fit conditional
track retains benefit for this cell and answers a different conditional question.

Population A / deadlift / 56d pseudo-label pretraining has ΔRMSE −0.888168482 kg
against PUBLIC_ONLY. Shared evaluation-entity dependence widens its interval across
the −1 kg boundary, so the previously published equivalence classification does not
survive. This is secondary pseudo-label inference, not a primary bootstrap result.

## Monte Carlo stability and inferential limits

For the two changed cells, run-specific endpoint and outer Monte Carlo bounds are:

| Cell | Run | 95% interval kg | MC outer envelope kg | Percentile status | Guard status |
| --- | --- | --- | --- | --- | --- |
| test_population_a / SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL | primary-510001 | [-1.035626335, -0.723571211] | [-1.050101445, -0.700230764] | INCONCLUSIVE | INCONCLUSIVE |
| test_population_a / SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL | stability-510002 | [-1.034350326, -0.724195955] | [-1.049950255, -0.700255763] | INCONCLUSIVE | INCONCLUSIVE |
| test_population_a / SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL | stability-510003 | [-1.034867638, -0.724120798] | [-1.051164619, -0.701464765] | INCONCLUSIVE | INCONCLUSIVE |
| test_population_b / SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP | primary-510001 | [-1.472792861, -1.004156470] | [-1.495469271, -0.969798126] | PRACTICAL_BENEFIT | INCONCLUSIVE |
| test_population_b / SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP | stability-510002 | [-1.474832634, -1.000275220] | [-1.498512056, -0.965027489] | PRACTICAL_BENEFIT | INCONCLUSIVE |
| test_population_b / SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP | stability-510003 | [-1.471430483, -1.001141965] | [-1.495705047, -0.967638030] | PRACTICAL_BENEFIT | INCONCLUSIVE |

The simultaneous .01 error bound controls Monte Carlo approximation across bootstrap
CDFs, not scientific multiplicity. All scientific intervals remain approximate per-cell
95% intervals, with no simultaneous family-wise superiority claim across 108 dependent
comparisons. Five fits do not establish exchangeability or adequate training-seed tail
support; nominal random-seed population coverage remains INCONCLUSIVE even for stable
labels. The correction is conditional on the original fitting data and upstream
synthetic/teacher realization, with no inference over fresh training datasets.

No model training, GPU experiment, parameter tuning, benchmark redesign, private
historical access, original artifact edit, RES-511 work, release/tag or DOI occurred.
Original numerical artifacts are retained as execution authority; pooled inferential
labels are proposed as superseded for inference only, pending independent scientific
approval. The complete-model old-commit replay would retrain and is NOT_RUN; original
post-seal point and bootstrap inference replay is executed instead. Rights, environment,
archival and release qualification remain separate blockers.
