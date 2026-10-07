# Scientific component taxonomy

A benchmark is a composition of scientific components. Each component class has one shared home; benchmark packages refer to those declarations rather than copying them.

| Component class | Meaning |
|---|---|
| WORLD | Causal latent-state transition mechanisms, consumed athlete parameters, process stochasticity, and intrinsic constraints. It excludes population, intervention regime, observations/reporting, tasks/QOIs, and evaluation design. |
| POPULATION | The construction of athlete-specific characteristics and initial conditions. |
| INTERVENTION_REGIME | Training or planned exposure rules, support, and scheduling. |
| OBSERVATION_MODEL | How latent or expressed states become measured observations. |
| QOI | The quantity or quantities a task asks a model to predict. |
| TASK | The prediction problem, horizon, origin, and available information. |
| REPRESENTATION | The model-facing form of available inputs. |
| DATASET_SPEC | The rule for a dataset family, separate from each realization. |
| EVALUATION | The protocol that compares predictions with targets. |
| METRIC | A numerical summary of prediction performance. |
| SHIFT | A declared difference between source and target conditions. |

The initial registry has six canonical world references across eight historical specimens. The observed-origin and latent-origin tasks share one dose-history world while retaining distinct task and quantity-of-interest declarations. Component references with unresolved historical identities stay marked unresolved.
