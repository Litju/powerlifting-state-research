# Structural reconstruction and identification specification

## System and units

For each lift, daily stimulus is `s_t = x_t / (x_t + X_REF)`, where
`x_t = dose_t * intensity_t`. The native zero-initial-state dynamics are

```text
A_t = alpha_A A_(t-1) + (1-alpha_A) s_t
R_t = alpha_R R_(t-1) + (1-alpha_R) s_t
C_t = B (1 + G_A A_t)
P_t = C_t (1 - G_R R_t)
alpha_A = exp(-1/tau_A), alpha_R = exp(-1/tau_R)
A_-1 = R_-1 = 0
```

`C` and `P` are kilograms; `A`, `R`, `s`, and the gains are dimensionless;
time constants and schedule cadence are days; dose, intensity, and `X_REF`
are the dimensionless public system coordinates. The implementation and
population transforms are the frozen M2/M3 sources named by the protocol.

The full unknown parameter vector is the 16-coordinate public population
parameterization: baseline scale and lift ratios, per-lift adaptation and
suppression utilization and retention coordinates, and a shared reference
stimulus. Each coordinate follows the public `[0, 1)` support; the numerical
solver uses zero and the largest representable float below one. The coordinates
are mapped by the public population transforms. This is system identification with the
equations and coordinate bounds known; it is not discovery of an unknown
physiological law.

## Observation and information boundary

At days 6, 13, …, 223, the native M2 generator records assessment `a`, load
`L=f*a` with `f` in `[0.68, 0.71)`, and velocity
`v=e+b*(1-L/P)/0.6 + epsilon_v`. The assessment is
`a=P*(1+epsilon_a)`. The generator rejects non-positive assessments and
relative loads outside `[0.4, 1]`. The study stores all three visible channels
and the past/future schedules, but predeclares that every reconstruction method
uses assessment history only. This keeps the structural comparison on the same
measurement channel and separates it from RES-287's channel-inversion study.
No estimator receives latent truth, true states, population coordinates,
future realized outcomes, or future observations.

The full noisy assessment likelihood marginalizes the sampled load fraction.
For `z=a/P`, its unnormalized density is the Normal density of `z` with mean 1
and standard deviation `CV * noise_scale`, multiplied by

```text
w(z) = max(0, min(0.71, 1/z) - max(0.68, 0.4/z)) / (0.71 - 0.68)
```

The normalizing acceptance probability is independent of `P` because the
assessment error and relative-load rule are scale invariant. The likelihood
includes the `1/P` change-of-variables term. Noise-free observations use a
deterministic least-squares objective; a zero-noise posterior is undefined and
will be reported as such rather than assigned an artificial noise floor. For
optimizer proposals outside the accepted assessment-ratio support, a fixed
quadratic feasibility penalty guides the solver. Such proposals are never
eligible as final fits; all selected fits use the exact conditional likelihood.

## Reconstruction estimands

The reduced estimator uses the newest assessment to estimate only expressed
performance `P_223` in kilograms. It does not estimate capacity, states,
dynamics, or future capacity change. The full estimator fits all 16 bounded
coordinates to assessment history and the known schedules under the native
zero initial state, then derives `P_223`, `C_223`, `A_223`, `R_223`, and
`DeltaC_56 = C_279 - C_223`. The Bayesian method uses the same full system,
the exact noisy assessment likelihood, and two predeclared coordinate priors:
Uniform `[0,1]` and independent Beta(8,8) for prior sensitivity. Its reported
posterior is a bounded local Laplace approximation at the MAP; failures of the
interior-mode, positive-Hessian, conditioning, or draw-support checks remain
explicit failures. A zero-noise posterior is not defined. The hybrid retains
full structural states and parameters, and fits a ridge correction for
`DeltaC_56` from development-only prediction residuals. Its correction is
clipped to the protocol's fixed kilogram bound. A predictive correction is
not evidence of improved state or parameter recovery.

## Identifiability claims

Structural identifiability asks whether ideal complete outputs uniquely
determine states or parameters for a specified input and known law. Local rank
checks address only nearby sensitivity; global identification requires ruling
out every admissible alternative. Practical identifiability is the stability
of estimates under finite noisy observations. Prediction error is a separate
estimand, and causal identification is outside this study.

At one time, all native observation channels factor through `P`. For free
`A,R`, the latent derivative has one output row,
`dP/d(A,R) = (B*G_A*(1-G_R*R), -C*G_R)`, so the instantaneous rank is at most
one. Along a fixed-`P` level set, admissible `R` changes can be offset by `A`,
changing `C` while leaving `P` unchanged. Whole histories can add information
only through known dynamics and sufficiently informative inputs.

Under a constant input product `x=0.6` and the native zero initial state,
changing the population reference-stimulus coordinate while inversely
rescaling adaptation and suppression gains preserves `G_A*A_t` and
`G_R*R_t` at every time. Thus `C_t` and `P_t` remain equal while the hidden
states, gains, and `X_REF` change. This exact family is outside the four
canonical historical input templates. It is a counterexample for that
constant-input design and does not establish non-identifiability on the native
templates. The RES-287 free-initial-state rest result is a distinct extension
and is not transferred to the native zero-initial-state system.

Midpoint Jacobians use all 32 weekly expressed-performance outputs for three
lifts, normalized coordinates, central steps `1e-5` and `5e-6`, and relative
rank threshold `1e-8`. They are evaluated separately for each canonical history
template and for the declared low-excitation sensitivity design. Finite
differences, singular spectra, and multi-start equivalence searches can expose
local weakness or a counterexample; they cannot establish global uniqueness.
If no exact counterexample is found on canonical histories, the global result
remains `INCONCLUSIVE`.

## Units and claim limits

Assessment, load, expressed performance, capacity, and capacity change are
reported in kilograms; velocity (stored but unused by these estimators) is in
m/s; states and population coordinates are dimensionless; time constants are
in days. The study tests exact synthetic system identification under its
declared support. It does not estimate real-athlete physiology, intervention
effects, or generalization beyond these schedules and the public model.
