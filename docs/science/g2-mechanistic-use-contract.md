# G2 mechanistic-use contract

Decision: [`FULL_G2_IDENTIFICATION_UNSUPPORTED`](../studies/g2-identifiability-decision.md). This contract states what the G2 mechanistic model may and may not be used for in PSR. It applies to current-facing documentation, reports and code comments. It does not edit frozen studies.

## Permitted uses

- **Synthetic dynamical simulation:** running the known adaptation and suppression equations forward for declared synthetic parameters and plans.
- **Mechanistic hypothesis exploration:** examining how declared parameter values would change simulated trajectories, labelled as simulation.
- **Controlled forward-model sensitivity:** local sensitivities and design screens, reported as conditional on the stated parameter point and model (not as identifiability).
- **Forecasting comparisons within validated experimental conditions:** comparing forecasting procedures (including M1 and M2) on the synthetic observations, populations and shifts that were actually tested, with their denominators and uncertainty.
- **Estimating observed-style expressed performance** in the tested synthetic conditions, as a prediction target and not as mechanism evidence.

## Unsupported uses

- Claiming recovery of an athlete's actual adaptation or suppression state, gain, utilization, retention or time constant.
- Reporting nonstationary or bound-limited optimizer point estimates as identified physiological parameters. A fitted value that sits on a box bound, or whose optimizer did not pass an independent stationarity check, must be labelled "optimizer output, not identified".
- Claiming unique parameter recovery, or a reduced identifiable combination, a parameter range or a confidence set, without adequate evidence (a structural argument or calibrated global profile, plus practical interval evidence).
- Treating zero detected ambiguity pairs, local full rank or improved objective values as identifiability.
- Real-athlete training prescription, causal effectiveness claims, or physiological validation.

## M1 and M2

M1 (adaptation-only) is the simpler numerical and predictive baseline: it reaches independent stationarity more often and predicts about as well as M2 in the preserved comparison. This is evidence of numerical tractability and parsimony. It is not evidence that adaptation parameters are biologically real or identified, and M1 omits the suppression pathway present in the synthetic generator. M2 is the full 16-parameter model and carries no demonstrated predictive advantage over M1.

## Reopening the question

Full recovery may be reconsidered only with new, separately authorized evidence that meets the definitions in the decision memo. This contract does not authorize a new optimizer or profile campaign.
