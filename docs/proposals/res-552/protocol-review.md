# RES-552 — G2 numerical adequacy protocol, draft 0.1.0

Status: **READY_FOR_INDEPENDENT_PROTOCOL_REVIEW**. This is a prospective,
non-operative proposal, not an approved or frozen execution protocol. All
numerical checks and phases below are **NOT_RUN**. Phase B is **NOT_ADMITTED**.
Independent numerical/inverse-problem review and explicit owner
`GO_FOR_G2_NUMERICAL_EXECUTION` are required before any solver or model evaluation.
A Phase A authorization alone does not authorize Phase B.

## Authority, preservation and question

Authority is RES-552, following completed RES-551's planning-only G2 decision.
Research main is exactly `b751cf4c9d44301b03861127ed94158d7c93fa3a`;
original science freeze is `3b833b627714fb4f788d4d61de6efa52453dafa5`.
RES-289 execution source is `7666415` (full SHA in source-identities.json).
The unchanged study is
`psr:study:target-sufficient-structural-reconstruction-public-native@1.0.0~12aafcbac716`,
protocol digest `sha256:12aafcbac716350e46002178918fe1ee08f65c2f76167368f7ed6cb4a8e0f405`.
Exact realization, evaluation, scientific identities, source hashes and artifact
hashes are in source-identities.json. All baseline tracked files are protected
by baseline-files.json, including G1–G4, RES-293, model states, licenses and CI.
No existing file may change. The separate anonymous/attributed manuscript and its
commercial-licensing/author gate are independent and untouched.

Question: can either of two fixed numerical procedures produce independently
checked stationary, feasible, mutually corroborated low-objective candidates
under the **same** accepted-assessment MLE on a small existing sentinel cohort?
Failure to do so is numerical inadequacy/inconclusiveness, not evidence of
structural non-identification. No training, priors, residual refits, posterior
fitting, data generation, truth scoring or new excitation is proposed here.

The execution-era pyproject.toml and uv.lock hashes differ from current main.
Both old hashes match RES-289's execution commit; the later RES-298 dependency
lock change is historical, not evidence corruption. Preserve both identities.
A later admission must qualify Python 3.12.13, NumPy 2.4.4 and SciPy 1.18.1 plus
platform/BLAS/build identities, without installing or running them in this task.
The current web solver references describe SciPy 1.18.0; they support option
semantics, not binary compatibility or a claim that 1.18.1 was qualified here.

## Exact likelihood and derivatives

For normalized coordinates q in Q=[0,u]^16, u=nextafter(1,0), use exactly the
public population transform and native initial states A[-1]=R[-1]=0. For lift l,
s_t=x_t/(x_t+X_REF), alpha_A=exp(-1/tau_A), alpha_R=exp(-1/tau_R),
A_t=alpha_A A_(t-1)+(1-alpha_A)s_t,
R_t=alpha_R R_(t-1)+(1-alpha_R)s_t,
C_t=B(1+G_A A_t), P_t=C_t(1-G_R R_t).
The physical transform is frozen source, not an additional fitted model.
In particular its reference coordinate r=0.12+0.73q_15 gives
X_REF=0.6(1-r)/r; it must not be mistaken for X_REF itself.

For each of 96 assessments a_j>0 (three lifts × days 6,13,...,223),
Z=a/P has N(1,sigma_l^2) density before acceptance, with sigma_l=n CV_l,
CV=(0.05,0.04,0.05), n in {1,2}. Independently F is uniform on [b,c),
b=0.68,c=0.71. Acceptance is a>0 and d<=FZ<=e, d=0.4,e=1.
Integrating out F and the unused velocity gives

```
w(z) = [min(c,e/z)-max(b,d/z)]_+ / (c-b), z>0; otherwise 0
Zacc(sigma) = integral phi((z-1)/sigma)/sigma * w(z) dz
           = 1/(c-b) integral_b^c [Phi((e/f-1)/sigma)
                                  -Phi((d/f-1)/sigma)] df
p(a | P, accepted) = phi((a/P-1)/sigma) w(a/P) / (sigma P Zacc(sigma))
```

