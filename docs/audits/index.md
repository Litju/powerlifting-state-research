# Cross-benchmark audit suite

The audit suite asks validity questions across benchmark formulations. An audit axis is not a benchmark version, study result, or substitute for a benchmark's own evaluation.

| Audit axis | Question |
|---|---|
| reproducibility | Exact regeneration and identity agreement. |
| information_leakage | Information-boundary and target leakage. |
| observability | Latent-state and target observability. |
| structural_reconstructability | Structural target/world reconstruction. |
| public_surrogate_reconstructability | Reconstruction from participant-public inputs. |
| simple_model_frontier | Strong simple/reference comparator frontier. |
| representation_dependence | Representation and input-transform dependence. |
| machine_learning_load_bearing | Learned-method contribution under controlled alternatives. |
| history_cadence_sensitivity | History length and observation-cadence sensitivity. |
| intervention_robustness | Target-domain and intervention-regime robustness. |
| model_ranking_stability | Model ranking stability across benchmark formulations. |

Each audit should declare the threat or question, benchmark/data/model identities, changed and held-fixed axes, method, result manifest, uncertainty, and claim limit. The bootstrap declares the homes only; it includes no audit runner or historical result bundle.
