# G2 identifiability decision (RES-617)

**Question.** From the current synthetic observations, can PSR defensibly recover the individual adaptation and suppression parameters of the full 16-parameter G2 model?

**Answer.** No. Disposition: **`FULL_G2_IDENTIFICATION_UNSUPPORTED`**. The preserved evidence supports G2 as a forward simulator and a locally informative sensitivity tool. It does not support recovering an athlete's adaptation or suppression parameters, and it does not certify a reduced identifiable quantity or a calibrated parameter set.

This memo adds no computation. It reads preserved results only and records no private rows, parameters or predictions. Identities and the verification of each bundle are in the [provenance record](../../provenance/RES-617-g2-evidence-provenance.md).

## 1. Definitions used

For inputs `u` (schedule, plan) and the observation map `y(θ; u)` of the synthetic model with parameters `θ`:

- **Structural identifiability:** `y(θ; u) = y(θ'; u)` for all observation times implies `θ = θ'`, over the admissible parameter set, without noise. It is a property of the equations and inputs.
- **Practical identifiability:** with finite noisy data, the likelihood determines `θ` to a bounded region that is small relative to the admissible set. Requires a profile-based or equivalent interval.
- **Local sensitivity:** the Jacobian `J = ∂y/∂θ` at one point has full numerical rank. A necessary hint of local identifiability, not sufficient for global or practical identifiability. With noise-scaled `J`, `JᵀJ` is the local Fisher information, whose smallest eigenvalue `s_min²` gives a linearized standard deviation `1/s_min` for the weakest combination.
- **Numerical stationarity:** the projected gradient `‖q − Proj_Q(q − ∇f(q))‖∞` is at most `10⁻⁶` at an optimizer's returned point. It certifies a local stationary point of the training objective only. It says nothing about uniqueness, curvature or global optimality.
- **Predictive adequacy:** forecast accuracy on held-out observations. It does not imply that parameters are recovered.

## 2. Verified evidence

| Source | Preserved result (aggregate only) |
| --- | --- |
| RES-289 (public) | Instantaneous assessment, load and velocity all factor through expressed performance `P`, so one time step carries rank at most one for the two latent states. Local rank is 16/16 at tested midpoints, with condition numbers 952–1119. There is an exact equivalence counterexample (reference-stimulus/gain) for the constant 0.6 input design, outside the canonical templates. Global identification on canonical templates is **INCONCLUSIVE**. At native noise only 7/256 full-MLE starts converged (22/256 at doubled noise). |
| RES-557 | Final integration returned `NUMERICAL_ADMISSION_V2_INCONCLUSIVE`: of the 192-start synthetic rehearsal, 19 starts were attempted and 173 were not run before a predeclared resource stop. No original-data call was made and no readiness is claimed. |
| RES-592 main | 192 starts were attempted over 16 synthetic cases: `MAIN_BENCHMARK_PARTIAL`. 27 M2 L-BFGS-B starts hit the 400-call limit; two M1 starts had incomplete diagnostics. Independently verified stationarity: M1 L-BFGS-B 15/64, M2 L-BFGS-B 2/64, M2 SLSQP 0/64 (16 not feasible); 17/192 overall. |
| RES-592 predictive | 13 finite M2-versus-M1 pairs: M2 won 6, M1 won 7. Mean ΔNLL −0.0332 nat/observation, median +0.0180, descriptive interval [−0.0848, +0.0126] crossing zero: `MODEL_COMPARISON_INCONCLUSIVE`. Unpaired mean held-out NLL: M0 4.724 (16 cases), M1 4.191 (15), M2 4.189 (13); unequal available-case sets prohibit using these means as a matched superiority comparison. |
| RES-592 sensitivity and profiles | 13 feasible selected M2 fits had local spectra: all rank 16/16 at cutoff `10⁻⁶`, but condition numbers 6.8×10² to 1.2×10⁵ and smallest scaled singular values 1.4×10⁻³ to 0.31. Two fixed profile entities completed 40 bounded profile fits with no qualifying ambiguity pairs; the profile values are feasible upper bounds, not global minima or intervals: `LOCALLY_INFORMATIVE_ONLY`. |
| RES-592 rescue | Eight selected capped starts: all improved exact training NLL (median 7.87×10⁻⁵ nat, max 0.0519), none became independently stationary: `NO_RESCUE_WITHIN_FIXED_BUDGET`, 0/8. A post-hoc selected-start sensitivity result; it does not replace the original comparison. |