Zacc is independent of P: acceptance uses ratios, not a fixed kilogram cutoff.
Finite rejection of 1000 independent attempts, conditioned on obtaining an
accepted observation, has the same accepted density; exhaustion is an input
failure, not an alternative likelihood. Finite-precision Gaussian/velocity
sampling is treated by the original continuous observation-law approximation;
no likelihood for the PRNG's discrete output is claimed.

Thus exact summed negative log likelihood (NLL) is

```
ell(q) = sum_j { log P_j + (a_j/P_j-1)^2/(2 sigma_l^2)
                -log w(a_j/P_j) + log sigma_l
                + 0.5 log(2 pi) + log Zacc(sigma_l) }
```

If any P<=0, nonfinite value, or w<=0 occurs, ell=+infinity. The support is
**open** d/c<z<e/b. No clipping, epsilon likelihood, winsorization, least-squares
surrogate or Beta(8,8) prior is permitted. For comparison to stored objectives
use ell0=ell-sum_l 32[log sigma_l+0.5log(2pi)+log Zacc(sigma_l)]; the original
implementation omits only this q-independent constant. Candidates optimize
f=ell0/96, which has precisely the same MLE; always report ell0 and full ell.
Original source integrates Zacc over [0,3]; w is zero outside (d/c,e/b),
so this is equivalent mathematically, subject to numerical quadrature error.

On each smooth piece, if J_j=partial P_j/partial q,

```
grad ell0 = sum_j [1/P_j - z_j(z_j-1)/(P_j sigma_l^2)
                   + z_j w'(z_j)/(P_j w(z_j))] J_j
```

There are four breakpoints d/c, d/b, e/c, e/b, in that order. On the three
positive-support pieces w is respectively (c-d/z)/(c-b), 1,
(e/z-b)/(c-b); derivatives are d/[(c-b)z^2], 0,
-e/[(c-b)z^2]. The two internal knots have unequal one-sided derivatives.
The implementation's chosen equality branch is not a mathematical derivative.

The original 1e6 quadratic outside-support penalty may guide search only;
its finite value replaces an invalid term and is not ell. Both candidates
use the original penalty with the same 1/96 scaling during search. A separate
terminal evaluator must recompute the exact likelihood, with no penalty path.
No finite penalized terminal can qualify. Never rank it against a feasible fit.

## Proposed numerical checks and scale-based tolerances

All checks in this section are prescribed for a later authorized stage;
none has been evaluated here. Binary64 epsilon is 2^-52. Numerical gate
thresholds are engineering proposals for review, not empirically calibrated
error bars. If they cannot be resolved within the ceilings, stop; no tuning.

1. Check all input hashes and 16 bounds exactly, all 96 finite positive
   assessments, day/lift ordering and schedules. A terminal must have every
   P_j>0 and w_j>0, and a full finite NLL, with zero support penalties.
   Record min w, minimum distance to every ratio knot and each coordinate bound.
2. Fail closed for any ratio within eta_z=64 sqrt(epsilon) max(1,abs(z))
   of any of the four knots, or any derivative stencil crossing a knot.
   Mark `INCONCLUSIVE_NONSMOOTH`; no smooth KKT or Hessian claim there.
   Report one-sided slopes descriptively; do not replace the gate with a
   subgradient claim or silently shift observations/solutions off a knot.
3. Independently implement the piecewise density formula, using compensated
   summation and a normal-CDF integral over f for Zacc. Compare ell0 against
   the frozen formula at the same feasible coordinates. Tolerance is
   tau_eval=1e-8+256 epsilon sum_j abs(ell0_j) in summed NLL units.
   Check full ell differs from ell0 by exactly the declared constant within
   tau_eval; Zacc absolute error <=1e-12 under two fixed integration settings
   (absolute/relative tolerances 1e-12 and 1e-13). Failure is FAILED_OBJECTIVE.
