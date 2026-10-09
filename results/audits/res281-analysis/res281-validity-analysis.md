# RES-281 cross-version validity audit

Execution bundle: `results/audits/res281/audit-results.json` (`sha256:0bbe5d58be59c8ba76fae1a9d6e4a116629b5c88fbdbfb32def6c4b9872bb597`).
Axis reproduction receipt: `results/audits/res281/reproducibility-execution.json`.
Axis execution SHA-256: `sha256:992644d03d3adee96b66953a5a001f3ccd5b1b3685403191347e18334ec16e94`.
The audit covers 9 registered versions and all 14 attack contracts per
version (126 version/attack states).

## M5 coverage

| State | Attack/version records |
|---|---:|
| `PASS` | 12 |
| `FAIL` | 0 |
| `INCONCLUSIVE` | 14 |
| `NOT_APPLICABLE` | 53 |
| `NOT_RUN` | 1 |
| `UNSUPPORTED_BY_EVIDENCE` | 46 |

Every registered attack/version cell has exactly one state. Coverage
PASS is a process check, not a validity finding. No scalar validity
score is computed.

## Evidence-backed findings

Public-native version: `iid_latent_capacity_change_with_transient_expression_forecasting@1.0.0`.
9 non-coverage diagnostics executed. The fresh full-production replay
passed twice: train and validation bytes matched across generations,
and both manifests matched the frozen IID manifest byte for byte.

The bounded participant-key and target-canary checks passed: all 18
sealed comparator instances were invariant on the 96-row audit sample.
The provenance check passed for the public-native source, generation
configuration, and the hashed M4 artifacts. These results do not
generalize beyond those checks and inputs.

Plan counterfactual, reversed-history, observation-noise, simple-
model-frontier, fit-seed, and model-ranking diagnostics are
INCONCLUSIVE under their frozen criteria. The measured deltas and
ranks are descriptive; no post-hoc margin was added. No attack
returned FAIL.

Sparse-history sensitivity is UNSUPPORTED_BY_EVIDENCE because the
public schema requires complete weekly histories and declares no
missingness law. Distribution-shift sensitivity is
UNSUPPORTED_BY_EVIDENCE because this version declares no supported
shift relation. Shortcut-feature dependence is NOT_RUN because no
suspect feature was identified before outcomes were inspected. The
native hidden-test attack is NOT_APPLICABLE because this version makes
no hidden-test claim.

The metadata-only provenance audit ran on all eight historical
projections and was INCONCLUSIVE: public source descriptions and
identity records were checked, but original realization, model, and
evaluation artifacts are unavailable. Their applicable row-level
attacks remain UNSUPPORTED_BY_EVIDENCE because the repository has no
rights-cleared version-specific rows and split identities, runnable
historical adapters, or matching fitted model/evaluation artifacts.
Historical hidden-test access status is also unknown. No private
historical rows or checkpoints were imported.

## Cross-version comparison

All 36 pairwise numerical comparisons are rejected. Historical score
artifacts and matched cross-version support are unavailable, and the
versions vary in task, QOI, information boundary, world, DatasetSpec,
or evaluation identity. The capacity-change comparison is especially
explicit: historical production used scrambled Sobol sampling while
the public-native variant uses IID pseudorandom sampling, and their
evaluation identities differ. Raw scores and rankings are therefore
not comparable.

No cross-version validity improvement or regression is demonstrated.
The registry documents design changes, but chronology alone is not
evidence that a change improved validity. Within-version sensitivity
findings remain scoped to their own native tasks and protocols.

## Unresolved scientific questions

The synthetic task's correspondence to real-athlete populations and
outcomes has not been externally validated. No admissible data or
matched model outputs resolve historical reconstruction, hidden-test
fairness, or ML load-bearing contribution. Native sparse-history and
distribution-shift robustness also remain unresolved. The observed
plan/history/noise sensitivities need predeclared uncertainty or
practical margins before they can support a resolved effect claim.

## Files

- `attack-by-version.csv`: every registered attack by version with its six-state result.
- `version-by-axis-evidence.csv` and `.json`: pre-RES-281 profile
states alongside RES-281 attack and direct-axis evidence; cells retain
multiple states rather than collapsing them.
- `cross-version-comparability.csv`: declared semantic checks and
explicit rejection reasons for every version pair.
- `design-change-evidence.csv`: source-backed design descriptions,
with no validity-improvement inference.
- `unsupported-evidence.json`: every unsupported attack and historical
axis state with cited evidence and named gaps.
- `m5-coverage-summary.json`: per-version and overall attack-state counts.
- `analysis-results.manifest.json`: checksum index for these files and
the execution inputs.