Two read-only tabulations of preserved tables, added here: (a) in the selected fits, 80 of 208 M2 normalized coordinates (38.5%) and 50 of 150 M1 coordinates (33.3%) sit on the box bounds `[0, 1)`. (b) Reading the stored M2 singular values as a noise-scaled Jacobian with respect to the 16 normalized coordinates, the linearized standard deviation of the weakest direction, `1/s_min`, is between 3.2 and 725 across the 13 fits. The coordinate box has width 1, so even the best-conditioned fit does not localize its weakest combination within the box. This is a local, linearized reading at mostly nonstationary points and is not a confidence set.

## 3. Target-by-target assessment

Classes: **S** structurally identified, **P** practically constrained, **L** only locally informative, **U** unsupported or inconclusive.

| Target | Structural | Practical | Local sensitivity | Stationarity | Predictive | Class |
| --- | --- | --- | --- | --- | --- | --- |
| Individual adaptation parameters (gain, utilization) | not shown; counterexample outside canonical templates, global canonical case inconclusive | squat adaptation-coordinate RMSE 0.30–0.34 for the MLE and uniform-prior Laplace fits at native noise, versus 0.289 for the standard deviation of the uniform population itself | informative locally | 2/64 M2 starts stationary | not applicable | **U** |
| Individual suppression parameters | not shown | squat suppression-coordinate RMSE 0.39–0.40 (same fits), again above the 0.289 population spread; suppression coordinates sit on a bound in 5–9 of 13 selected fits per lift | informative locally, weakest directions near-degenerate | as above | not applicable | **U** |
| Retention / time constants | not shown | squat adaptation time-constant RMSE 29–49 days against a 12–172 day population range; suppression 4–7 days | locally informative | as above | not applicable | **U** |
| Net expressed-performance trajectory `P` | observations are generated conditional on `P` by the model's observation map; estimating `P` from noisy measurements is a distinct inverse task | squat `P_223` RMSE 2.9 kg (MLE) and 4.0 kg (Laplace) at native noise versus 11.5 kg for the reduced latest-assessment estimator (RES-289, known law) | n/a | MLE starts mostly nonconverged (retained) | descriptive estimation improvement under the tested synthetic law, not a calibrated parameter interval | **U** for practical identifiability; observable-style `P` is estimable descriptively, not an identified physiological state |
| Future mechanistic forecasts | n/a | n/a | n/a | n/a | M1/M2 unpaired mean NLLs are numerically lower than M0, but unequal available-case sets prevent a superiority inference; M2 vs M1 is inconclusive (6 vs 7); 3 of 16 pairs unavailable | **U** for M2's advantage; forecasts only within validated conditions |
| Reduced parameter combinations | none preregistered or tested | none profiled | none isolated | M1 15/64 stationary vs M2 2/64 | M1 ≈ M2 | **U** (see M1 note) |
| Set-valued parameter descriptions | none certified | profiles are upper bounds only | n/a | n/a | n/a | **U**; exploratory only |

## 4. Numerical optimization limitations

Optimizer success is not identifiability. Even the best case (M1 L-BFGS-B) verified stationarity in 15 of 64 starts, and verified stationarity is a local property. Zero detected ambiguity pairs from two bounded profiles with feasible upper-bound values cannot establish uniqueness: failing to find a competing solution is not a proof that none exists. The rescue showed that improved objectives (all eight improved) did not produce stationarity. The eSS+IPOPT hybrid was not run because the dependency was unavailable. RES-557 stopped its synthetic admission rehearsal under a resource control. No result here is a theorem about global identifiability.

## 5. Supported and unsupported mechanistic quantities