4. Gradient checks use f=ell0/96 and h=epsilon^(1/3), h/2, about 6e-6 and
   3e-6 of a full coordinate range. Central differences when allowed;
   second-order inward one-sided differences at box boundaries. No clipping
   the stencil. Compare analytic derivatives of both f and P-history to
   differences: abs(error)<=1e-7+1e-5 max(abs(analytic),abs(difference)).
   Both steps must pass. For stationarity certification additionally require
   max absolute f-gradient error and inter-step discrepancy <=2.5e-7;
   otherwise INCONCLUSIVE_PRECISION. Use shared perturbation trajectories to check both f and P, not duplicate model calls. Verify every coordinate at each of
   the 12 method/start terminals, plus four original starting points per case
   when smooth and feasible. An infeasible start needs support/penalty tests,
   not an exact gradient certification. Uncertifiable terminal stays unqualified.
5. Evaluate support algebra at midpoints of each piece, the four exact knots,
   and one binary64 nextafter point on each side. Check w=0 at outer endpoints,
   positive interior w, continuity, one-sided derivatives and q-independent
   normalization. Also test the 1/P density Jacobian explicitly. These are
   synthetic algebra test arguments, not newly generated research observations.
6. With g=grad f define G=q-Proj_Q(q-g). Require ||G||_infinity<=1e-6.
   Also check the box KKT sign residual coordinatewise: at lower bound g>=-1e-6,
   at upper bound g<=1e-6, in the interior abs(g)<=1e-6, using only a
   64 epsilon coordinate active-set tolerance. This prevents near-bound
   projection alone hiding a large interior gradient. There is no multiplier
   for observation support at a qualified smooth terminal, since support is
   strict. Equivalent bound multipliers must be nonnegative and satisfy
   complementarity within 1e-6; record raw gradients and both residuals.
7. In each candidate run require five final accepted iterates, each with
   summed ell0 change <=1e-6 and coordinate step infinity norm <=1e-5,
   as well as terminal feasibility, differentiability, gradient and KKT gates.
   A solver success flag alone never qualifies. A budget-terminated candidate
   may meet these independent checks; preserve its raw failure flag.
   The mean-gradient threshold implies a first-order summed NLL change below
   9.6e-8 for a 1e-3 single-coordinate displacement, below the 1e-6 iterate
   band. Binary64 accumulation allowance is separate from optimizer tolerance.
   This is a local first-order scale argument, not a curvature/global bound.
8. Each candidate procedure must have at least two distinct original starts
   qualify within 1e-4 summed NLL of its best qualified terminal. The two
   candidate best objectives must agree within 1e-4. No feasible terminal
   from any procedure or stored original start may have NLL lower than the
   corroborated candidate best by more than 1e-4 without blocking admission.
   The 1e-4 band is 100 times the iterate band and below 0.000002 per datum;
   it is numerical agreement, not a statistical likelihood cutoff.

Phase A PASS requires all sixteen cases to satisfy the shared objective and
support checks and both candidate corroboration rules. Failure of exact
algebra/gradient consistency is FAILED; lack of feasible certified candidates,
timeout, nonsmoothness, unresolved precision or multistart disagreement is
INCONCLUSIVE, never a global non-identification finding. Multiple stationary
modes and boundary modes remain separate records. Distinct coordinates with
near-equal objective do not prevent numerical PASS; their target spread is
reported and prevents any uniqueness claim.

## Outcome-blind cohort and information firewall

Use only the 32 **development** entities from the existing RES-289 observation
file and split; no test labels or latent truth. Enumerate h=0,1,2,3 for the
squat history template and p in {h,(h+1) mod 4} for plan index, with plan order
[continue,step_up,step_down,cessation]. In each of eight cells, select the entity
minimizing (SHA256(UTF8("RES-552/sentinel/v1|"+entity_id)),entity_id), lexical
hex order. Require the template tuple (h,(h+1)%4,(h+2)%4), canonical key/index
consistency and exactly two eligible development entities per cell; otherwise
BLOCKED. The emitted sentinel-keys.json fixes the resulting eight keys.
Each history and plan appears twice; this deliberately covers eight of sixteen
joint cells, not their interactions. All three lifts are fitted jointly with
shared coordinates. Noise {1,2} gives sixteen cases. Noise zero is excluded
because it is a degenerate likelihood and would test a different solver.

