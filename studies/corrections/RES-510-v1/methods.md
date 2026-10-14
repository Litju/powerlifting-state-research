# RES-510 v1 — Corrective statistical method

This is a post-seal inference correction of RES-292, conditional on the original
fitting data, upstream synthetic/teacher realization and sealed fitted states.
No model, target, training seed, dataset or margin is changed. RES-509 remains
open and preservation PR #27 remains draft. Final scientific qualification and
external scientific approval are pending.

## Estimand and dependence

For each of the 108 population × lift × horizon × treatment/control cells, preserve

\[
\widehat\Delta={1\over5}\sum_{s=1}^{5}
\left[\sqrt{{1\over128}\sum_{i=1}^{128}e_{Tsi}^2}
-\sqrt{{1\over128}\sum_{i=1}^{128}e_{Csi}^2}\right]\quad\text{kg}.
\]

Each cell has 128 distinct held-out entities, 32 in each of four intervention plans.
Keep their observed equal plan weights. The estimand averages five individual fitted
pair performance differences; it is neither an ensemble-prediction score nor an RMSE
of errors pooled over seeds. All five paired fits share exactly the same held-out
entities. Treatment/control pairing uses the same fit-seed label and evaluation row.
Horizons, targets, populations and contrasts are never pooled.

The original nested procedure resamples a different entity sample for every selected
seed occurrence. It therefore loses shared entity covariance across fits. This can
understate uncertainty with positive cross-fit entity covariance, but it need not
always understate variance. A change in classification alone cannot validate a remedy.

## Chosen procedures, frozen before execution

The primary crossed/product bootstrap independently samples five paired seed indices
with replacement and a single common entity sample with replacement within each plan.
Every selected seed occurrence and both arms use that entity sample. Recompute the
seed-specific RMSE differences and average them, retaining the original point estimate.
This preserves fitting-seed and shared entity variation in their observed crossed layout.
The [pigeonhole bootstrap](https://arxiv.org/abs/0712.1111) provides the basis for
resampling the two factors separately. It does not establish exact finite-sample
coverage for this nonlinear statistic with only five seed fits.

A separate fixed-five-fit conditional bootstrap uses the same entity draws but averages
all five original fitted pairs without seed resampling. It estimates entity-sampling
uncertainty conditional on these exact models. It does not represent hypothetical
training-seed uncertainty. The primary random-seed interpretation additionally assumes
exchangeability of the five fit pairs over the declared initialization/training
randomness, conditional on the fixed training data and synthetic/teacher construction.
Consecutive numerical seed labels do not themselves establish that assumption.

Each cell/track has three independently identified 50,000-replicate runs. PCG64,
cell-seed derivation, whole-array draw order, plan order and row ordering are frozen
in [analysis-specification.json](analysis-specification.json). Intervals use linear
2.5%/97.5% quantiles and the original ±1 kg practical margin. Negative differences
favor treatment. Benefit requires upper < −1; harm requires lower > +1; equivalence
requires lower ≥ −1 and upper ≤ +1; all other cases are INCONCLUSIVE.

Monte Carlo precision is separate from statistical coverage. A DKW empirical-CDF
bound with family error probability .01, union-bounded over 648 bootstrap CDFs,
gives epsilon = sqrt(log(2×648/.01)/(2×50000)). Outer percentile bounds use lower
and higher order statistics at p−epsilon and p+epsilon; ordinary 95% endpoints
retain linear interpolation. A practical status is retained only when all three
percentile statuses and all three outer-envelope statuses agree. Otherwise the
corrected status is INCONCLUSIVE. Primary-run percentile classification and final
Monte Carlo guarded classification are both published; no adaptive resampling or
selection of a favorable run occurs. This bound concerns simulation randomness
only, not 99% scientific coverage or multiplicity adjustment for scientific effects.

## Alternatives and limitations

The decision was made from sampling design before the complete corrected campaign,
with an outcome-blind independent agent method review. A preexecution amendment
replaced interpolated Monte Carlo bounds with outer order statistics after that
review identified the ECDF inversion issue; its old/new hashes and freeze time are
in [method-freeze.json](method-freeze.json).

Entity-only conditioning is defensible but answers a different question. Seed-only
resampling omits entity uncertainty. Seed-level t intervals condition on observed
evaluation data and need additional distributional assumptions. Crossed influence
functions, variance-component or parametric bootstraps require assumptions and
unstable component estimation with five seeds. BCa/studentization with only five
seed units does not automatically solve that problem. Leave-one-seed-out summaries
are fragility diagnostics rather than calibrated intervals.

Under a smooth linearized crossed-effects model, product resampling can inflate
interaction variance. The [multiway bootstrap analysis](https://arxiv.org/abs/1106.2125)
supports approximate variance behavior under stated conditions, not a guaranteed
conservative 95% percentile interval here. The usual entity-bootstrap asymptotics assume independent, exchangeable entities
within each fixed plan, positive MSE and finite fourth error moments for the RMSE
linearization. Crossed-factor asymptotics also need a growing seed factor under
appropriate main-factor conditions; increasing entities with five fixed seeds
cannot establish random-seed consistency. These are coverage assumptions and
limitations, not additional resampling choices or a coverage claim. Only five fitted pairs provide weak information about
training-seed tails; increasing bootstrap replication cannot add seed information.
Nominal random-seed coverage qualification remains INCONCLUSIVE. No uncertainty
about new fitting datasets, teachers or synthetic realizations is identified.

The 108 scientific intervals are per-cell; neither their agreement nor two control
comparisons establish simultaneous family-wise superiority. No universal, causal,
real-athlete, source-identification or structural-equivalence claim is supported.

## Reproduction and preservation commands

Use a full-history checkout, CPython 3.12.13 and NumPy 2.4.4, with an existing
validated environment. The numerical scripts need NumPy and Git; repository-wide
checks additionally use the existing development/test dependencies. The recorded
repository environment contains SciPy outside the lock and is not pure-lock approval.
Run from the repository root; choose receipt locations outside every Git worktree.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/res510_correct_inference.py --check
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/verify_res510_correction.py --root . --json-out ../res510-verification.json
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_res510_correction.py tests/test_res510_verifier.py
.venv/bin/python scripts/verify_release_freeze.py --baseline de014231569442c7e83d1774877a8b92a9abc314 --json-out ../res510-preservation.json
```

Omitting `--check` regenerates only the separately versioned correction outputs.
It never generates data, refits models or writes into original study/result homes.
`SHA256SUMS.txt` indexes all numerical outputs and their manifest; the manifest also
binds every original input and supporting specification, implementation, tests and
prose source. The qualification receipt binds numerical verification, command/log
hashes, environment and original-file preservation. Verification checks all rows
and intervals, rather than treating hashes or a successful test suite as science.