- **Supported (conditional, within named synthetic conditions):** forward simulation of the known equations; noisy observed-style expressed performance as an estimable and forecastable quantity; local forward-sensitivity diagnostics as exploratory information; comparison of forecasting procedures within validated conditions.
- **Unsupported:** individual adaptation, suppression, gain and time-constant values; latent states `A`, `R` and capacity `C` as recovered physiological quantities; any certified reduced combination, parameter range or confidence set; M2's superiority over M1.

**M1's position.** M1 (adaptation-only, 10 coordinates) is the simpler numerical and predictive baseline: it verified stationarity far more often (15/64 vs 2/64 M2 L-BFGS-B starts) and predicted about as well (13-pair comparison inconclusive). That is evidence of numerical tractability and parsimony only. M1 omits the suppression pathway that the synthetic generator contains, was not profiled, and carries no biological validation. It does not certify any identified quantity.

## 6. Final disposition

`FULL_G2_IDENTIFICATION_UNSUPPORTED`. `REDUCED_QUANTITIES_SUPPORTED` is not chosen because no reduced quantity was preregistered or certified. `SET_VALUED_SENSITIVITY_ONLY` is not chosen because the evidence cannot bound feasible sets or give calibrated ranges. The question is closed at its demonstrated boundary; no follow-on optimizer campaign follows from this decision.

## 7. Claim-to-evidence matrix

| Claim | Status | Evidence |
| --- | --- | --- |
| Full 16-parameter athlete-state recovery is supported | **Not supported** | RES-289 inconclusive global case and nonconvergence; RES-592 2/64 M2 stationarity, 38.5% bound coordinates, wide linearized weakest-direction uncertainty; RES-557 inconclusive admission |
| Individual adaptation / suppression / time constants are identified | **Not supported** | coordinate RMSE at or above the uniform population spread; coordinates on bounds; counterexample outside canonical templates |
| Local rank shows identifiability | **Not supported** | rank 16/16 coexists with condition numbers up to 1.2×10⁵; local only |
| Zero ambiguity pairs shows uniqueness | **Not supported** | profile values are upper bounds from two entities |
| M2 predicts better than M1 | **Not supported** | 6 vs 7 of 13, interval crosses zero |
| M1/M2 predictive superiority to persistence based on unpaired mean NLLs | **Not established by unequal-denominator means**; descriptive values only | M0 4.724 (16 cases), M1 4.191 (15), M2 4.189 (13); requires matched-case comparison |
| Optimizer improvement implies recovery | **Rejected** | 8/8 improved, 0/8 stationary |
| Observed-style performance is estimable in the tested synthetic conditions | Supported, conditional | RES-289 `P_223` RMSE vs reduced estimator |
| G2 is a valid forward simulator and sensitivity probe | Supported | model code and RES-592 forward sensitivities |
| Real-athlete, physiological or causal claims | **Not supported** | no experiment addresses them |

## 8. Mechanistic-use contract

The binding statement of permitted and unsupported uses is the [G2 mechanistic-use contract](../science/g2-mechanistic-use-contract.md). In short, G2 may be used for synthetic simulation, mechanistic hypothesis exploration, controlled forward-model sensitivity and forecasting comparisons within validated conditions. It may not be used to claim recovery of an athlete's adaptation or suppression state, to report nonstationary point estimates as identified parameters, to claim unique recovery without adequate evidence, or for real-athlete prescription or causal claims.

## 9. Remaining scientific limitations

- The preserved results come from eight selected synthetic sentinel entities at two noise levels (16 cases), not an untouched test cohort. Held-out comparisons have unequal denominators (16, 15 and 13).
- Profiles cover two preselected entities and two quantities, with feasible upper-bound values only.
- The linearized weakest-direction reading in section 2 uses mostly nonstationary points and is not a confidence set.
- No structural identifiability theorem is established or refuted for the canonical templates; the question remains open but is not pursued here.
- The RES-289 public study assumes the known equations and zero initial states, and its failures are retained.
- Different studies (RES-289, RES-557, RES-592) use different source and observation laws and are not pooled.
- All results are synthetic. No real-athlete validity, physiological identification or causal training claim follows.