Selection reads keys, split, history-template and plan metadata only. The
static selection check does not inspect assessments, target values, stored
terminal coordinates or convergence to choose cases. Stored aggregate numerical
failures motivated this prospective design, so this is numerics development,
not untouched confirmation. After freeze, an input adapter may expose only the
96 assessments at or before day 223, lift identities, past schedules and declared
future schedules. Future schedules affect derived future targets, never the
history likelihood. Prescribed load and velocity are unused. No truth rows,
latent parameters, future realized observations, target-errors, test labels,
posterior modes or residual-model outputs enter solvers or method selection.
Use a separate input mount without those files; record the allowlist and access
log. Any leak, hash drift or cohort substitution is BLOCKED before solving.

## Two candidates and unchanged comparator

Baseline: the original four-start MLE, q=0.25/0.50/0.75 and the original
entity/noise-seeded uniform start, seed 289303+10*entity_index+int(noise),
Python random.Random uniform(0.1,0.9), coordinate order frozen source.
Reuse exact stored start vectors; verify their start identity in a later stage.
Original L-BFGS-B on ell0, analytic gradients, maxiter=100, maxfun=3000,
ftol=1e-10, gtol=1e-6, box [0,u], unchanged selection rule (converged first;
otherwise lowest finite feasible marked nonconverged). Preserve every old
start and selected output as historical comparator. A later paired rerun uses
the same settings and instrumentation; label it prospective and do not overwrite
old outputs. If a hard external ceiling interrupts it, it is censored, not an
unchanged completed baseline. Never select a candidate by latent error.

Candidate L: L-BFGS-B on f=ell0/96, same four starts, analytic gradients,
maxiter=800, maxfun=800, ftol=1e-13, gtol=1e-7, maxcor=10, maxls=20.
This isolates longer iteration allowance and mean-objective scaling in the
same coordinates, without a logit transform that would exclude boundary modes.
Candidate S: SLSQP on the identical f and four starts, analytic gradients,
maxiter=400, ftol=1e-10, box [0,u], no extra Phase A constraints.
It supplies a different step/active-set mechanism and a route to later equality
profiles. Neither is Bayesian, a least-squares fit or an additional prior.
No further candidate, preconditioner search, restart, warm-start transfer,
noise floor or result-driven resource extension is allowed.

Compare paired per-case objective, feasibility, KKT residuals, qualifying
starts, raw success flags, iteration/call counts, boundary coordinates, and
all near-best target spreads. Report original selected and lowest feasible
objective separately because the historical converged-first rule may differ.
Record target spreads for all five named targets and all lifts descriptively;
primary prospective target is **squat C_223**, no target-error scoring.
Meaningful separation is fixed at 1 kg for C/P/DeltaC, 0.01 for A/R, and
1e-3 for coordinates; numerical target agreement is 1e-4 kg or 1e-6 state units.
Intermediate spreads are unresolved, not forced into stable/ambiguous labels.
An objective advantage by itself is not structural recovery.

Solver option meanings: [SciPy L-BFGS-B documentation](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-lbfgsb.html)
separates objective-reduction and projected-gradient stops;
[SciPy SLSQP documentation](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html)
uses ftol for several conditions and does not return box multipliers. These
are reasons to compute common external criteria rather than compare flags.

## Fixed resource envelope and later admission

One process, one CPU thread including BLAS/OpenMP, no GPU, binary64 throughout;
2 GiB resident/process-tree memory cap; no parallel starts. Hard watchdogs
and call counters operate outside SciPy and include rejected/penalty evaluations,
finite-difference probes, constraint evaluations and independent validation.
A function call includes a likelihood-only request; a gradient-only request
counts against the gradient cap; a fused call counts against both. Count every
model trajectory evaluation separately, including cache misses and target probes.
Report accepted versus rejected work and daily-transition equivalents (at most
840 per full three-lift/280-day trajectory pass).

