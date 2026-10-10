# Methods and scientific limitations

## Evidence qualification

The starting checkout was clean and synchronized at main SHA 99a834721098d9953fd268dcdef5ce2177a490b0. The RES-278 and RES-281 audit bundle manifests were checked against every listed file, bundle digest, result-record pointer, result identity, record digest, serialized-record digest, and record-level input artifact hash. Each contains 126 records over nine versions and fourteen attack contracts. The RES-281 bundle hash is 0bbe5d58be59c8ba76fae1a9d6e4a116629b5c88fbdbfb32def6c4b9872bb597.

The RES-281 analysis manifest, source files, and output files were checksum-verified. RES-283 checksum-index and run-manifest hashes were verified, then its existing deterministic replay check was run. The audit runner read-only reconciliation and RES-283 deterministic replay both passed before publication. The publication index includes source hashes for every direct report, table, and figure dependency.

## Frozen IID analysis

Target-wise values and ranking order are carried from the RES-283 frozen CSV and existing EvaluationResult identities. The candidate unit is a fitted instance; expert seed instances and the separately identified ensemble are distinct candidates. The panel has seven model families, 22 candidate identities, three target QOIs, and 3,072 shared prediction keys under one IID DatasetRealization and one canonical RES-271 evaluation.

RMSE and MAE are in kilograms; R² and SRE(ddof=0) are unitless. RMSE, MAE, and SRE(ddof=0) minimize; R² maximizes. Ranks are target- and metric-specific, with exact ties handled in the source analysis. No cross-target aggregate rank is created.

Every chart is generated from a checksum-verified tracked table. Figures display point estimates, not uncertainty intervals. The target-wise table retains the source precision, fitted-instance/evaluation/prediction identities, ranks, and model-rights field. No target values or score values are entered by hand.

## Audit interpretation

RES-277 defines the six audit states: PASS, FAIL, INCONCLUSIVE, NOT_APPLICABLE, NOT_RUN, and UNSUPPORTED_BY_EVIDENCE. The RES-277 profile snapshot, RES-278 run, and RES-281 run are shown separately. Executed PASS/FAIL/INCONCLUSIVE states remain bounded to their named version, evidence, and protocol. NOT_RUN, NOT_APPLICABLE, and UNSUPPORTED_BY_EVIDENCE are not converted to negative or positive validity scores.

The RES-281 paired key/canary results apply to the repository inference adapter and registered comparator states. Plan swap, reversed history, and observation-noise diagnostics are limited to named synthetic interventions; their states remain INCONCLUSIVE. Their diagnostics do not establish broad distribution-shift robustness or real-athlete validity.

## Ranking and uncertainty limits

The 11/12 expert-ensemble lead count, metric reversals, seed ranks, and Pareto frontier describe frozen point estimates. They do not imply statistical significance or practical superiority. R² and SRE(ddof=0) are monotone transforms of RMSE on a fixed target evaluation population, so they do not add independent candidate ordering.

No observed pairwise ranking reversal occurs across the saved three-seed fit panel. The panel has only three distinct fits for temporal-expert and compact-neural; other families repeat deterministic outputs under seed labels. Dataset-seed, split-seed, distribution-shift, and out-of-sample ranking variability are not estimated. RES-281 model-ranking-instability and baseline-domination remain INCONCLUSIVE.

Tracked public inputs do not include validation target truth rows or the row-to-entity mapping. The planned 2,000-resample entity bootstrap was not run. All 264 candidate/target/metric uncertainty cells remain UNSUPPORTED_BY_EVIDENCE and inference INCONCLUSIVE.

## Historical comparison boundary

All 36 cross-version numerical comparisons remain REJECTED_FOR_NUMERICAL_COMPARISON. Eight historical versions lack public matched fitted-model/evaluation panels and common-evaluation paired evidence. Their within-version rankings and cross-version rank stability cannot be identified. Missing evidence does not demonstrate either a ranking change or stable rankings.

Design genealogy is descriptive. Chronology is not evidence of validity improvement, and this synthesis assigns no causal effect to a design change. The historical scrambled-Sobol and public-native IID DatasetSpecs differ; their raw scores are not directly ranked. Different benchmark designs could change model rankings in principle, but this report does not claim an observed cross-version effect.

## Rights and provenance

The repository public-file origin ledger and frozen result-manifest rights metadata were reviewed. The public-native temporal-expert source prediction-rights field remains NOASSERTION in the RES-283 model evidence. This publication retains that exact field and includes aggregate evaluation metadata only; source prediction JSONL and checkpoint bytes are not copied. Historical private rows, checkpoints, and outputs remain excluded. Repository presence is not treated as blanket redistribution permission.

## Future evidence requirements

The companion scientific-limitations table names the missing evidence needed for each stronger claim: validation truth and entity mapping for paired uncertainty; independent fit/data/split seeds and predeclared margins for broader stability; rights-cleared historical rows, adapters, common support, and the same fitted panel for historical comparisons; supported preregistered shift protocols for broader robustness; and a separate empirical validation design for real-athlete claims.

## Reproduction

Regenerate and verify this bundle with uv run --locked python -m powerlifting_state_research.audits.res284_publication and uv run --locked python -m powerlifting_state_research.audits.res284_publication --check. These commands only validate saved artifacts and create publication files.
