# Conditional uncertainty and support-constrained capacity forecasting

This is an owner-authorized public methods and aggregate-claims summary of completed synthetic research. It is newly authored documentation, not a redistribution of private reports or evidence. The underlying numerical audit is private; a public clone can inspect these methods but cannot reproduce the reported probabilistic scores. See [reproduction levels](../reproducibility.md#public-and-restricted-reproduction), [rights clarification](../../provenance/normalization-and-rights-clarification.md), and the [technical provenance appendix](#technical-provenance).

## Question and information boundary

Can an unchanged temporal GRU point forecast be supplemented with more useful predictive distributions, without confusing aggregate score improvement with conditional reliability? The [system equations](../science/system-model.md) define latent capacity and transient expression. The three-lift target is capacity change from day 223 to days 237, 251 or 279. Histories end at day 223. Plans are cessation, step-down, continuation and step-up. Twelve plan/horizon strata each contain 256 test entities; each independent test cohort has 3,072 entities with three paired lift outcomes.

The original three-seed GRU, train-only normalization and 127 participant-visible summary features stay fixed. No true capacity, time constants, latent coordinates, future observations or entity identifiers are predictor features. [Public algorithms and models](../models/reference-models.md) and [research references](../science/research-positioning.md) give the architectural context. These studies contain no trained cross-family stacking model.

## Methods

**Point-correction failures.** A fixed cessation/56-day bias correction failed its 3% RMSE-improvement screen on both new test cohorts: mean gains were −0.068% and −0.100%. A subsequent fixed visible-history Ridge residual correction also failed, with 0.393% and 0.756% gains; only one of three lifts improved on the first test. A retained engineering restart preserved the original fit cohort. These negative results concern the tested procedures, not impossibility of any future correction. Retrospective error decomposition found scale-dominated errors but did not prove irreducibility or heteroscedasticity.

**Conditional scale H.** For each lift, regress

$$t=\log((y-\mu)^2+0.25^2)$$

on 140 fit-standardized features: the original 127 visible summaries, that lift's GRU location $\mu$, and 12 plan/horizon indicators. Use an unpenalized intercept and Ridge penalty $0.05\|\beta\|^2$ on the mean squared regression loss. The 12,288-row fit cohort alone supplies coefficients and feature means/population standard deviations, with a $10^{-6}$ scale floor. Set raw $\sigma=\operatorname{clip}(\exp((b+z\beta)/2),0.25,100)$ kg. This is a log-error proxy, not identification of true conditional variance.

B0 uses a per-lift fit residual RMS; B1 uses plan/horizon/lift RMS. For each method and lift independently, a new 3,072-row development cohort supplies

$$c=\operatorname{clip}\left(\sqrt{\operatorname{mean}_{DEV}((y-\mu)^2/\sigma_{raw}^2)},0.25,4\right),\quad
\sigma=\operatorname{clip}(c\sigma_{raw},0.25,100).$$

Thus the supported unit is the entire fitted and calibrated H procedure. No ablation isolates history's contribution from the location, group indicators and calibration. Raw H nominal 90% coverage was approximately 74%; development scaling brought it to approximately 91%. Gaussian distributions still assigned impossible positive capacity-change mass under cessation.

**Group calibration G and truncation T.** A separate new development cohort supplies exactly 36 group/lift factors. With $R=\operatorname{mean}((y-\mu)^2/\sigma_H^2)$, $n=256$ and $\kappa=256$,

$$g=\operatorname{clip}\left(\sqrt{(nR+\kappa)/(n+\kappa)},0.70,1.40\right),\quad
\sigma_{HG}=\operatorname{clip}(g\sigma_H,0.25,100).$$

T conditions the Gaussian on $y\leq0$ only under cessation. For $a=-\mu/\sigma$, its CDF is $\Phi((y-\mu)/\sigma)/\Phi(a)$ on that support and 1 above zero; density above zero is exactly zero. It is truncation, not censoring or a boundary atom. Its mean is $\mu-\sigma\phi(a)/\Phi(a)$, so the retained GRU location is **not the truncated predictive mean**. G and T do not change the separately scored point forecast. The fixed six-arm panel is B1, B1_T, H, H_T, H_G and H_GT. No winner was selected using the later test outcomes.

**Evaluation.** CRPS in kg and negative log density in nats per observation are lower-is-better scores. Macro scores equally average per-lift means; kg-scale differences remain. Each distribution uses its own CDF and quantiles for PIT and central 50/80/90% intervals. Joint three-lift calibration is untested. The [reference toy tests](../../tests/test_probabilistic_reference_formulas.py) check displayed Gaussian and upper-truncated formulas against independent CDF integrals. They are mathematical examples, **not the private scoring implementation or numerical study replay**.

## Same-law results and negative findings

| Procedure comparison | First independent test | Second independent test | Interpretation |
| --- | --- | --- | --- |
| Calibrated H versus B1 macro CRPS gain | 2.7485% | 2.9636% | Full calibrated procedure; all three lifts improved |
| H versus B1 step-down/14 bench CRPS worsening | 2.65% | 5.23% | Aggregate success includes local regressions |
| H_GT versus H macro CRPS gain | 0.3582% | 0.3133% | Small improvements on two subsequent same-law tests |
| H_GT minus H macro NLL | −0.020874 | −0.019728 | Lower log loss; unchanged separate point errors |
| H_GT versus H step-down/14 bench CRPS gain | 4.0817% | 3.7540% | G drives this contrast because T is inactive here |
| H_GT versus H group/lift CRPS regressions | 6/36 | 8/36 | No universal subgroup improvement |
| H_GT nominal 90% pooled coverage | 90.6901% | 90.7118% | Pooled coverage is not conditional calibration |

The conditional-scale study and subsequent six-arm calibration study passed their original pragmatic screens. H_GT still overcovers at nominal 50% and 80%. Reweighting existing test rows by plan mixture improved CRPS by 0.4165%/0.3718%, but this is a different estimand on the same rows, not a novel cohort or distribution-shift simulation. Neither same-law study supplied a bootstrap confidence claim.

## Controlled shifts

All fitted GRU, H, B1 and G parameters were frozen. Two fresh independent test **parents** each supplied three paired scenarios: IID control, extra velocity noise and altered adaptation-time-constant population density. These are six dependent scenario sets from **two parents**, not six independent replications.

- Extra velocity noise adds independent Gaussian noise with the original per-lift observation standard deviation to velocity alone. Net conditional velocity noise standard deviation becomes $\sqrt{2}$ times the original under the construction. Targets are byte-identical to paired controls; other intended inputs are unchanged.
- Adaptation shift maps exactly the three normalized adaptation coordinates from $u$ to $\sqrt{u}$ before the original parameter mapping. Other 13 coordinates, dynamical equations, measurement law and support remain unchanged. Since $\tau=-28/\log(1-(0.15+0.75u))$, larger mapped coordinates yield **shorter** time constants. True parameters are never features.

| Parent/scenario | H_GT macro CRPS (kg) | H_GT minus H CRPS (kg) | H_GT pooled 90% coverage |
| --- | --- | --- | --- |
| A / IID | 1.29709945 | −0.002631386 | 90.3103% |
| A / velocity noise | 1.34444498 | −0.003033227 | 89.6810% |
| A / adaptation timescale | 1.42781697 | −0.010477093 | 88.2053% |
| B / IID | 1.26971612 | −0.003876393 | 91.3628% |
| B / velocity noise | 1.31993375 | −0.004067711 | 90.5816% |
| B / adaptation timescale | 1.40290993 | −0.011669248 | 88.6719% |

H_GT retained favorable relative CRPS against H and B1 and passed the frozen heuristic screen in all four required shifted evaluations. That screen requires CRPS ≤1.01 H and ≤B1, NLL excess ≤0.03 nats, pooled 90% coverage within 85–95% with comparator deviation excess ≤2 percentage points, exact cessation support and verified shifts. These margins do not define formal noninferiority or equivalence.

**Absolute forecasts worsen under both shifts.** Adaptation-shift H_GT CRPS rises about 10% from each paired IID control. Nominal 90% conditional coverage falls to **208/256 = 81.25%** for A step-up/14 squat and **203/256 = 79.296875%** for B step-up/28 squat. Other groups overcover, reaching 97.65625%/95.3125%. Adaptation-shift H_GT versus H has 4/36 and 6/36 CRPS regressions and 12/36 and 10/36 NLL regressions. Pooled success partly hides opposing subgroup behavior. Conditional reliability is not established.

A 2,000-draw paired bootstrap per parent resamples 256 entities within each of 12 strata, sharing draws across three lifts, methods and scenarios. All six scenario-specific H_GT−H descriptive 95% intervals exclude zero favorably; both velocity difference-in-differences intervals include zero. These intervals condition on fixed fitted methods, the selected questions and the generator. They omit fitting/development uncertainty, training-seed variation and program-wide selection, and provide no simultaneous conditional coverage.

## Claims and reproduction matrix

| Claim | Evidence status | Public inspection / numerical access |
| --- | --- | --- |
| Public dynamics, information boundaries and point metrics | Executable public source and tests | Public full clone; locked environment |
| Three-seed GRU and representation fits | Authorized original bytes, identities and loading checks | Public; CPU/GPU tolerance applies to original GRU replay |
| H and H_GT relative proper-score gains | Private saved-data audit, bounded same-law findings | Public method/aggregate summary; raw numerical replay restricted |
| Robustness under two named supported shifts | Private paired evaluation; pragmatic screen retained | Public definitions and limits; raw scenarios/adapters restricted |
| Exact nonpositive cessation support | Mathematical consequence of truncation under the synthetic law | Public equations and reference toy tests; private experiment implementation excluded |
| Conditional reliability | Not established; repeated undercoverage and overcoverage | Negative finding retained explicitly |
| Cross-family trained stacking, new generic estimator, true variance identification | Not established | No such public model or supporting ablation |
| Universal OOD, real-athlete validity, physiological identification | Unsupported | No corresponding experiment |
| Immutable preregistration or adversarial first-truth-access guarantee | Not established | Recorded code/seal chronology only |
| Independent external human peer review | Not performed | Engineering and internal computational audit are separate |

## Technical provenance

Historical phase aliases M10, M11 and M12 identify respectively conditional uncertainty, group calibration/support restriction and controlled shifts. They are retained here solely to reconcile original evidence. Scientific source commit: `b751cf4c9d44301b03861127ed94158d7c93fa3a`. Original GRU ID: `psr:model:public-native-lift-shared-temporal-gru-capacity-change@1.0.0~34d23123138f`. No new canonical model or realization identifier is minted for this documentation summary.

| Evidence index | SHA-256 of original index file | Access |
| --- | --- | --- |
| Conditional-scale experiment | c38c8952fc5308892d77323a12ba20c1215144dee13ca5c2ddabfe3e3230e4bf | Restricted |
| Group calibration and support experiment | 74ff10e1694dcd2f8cd055e1f40975ce1f121280c71c6f17de5b818d6c4b0536 | Restricted |
| Controlled-shift experiment | c801305e704c72e7c5b18da0bfa102a3b3bde2f5c5267e5644b3ef8c1cdd9284 | Restricted |
| Independent internal computational audit | 236f29a32645fcce56af758bf35e041d22c26749eaf5ab6dd3fd70003a92f75b | Restricted |
| Methodological-review dossier | d5d38fba90ccb5500a649b633fa2b95dd558c4a429834e8d4364212358a2af1f | Restricted |

The audit reports reconciliation of 702 conditional-scale, 504 calibration and 1,404 shift score cells, both bootstraps and all 589,824 velocity perturbations. This integration rechecks evidence preservation; it does not claim a new full numerical replay. Full original cohort/evaluation identifiers, all six-arm cells and negative findings remain in private manifests/audit tables. Hashes provide identity, not downloadable public evidence or redistribution permission.

The owner authorized this new public methods/aggregate summary in the repository closeout request; earlier private-package restrictions remain applicable to the original artifacts. Source bytes, fitted parameters, original reports and indexes are unmodified. Generic private MIT-for-dataset shorthand does not override the canonical dataset's CC BY 4.0 terms. Historical adapters depend on transient source paths, so a portable one-command private replay is not available. Current issue timestamps and same-user file permissions cannot independently prove exact historical protocol versions or first truth access. Sequential hypotheses selected after earlier diagnostics remain selection-sensitive even when subsequently tested on new cohorts.