Phase A per case: baseline 4×3000=12000 F/G; each candidate 4×800=3200 F/G;
shared diagnostic allowance 1400 F/G/model passes. Total per case <=19800
function, 19000 gradient, 19000 model passes. Sixteen cases <=316800 each,
<=266112000 daily-transition equivalents. No counter resets between methods.
Diagnostics include terminal checks, gradient probes, support/normalization
work and baseline's extra terminal evaluations; a cache can reduce cost but
never create budget. Reserve 1400 separately from solver calls; exhausting it
makes the case INCONCLUSIVE. SLSQP has no reliable maxfun option, so a counted
wrapper must refuse the next call at 800, independent of maxiter.
Each start <=30 seconds; diagnostic work <=90 seconds/case; Phase A aggregate
wall and CPU limits each 7200 seconds, including startup/input work. Earliest
ceiling wins. The start limits sum to 5760 seconds and diagnostic limits to
1440, so the global limit may censor overhead. These are hard ceilings, not
runtime predictions. Kill the entire process tree on timeout/memory overflow,
retain partial logs, mark INCONCLUSIVE_RESOURCE, and do not replace a case.

Original full-cohort noisy MLE cost is 29181+28836=58017 F/G calls across
512 starts (about 113/start). The proposed sentinel cap is about 5.46 times
that recorded work, despite fewer entities, to allow difficult starts without
an open-ended campaign. Candidate limits are about seven times the historical
mean per start, not a measured sufficiency guarantee. Diagnostics are bounded
and staged; if all terminal checks do not fit, report INCONCLUSIVE rather
than dropping failed terminals. Host runtime and RAM sufficiency are NOT_RUN.

Later admission requires: independent mathematical/numerical review, approved
fixed protocol hash and sentinel keys, exact input/source/environment hashes,
rights/allowlist verification, tested watchdog/counter enforcement using inert
non-scientific functions, and explicit owner authorization. Empirical threshold
calibration, if requested, is a distinct later authorized qualification stage
with its own frozen scope and review; it cannot revise this draft after outcomes.
Phase B needs its own owner authorization after Phase A PASS.

## Phase B — conditional target profiles, NOT_ADMITTED

Freeze only squat T(q)=C_223(q) as primary target. The other named targets
P_223, A_223, R_223 and DeltaC_56=C_279-C_223 are defined by the same trajectories,
but are descriptive Phase A outputs, not additional profile campaigns. Any
future profile of them requires a new prospective amendment before outcomes.
For a fixed existing case and the exact Q/support, define

```
L_T(t) = inf { ell0(q) : q in Q, every w_j(q)>0, T(q)=t }
D_T(t) = 2 [ L_T(t) - inf_{q in Q, support} ell0(q) ].
```

These are mathematical infima; finite solver values are upper bounds, never
proofs of the infimum or global uniqueness. A feasible alternative is evidence
of a feasible alternative even when optimality is unresolved. It does not
certify proximity to the unknown global MLE.

Choose the first two sentinel entities ordered by the same hash key, **before**
Phase A outcomes; native noise n=1 only. No replacement on failure. For each,
anchor t0 to Candidate S's best qualified Phase A target (ties within tau_eval:
lexically smallest full coordinate vector). Grid is t0+[-10,-5,-2,-1,0,1,2,5,10]
kg. The relative grid algorithm and separation threshold are frozen now;
its numeric center is a predeclared estimator output, not latent truth or an
adaptive grid. No extension/refinement after outcomes.

At each grid point use SLSQP on f with exact equality (T-t)/1 kg=0,
analytic constraint gradient, same box/likelihood and ftol=1e-10, maxiter=400.
Four starts are the Phase A anchor plus uniform vectors 0.25/0.50/0.75;
no neighbor warm starts or grid-dependent restart. Count feasibility restoration
inside the same start budget. Exact equality is never replaced by a soft target
penalty in the reported objective. Candidate L is not used as an equality solver.

