# RES-292 information boundary and estimands

## Study identity and scope

This is a new public-native synthetic experiment under G4's retrospective
study home. “Real” means held-out public rows sampled from the public-native
benchmark's original generating distribution. It never means human athletes.
The study estimates predictive behavior for three capacity-change targets in
kg, separately by lift, future horizon, held-out population, and fitting seed.

## Information roles

The Evaluation Authority uses the frozen public-native generator to create
fresh fitting, development, and two independent held-out populations. It
retains generator code, target truth, the split map, bootstrap donor keys, and
the teacher cross-fit map. The learner receives only the model arm's declared
training rows and their labels plus public development/test inputs without
targets. Training examples contain no source equations, hidden states,
population coordinates, exact support bounds, evaluation truth, authority-only
keys, or historical private material.

Predictions are serialized and SHA-256 sealed before the authority joins any
held-out truth. The isolated learner is first-party, imports NumPy and the
Python standard library only, and has procedural file, network, repository
import, and subprocess guards. This is a controlled-study firewall, not a
security sandbox for hostile code.

## Label provenance

Each synthetic input row is a complete copy of one original fitting donor,
with a fresh opaque synthetic row identity. There are two distinct label
sources:

| Label provenance | Meaning |
| --- | --- |
| ORIGINAL_PUBLIC_LABEL | Target attached to the original public fitting row |
| BOOTSTRAP_DUPLICATE_LABEL | Original public target copied together with its donor row |
| SURROGATE_PSEUDO_LABEL | Cross-fitted Summary Ridge prediction for the copied donor input |

The pseudo-label teacher uses the fixed RES-290-style 58-feature Summary Ridge
representation and alpha 100. In each plan-by-horizon cell, PCG64 seed 292190
permutes donor IDs; permuted position modulo four assigns the fold. Each fit
uses the other three folds and predicts the held-out fourth fold, so a donor's
own target is excluded from its teacher fit. No development or evaluation
target enters teacher fitting. Pseudo-labels are estimates, not
generating-distribution truth. The empirical bootstrap creates no new inputs
outside its finite donor records. No genuinely novel synthetic observations
or independently generated source-truth labels are used.

## Learner and matched arms

All arms share a fixed 58-input, three-output linear model with one bias per
output (177 trainable scalars), the same fixed participant-visible feature
map, initialization distribution, optimizer, learning rate, and batch size.
Input values use fixed unit scales; targets are divided by 10 kg during
optimization and restored to kg for evaluation. Each update uses the batch
mean squared error plus 0.5 × 1e-4 times the squared non-bias weight norm, with
gradient contribution 1e-4 × weight. Models use full-batch gradient
calculations on deterministic, seeded mini-batches of 32 rows. There is no
hyperparameter search, development-based model selection, or outcome-dependent
stopping. Development rows are prediction-only learning curve checks. A
pseudo-label-only student sees copied inputs and teacher outputs; its
supervision still derives from public training labels.

| Arm | Fit data | Updates | Public label exposure |
| --- | --- | ---: | ---: |
| PUBLIC_ONLY | Original public fitting rows | 128 | 4,096 row presentations |
| SYNTHETIC_ONLY_BOOTSTRAP | Donor-copy rows with BOOTSTRAP_DUPLICATE_LABEL | 128 | 0 |
| SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_BOOTSTRAP | 128 donor-copy pretraining updates, then 128 public fine-tuning updates | 256 | 4,096 row presentations |
| COMPUTE_MATCHED_PUBLIC_ONLY | Original public fitting rows | 256 | 8,192 row presentations |
| SYNTHETIC_ONLY_PSEUDOLABEL | Donor-copy inputs with SURROGATE_PSEUDO_LABEL | 128 | 0 direct presentations |
| SYNTHETIC_PRETRAIN_PUBLIC_FINETUNE_PSEUDOLABEL | 128 pseudo-label pretraining updates, then 128 public fine-tuning updates | 256 | 4,096 row presentations |

For each fitting seed, PUBLIC_ONLY and both fine-tuned arms use the identical
public mini-batch sequence during their 128 public updates, so direct
public-label exposure is matched. COMPUTE_MATCHED_PUBLIC_ONLY matches the
256 learner optimizer updates used by pretraining plus fine-tuning; its
additional 4,096 public-label presentations are reported as an exposure
difference. This pair of controls separates a pretraining contrast at equal
public-label exposure from a contrast at equal learner-update budget. The
pseudo-label arms are a distinct secondary treatment; teacher fitting and
pseudo-label construction compute are separately counted.

## Evaluation and decisions

Predictions are evaluated on independent test_population_a and
test_population_b. The protocol freezes RMSE, MAE, and signed bias in kg for
each target, lift, horizon, population, and fitting seed. Exact per-row
predictions and residuals are retained. The 95% percentile interval resamples
held-out entities with replacement within each plan and horizon, pairing the
same entity draws across arms. The pooled contrast also resamples fitting
seeds before entities. Duplicate bootstrap rows are never counted as
independent entities.

The practical RMSE margin is 1.0 kg. For the paired delta (treatment minus
control), an interval entirely below -1.0 kg is a resolved practical benefit;
entirely above +1.0 kg is resolved harm; entirely inside [-1.0, +1.0] kg is
practical equivalence; all other intervals are INCONCLUSIVE. This threshold is
fixed before fitting.

Finite-support diagnostics report donor counts, duplicate-draw fraction,
exact donor-copy fraction, visible-record overlap, plan/horizon coverage,
sample-extrema gaps, nearest-donor distances, and synthetic-label to held-out
target discrepancy. These finite-sample diagnostics do not estimate true
population support. Failure to resolve a contrast is retained as
INCONCLUSIVE, not converted into a null effect or proof that all synthetic
pretraining is ineffective.

Predictive utility, synthetic-only learning, incremental pretraining value,
compute-matched transfer, finite-support memorization, source-target
distribution discrepancy, structural equivalence, and real-world transfer
remain distinct. No result identifies the source system, estimates a causal
training effect, establishes structural equivalence, or transfers to real
athletes.
