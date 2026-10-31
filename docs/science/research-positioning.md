# Mechanistic simulation and scientific machine learning

The contribution is a controlled synthetic forecasting and benchmark-validity case study. Its value is in explicit equations, participant information boundaries, distinct scientific identifiers, preserved unsuccessful hypotheses and inspectable software. It does not introduce a new physiological law, uncertainty estimator or generic calibration algorithm.

## Where mechanistic knowledge enters

| Component | Actual role | Supported description |
| --- | --- | --- |
| Synthetic dynamics and observation model | Generate hidden capacity, transient expression and noisy measurements | Mechanistic simulation with stated assumptions; no validation against human physiology |
| Mechanistic midpoint comparator and residual comparator | Use declared generator knowledge | Mechanistic and hybrid prediction baselines; not mechanism discovery |
| Shared temporal GRU | Learns from public histories, schedules and plans | Data-driven sequence forecasting; no physics residual or constrained optimizer |
| Conditional scale head H | Regresses a log-squared-error proxy and receives development-set scaling | Conventional heteroscedastic error-scale modeling; no identification of true physiological variance |
| Group scale G | Fixed shrinkage moment calibration on a new development cohort | Post-hoc group calibration; no conditional-coverage guarantee |
| Cessation truncation T | Conditions forecasts on nonpositive capacity change under zero dose | Source-law support restriction at inference; a bounded science-informed operation |
| H_GT | Combines G and T with the unchanged GRU location | Support-constrained probabilistic forecast; truncated distribution mean differs from GRU location |

The physics-informed machine-learning review by Karniadakis et al. discusses integration of physical knowledge and learning. That broad research context does not justify describing this GRU as a physics-informed neural network. Here the constraint is applied to a predictive distribution after training, only under a specified synthetic cessation law.

The three-seed mean is an ensemble of the same family. The seven-family comparison does not contain a trained cross-family stacking model or model-of-models. The evidence does not establish a need for one: the compared representations, budgets and hardware differ and ranking uncertainty is unsupported. Such a model would be a new experiment, not repository cleanup.

## Research references

- [Karniadakis et al. (2021), Physics-informed machine learning](https://doi.org/10.1038/s42254-021-00314-5): broad scientific context, not a claim of implemented PINN training.
- [Cho et al. (2014), Learning Phrase Representations using RNN Encoder–Decoder](https://aclanthology.org/D14-1179/): recurrent gating context; the implemented GRU architecture is specified in the [model card](../../artifacts/model-cards/public-native-temporal-capacity-change.md).
- [Gneiting and Raftery (2007), Strictly Proper Scoring Rules, Prediction, and Estimation](https://doi.org/10.1198/016214506000001437): proper scoring context for CRPS and logarithmic scores.
- [Gneiting, Balabdaoui and Raftery (2007), Probabilistic forecasts, calibration and sharpness](https://doi.org/10.1111/j.1467-9868.2007.00587.x): calibration and sharpness are distinct evaluation properties.
- [Kuleshov, Fenner and Ermon (2018), Accurate Uncertainties for Deep Learning Using Calibrated Regression](https://proceedings.mlr.press/v80/kuleshov18a.html): established regression-calibration context; this project uses a different fixed moment-scaling rule and inherits no conditional guarantee from that paper.
- [scoringRules normal-distribution documentation](https://search.r-project.org/CRAN/refmans/scoringRules/html/scores_norm.html): established normal and truncated-normal score families, distinct from censoring.

These references locate the methods in existing research; they do not constitute a systematic novelty review. The [naming record](../provenance/scientific-naming-decisions.md) explains why fitness–fatigue terminology was rejected for these capacity/expression equations. See the [study synthesis](../studies/probabilistic-capacity-forecasting.md) for empirical claims and limitations.
