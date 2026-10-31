# RES-552 independent review checklist

Planning status: READY_FOR_INDEPENDENT_RE_REVIEW. AI-assisted desk review requested five bounded repairs; external human signoff
and independent re-review remain pending. Every unchecked item is pending; the static receipt is not a
scientific/numerical review or an execution authorization.

## Mathematical and numerical reviewer

- [ ] Confirm the accepted-assessment conditional density, scale-invariant
  normalizer, 1/P term, omission of constants only, and finite-rejection semantics.
- [ ] Confirm population coordinate ordering/transforms, zero initial states,
  ratio support, all four knots, piecewise derivatives and fail-closed kink rule.
- [ ] Verify independent z-domain piecewise Gauss-Kronrod (epsabs=1e-12/3,
  epsrel=1e-12, limit=200 per piece) and f-domain CDF composite 32-point
  Gauss-Legendre (1/2/4 panels, both differences <=1e-13); cross/original
  agreement <=1e-12 and full-NLL constant agreement within tau_eval.
- [ ] Judge independent normalization/gradient tests, binary64 step sizes,
  objective summation error allowance and stationarity error floor adequate.
- [ ] Check projected stationarity plus box-sign KKT and complementarity;
  confirm near-bound coordinates cannot evade the gate through projection alone.
- [ ] Verify source-confirmed accepted-event instrumentation, six checked states
  for five final nonzero moves, callback/trial/duplicate exclusions, diagnostic
  accounting and INCONCLUSIVE_INSUFFICIENT_HISTORY for <5 moves/zero iterations.
- [ ] Assess the five-iterate stop rule and two-start/two-method objective
  agreement thresholds. Are they stringent and resolvable without empirical tuning?
- [ ] Confirm the two candidates test numerical procedures on the identical MLE,
  without priors, changed bounds, unsupported clipping or an interior-only transform.
- [ ] Review lower unqualified feasible proposals, boundary/multiple-mode
  reporting, and the decision to stop when bounded search cannot corroborate.

## Scientific / inverse-problem reviewer

- [ ] Verify key-only sentinel selection, fixed noise/strata/primary target and
  omission of eight joint cells. Confirm the cohort is development evidence.
- [ ] Inspect input mount/access firewall: no latent truth, future outcomes,
  test labels, original errors, posterior coordinates or residual-model outputs.
- [ ] Confirm Phase A PASS is numerical adequacy for named cases only, with no
  global identification, physiology, causal or fresh-confirmation claim.
- [ ] Confirm constant-input and free-state counterexamples are not transferred
  to canonical schedules/zero initial states.
- [ ] Review Phase B's constrained infimum, finite-reference distinction,
  anchor/grid/tie rules, exact target equality, independent Lagrangian KKT and
  rank/constraint-qualification checks, and feasible distinct-vector evidence.
- [ ] Require EACH alternative vector in [ell_ref-max(tau_eval(reference),
  tau_eval(candidate)), ell_ref+1e-4] against ONE immutable same-case Phase A
  reference; lower solutions invalidate it, worse vectors are rejected, and
  pairwise-only comparison is forbidden. Check each vector's own target KKT.
- [ ] Check numerical near-equivalence versus descriptive likelihood-drop bands;
  no calibrated interval or global uniqueness claim follows from a finite profile.
- [ ] Confirm every failure denominator, NOT_RUN/BLOCKED/FAILED/INCONCLUSIVE
  state, falsification condition and post-selection limitation is explicit.

## Source, resource and owner admission reviewer

- [ ] Verify source-identities.json and baseline-files.json against the exact
  baseline. Keep execution-era dependency hashes distinct from current hashes.
- [ ] Qualify the later binary environment and BLAS/platform identities; web
  option documentation does not qualify the SciPy 1.18.1 binary.
- [ ] Verify original four starts, settings, converged-first selection and raw
  outputs remain unchanged; any prospective watchdog-censored rerun is labeled.
- [ ] Confirm resources JSON is the sole budget authority, all three independent
  per-case limits are 19800, and both prose/checklist tables are checked against
  JSON by the static validator. No diagnostic exemptions or bucket transfers.

<!-- phase-a-budget-table -->
| Counter | Per case | Phase A total | Daily-transition ceiling |
| --- | ---: | ---: | ---: |
| Function | 19800 | 316800 | — |
| Gradient | 19800 | 316800 | — |
| Model passes | 19800 | 316800 | 266112000 |
<!-- /phase-a-budget-table -->

- [ ] Review 316800 Phase A and 64800 Phase B F/G/model-pass caps, one CPU
  thread, 2 GiB memory and 7200/2160-second CPU/wall ceilings; counters include
  diagnostic and unsuccessful work and cannot reset or borrow phase budgets.
- [ ] Require later inert tests of watchdogs/counters and allowlisted read-only
  inputs before any scientific call. No hardware sufficiency claim exists here.
- [ ] Check all baseline files, G1–G4/RES-293/model artifacts and licenses remain
  unchanged. Confirm separate anonymous/attributed preprint preservation and
  private draft/unmerged paper PR gate without publishing manuscript material.
- [ ] Confirm public receipt commands use repository-relative paths; raw host
  paths remain private and a static guard rejects machine-specific paths.
- [ ] Record independent reviewer identities, conflicts, verdicts and exact draft
  hashes in a later authority record. No AI self-check substitutes for signoff.
- [ ] Obtain explicit owner GO_FOR_G2_NUMERICAL_EXECUTION for Phase A only
  after review; keep Phase B NOT_ADMITTED pending Phase A PASS and separate GO.

## Actual scope of this task

Static: pinned remote main/clean checkout, detached inspection, isolated branch,
source/artifact byte checks, original CSV count parsing, metadata-only sentinel
selection, proposal JSON/budget checks and preservation checks. These are recorded
in verification-receipt.json. Original source was read as text, never imported.
The standard-library validator verifies documents and bytes only.

NOT_RUN: likelihood/gradient/model evaluations, optimizer construction/execution,
training, inference replay, data generation, target scoring, environment runtime
qualification, independent review and both scientific phases. No original
`--check`, pytest suite, build_bundle, verifier with scientific replay or CI
workflow is invoked. Existing CI may execute scientific checks on pull requests;
the proposal commit carries `[skip ci]` to prevent those workflows from
starting on the draft PR. The documented marker applies to push/pull_request
events; this repository has only those automatic triggers. Do not remove it
or manually dispatch workflows during this planning gate. See
[GitHub skip-workflow documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs).