Require |T-t|<=1e-5 kg, all Phase A terminal support/gradient checks, and
box KKT on the Lagrangian grad(f)+lambda grad((T-t)/1kg), with 1e-6 residual
and bound signs/complementarity. Independently determine/check lambda rather
than trusting the QP multiplier; if the equality gradient is rank deficient
(norm below 1e-8 kg per normalized coordinate), or constraint qualification
cannot be established on the active box face, report INCONCLUSIVE_KKT.
Two distinct starts must corroborate each profile point within 1e-4 summed
NLL. Require five final iterate objective/step checks as in Phase A and
constraint feasibility. If profile finds ell0 lower than the Phase A anchor
by >1e-4, invalidate the reference and stop INCONCLUSIVE_REFERENCE; do not
recenter or silently improve/restart Phase A.

Report estimated objective differences 2(ell_profile-ell_anchor) with numerical
allowance 4e-4; negative values inside this allowance are numerical zero,
not improved evidence. A **conditional near-optimal target alternative** needs
two explicitly stored feasible, qualified vectors q0,q1 for the same entity,
noise and schedules with |C_223(q1)-C_223(q0)|>=1 kg and
ell0(q1)-ell0(q0)<=1e-4. State that this comparison is relative to the qualified
finite reference, not the unknown global optimum. Separately flag exact
numerical-equivalence candidates only if abs(ell0 difference)<=1e-6,
P-history RMSE<=1e-6 kg and max coordinate separation>1e-3, the old RES-289
criterion; this remains numerical evidence, not an exact algebraic proof.

Use D<=2 only as a predeclared descriptive likelihood-drop band, with no
confidence level or coverage interpretation. Report objective gap alongside
target separation, not an interval called 95%. No Wilks/chi-square calibration,
posterior interpretation or confidence interval is admitted without an
independently justified coverage study, especially with boundaries, support
knots, selection and multimodality. Failure to find an alternative, missing
profile points or a narrow finite grid is **INCONCLUSIVE** for identification;
optimizer failure never establishes target infeasibility.

Phase B cap: 2 entities × 9 grid points × 4 starts × 800 F/G/model passes
=57600 each; diagnostics 400 per entity/grid point=7200 each; total 64800
each, <=54432000 transition equivalents. Each start <=20 s, each grid point's
diagnostics <=40 s; aggregate wall and CPU <=2160 s, memory/thread caps as A.
No transfer of unused A budget. Combined prospective ceilings A+B are 381600
F/G/model passes, 320544000 transitions, 9360 CPU/wall seconds. Neither phase
has been run or authorized by this document.

## Falsification, limitations and stop semantics

The proposed claim of numerical adequacy is falsified by a density/gradient
mismatch, infeasible selected output, unrecognized support kink, unresolved
stationarity, lack of cross-start/cross-method objective corroboration, or a
lower feasible unqualified proposal outside the agreement band. The design's
resource sufficiency is falsified by a ceiling hit; do not hide those cases
from denominators. The admission design is invalidated by data/truth leakage,
source drift, cohort substitution or ex post threshold changes.

Known synthetic equations, finite coordinates and zero initial states are strong
world knowledge. No conclusion transfers to real physiology, causal effects,
unknown laws or free initial states. Flat/multiple modes may persist even after
numerical PASS. Local rank and finite multistart agreement do not prove global
uniqueness. The constant-input x=0.6 exact counterexample is outside canonical
templates and does not settle this design. Parameter-dependent support can
produce nondifferentiability and unstable gradients; clipping can manufacture
solutions. Binary64 tests do not bound all errors. Prior sensitivity in the
original Laplace study is separate and cannot rescue failed MLE optimization.
This already inspected cohort has post-selection/development limits; no fresh
confirmation or population-level inferential coverage is claimed.

`NOT_RUN`: no authorized attempt. `BLOCKED`: authority, input, environment,
firewall or resource enforcement missing. `FAILED`: a check contradicts the
likelihood/gradient/feasibility contract. `INCONCLUSIVE`: bounded computation
cannot certify numerical adequacy or identification. Phase A PASS applies only
to sixteen named numerical cases, never to all RES-289 entities. Report every
case/start and failure reason with its denominator, bound/mode identity and
resource counts. A successful planning review permits a later decision, not
execution, paper changes, merging, publication or new research issues.
