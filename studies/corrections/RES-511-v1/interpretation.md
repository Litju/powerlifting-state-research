# RES-511 v1 — RES-292 initialization deviation erratum

**Status: historical execution deviation confirmed.** This erratum documents the
RES-292 public-native execution. It does not change the frozen protocol, learner,
predictions, fitted states, or metrics. RES-509 remains a blocking dependency;
scientific release qualification remains blocked.

## What the protocol specified and the learner executed

The frozen protocol specifies independent PCG64 draws from a normal distribution
with mean 0 and standard deviation 0.01 for the 58-by-3 weight matrix, with all
three output biases set to zero. It also specifies identical starts for the six
arms at each fitting seed.

The frozen learner calls `default_rng(fit_seed).normal(0.0, 0.01, size=(59, 3))`.
The 59th row is the three-output bias row, so its values were drawn from the same
normal distribution as the 58 weight rows. At a given seed, this complete matrix
is initialized before any arm-specific fitting and shared by the six arms.

The table gives the initial bias parameters in normalized target units (the
learner scales targets by 10 kg, so the equivalent initial output offsets in kg
are ten times these values).

| Fit seed | Squat bias | Bench press bias | Deadlift bias | Shared arms |
|---:|---:|---:|---:|---:|
| 292201 | 0.020983372923549896 | -0.002813681966121168 | -0.016008908525505683 | 6 |
| 292202 | 0.016504270989740073 | 0.02045264695978766 | 0.006937279225743331 | 6 |
| 292203 | 0.01449867791593493 | 0.005143104338477398 | -0.007726452010622767 | 6 |
| 292204 | 0.0048331481796608546 | -0.01089157664059558 | 0.011014555575501617 | 6 |
| 292205 | -0.0029663849315563324 | 0.009284113823082613 | -0.007894574603355723 | 6 |

The values and initialization-matrix digests were reconstructed with NumPy
2.4.4, `default_rng(seed)` / PCG64, and the frozen learner's `(59, 3)` draw.
The machine-readable [deviation record](deviation-record.json) binds each seed
to all six original fitted-instance IDs, identity digests, and fitted-state
hashes. The [result table](../../../results/corrections/RES-511-v1/initial-biases.csv),
[manifest](../../../results/corrections/RES-511-v1/manifest.json), and
[checksum file](../../../results/corrections/RES-511-v1/SHA256SUMS.txt) provide the
reproducible record and its integrity hashes.

## Bounded initialization and optimization audit

The audit compared the frozen protocol with the frozen learner and the 30
published fitted-instance records. It found no additional deviation in the
bounded initialization/optimization contract:

| Contract item | Executed evidence | Finding |
|---|---|---|
| Architecture | 58 inputs, three outputs, 177 parameters; final matrix row is bias | Conforms |
| Initialization | Normal `(59, 3)` draw, mean 0, standard deviation 0.01; seed is the fit seed | **Bias-row deviation** |
| Batch and objective | 32 rows sampled with replacement; mean squared error and `1e-4` weight-only L2 gradient | Conforms |
| Optimizer rate | Learning rate 0.01 | Conforms |
| Update budgets | 128 per single phase; 128 synthetic plus 128 public for fine-tuned arms; 256 for compute-matched public-only | Conforms across all 30 identities |
| Public mini-batches | Independent public RNG seeded by `fit_seed + 1,000,000`; same first 128 batches at each seed across public-only and fine-tuned arms | Conforms |
| Development use | Prediction-only curves; no selection or early stopping | Conforms |

This is a source-and-record audit, not a fresh fit or a full replay. It makes no
claim about protocol dimensions outside initialization and optimization.

## Claim impact and reader interpretation

The existing predictions, fitted states, evaluation metrics, and RES-510
inferential correction continue to describe the learner that was executed,
including these seed-specific random bias starts. Since the six arms share the
same start within each seed, their paired comparisons retain that shared-start
design. This does not make those comparisons results from the specified
zero-bias learner.

No estimate was produced for the unexecuted zero-bias learner, and this audit
does not identify the effect of the initial biases on any result. Claims that
depend on strict conformance to the zero-bias protocol are unsupported. Read the
RES-292 results as evidence about the executed fixed learner with the recorded
initialization above, conditional on its data, seeds, and evaluation design.
RES-510 addresses pooled uncertainty for these same fitted instances; it does
not remove this protocol deviation. No retraining or numerical study was done.

## Provenance

The execution is tied to baseline commit
`de014231569442c7e83d1774877a8b92a9abc314`; this erratum is proposed from
preservation parent `15451032ee75f5e99c728aa44fd1f83f780bacc5`. Exact protocol,
learner, realization, fitted-instance, model, prediction, metric, and source
hashes are recorded in the machine-readable files. The erratum is outside the
frozen `studies/synthetic_pretraining_transfer/` and
`results/studies/synthetic_pretraining_transfer/` evidence homes.
