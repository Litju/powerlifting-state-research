# Powerlifting State Research

Research on what can be inferred about an athlete's **latent capacity** from noisy performance observations, and how benchmark design changes the meaning of a successful forecast. All experimental evidence here is synthetic; real-athlete validity has not been demonstrated.

Start with the [G1–G4 studies](docs/studies/index.md), [benchmark audit evidence](docs/audits/index.md#evidence-reading-guide), or [reproducibility guide](docs/reproducibility.md). Read the [current G4 correction notice](docs/studies/g4-reader-corrections-v1.md) before interpreting its original report.

## Research problem

A strong performance can reflect lasting capacity, transient readiness, or measurement noise. These quantities need different targets and different evidence. Forecasting an observed lift accurately does not establish that a model has recovered the athlete's latent state or the mechanism of adaptation.

In state-space notation, the research problem is:

$$
x_{t+1}=f_\theta(x_t,u_t),\qquad y_t=g_\theta(x_t,u_t,\epsilon_t).
$$

Here $x_t$ is hidden state, $u_t$ is training exposure, $\theta$ contains athlete-specific parameters, and $y_t$ is the recorded observation. A task fixes the observed history, forecast origin, visible future plan, target, and scoring rule. In the executable capacity-change world, adaptation contributes to capacity $C_t$ and transient suppression separates it from expressed performance $P_t$. Assessment, prescribed load, and velocity observe that expression through a shared observation process. The forecast target is $\Delta C=C_{t_0+h}-C_{t_0}$ for each lift, rather than an observed-performance difference. See the [system model](docs/science/system-model.md), [implemented dynamics](src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dynamics.py), and [dataset contract](artifacts/dataset-cards/iid-latent-capacity-change-with-transient-expression-forecasting.md).

Partial observability matters because several channels can carry information about the same expressed quantity without independently revealing all latent coordinates. Known-generator inversion, parameter identification, participant-visible prediction, and causal intervention claims therefore require separate tests.

## What is implemented

The repository provides typed scientific contracts; a nine-entry benchmark registry; independently authored public dynamics, observation and IID data generation; prediction alignment and four-metric evaluation; saved model/comparator evidence; version-specific audit contracts and results; and four completed public-native studies. Scientific identities separately bind benchmark semantics, data realizations, models, predictions, and evaluations. See the [public contract](docs/contracts/public-benchmark-contract.md) and [source package](src/powerlifting_state_research/).

### Historical reconstruction and public-native research

The [registry](docs/benchmarks/index.md) contains **eight historical specimens across six shared worlds, plus one independent public-native variant**:

| Entry | Evidence status |
| --- | --- |
| [Class-normalized cross-lift five-target forecasting](docs/benchmarks/class-normalized-cross-lift-five-target-performance-forecasting.md) | Partial historical reconstruction |
| [Four-target load–velocity and competition forecasting](docs/benchmarks/four-target-load-velocity-and-competition-performance-forecasting.md) | Partial historical reconstruction |
| [Held-out final-origin five-target evaluation](docs/benchmarks/held-out-final-origin-five-target-performance-evaluation.md) | Partial historical reconstruction |
| [Capacity change with transient expression](docs/benchmarks/latent-capacity-change-with-transient-expression-forecasting.md) | Reproducible historical specification; historical production remains unimplemented publicly |
| [Latent-origin capacity change](docs/benchmarks/latent-origin-capacity-change-forecasting.md) | Partial historical reconstruction |
| [Observed-origin-referenced capacity change](docs/benchmarks/observed-origin-referenced-capacity-change-forecasting.md) | Partial historical reconstruction |
| [Seasonal five-target forecasting](docs/benchmarks/seasonal-five-target-load-velocity-performance-forecasting.md) | Partial historical reconstruction |
| [Schedule, exposure, and reporting heterogeneity](docs/benchmarks/performance-forecasting-under-schedule-exposure-reporting-heterogeneity.md) | Partial historical reconstruction |
| [IID capacity change with transient expression](docs/benchmarks/iid-latent-capacity-change-with-transient-expression-forecasting.md) | Independent executable PUBLIC_NATIVE benchmark |

The historical capacity-change production design used scrambled Sobol sampling. The public-native variant uses IID pseudorandom sampling and separate DatasetSpec, evaluation, and BenchmarkSpec identities. Shared mechanics do not make their numeric scores comparable. Historical G1–G4 names survive as metadata; the completed public-native studies are new experiments, not recovered historical results. [Naming provenance](docs/provenance/scientific-naming-decisions.md) records the retained aliases and scientific references.

## Studies and major findings

| Study | Bounded finding | Evidence |
| --- | --- | --- |
| G1 · Observation inversion (RES-287) | Exact expressed-performance inversion is insufficient for latent-capacity recovery; longer history averages can mix changing states. | [Report and negative findings](results/studies/observation_inversion/report.md), [protocol](studies/observation_inversion/protocol.json) |
| G2 · Structural reconstruction (RES-289) | Known-law reconstruction and local sensitivity do not prove global identification. Most noisy full-MLE starts did not converge. | [Report and convergence diagnostics](results/studies/target_sufficient_structural_reconstruction/report.md), [protocol](studies/target_sufficient_structural_reconstruction/protocol.json) |
| G3 · Public-surrogate reconstruction (RES-290) | Finite donor copying and predictive approximation do not establish source-mechanism recovery; the tested structural non-identification comparison remains inconclusive. | [Report](results/studies/public_surrogate_reconstruction/public-native/report.md), [protocol](studies/public_surrogate_reconstruction/protocol.json) |
| G4 · Synthetic-pretraining transfer (RES-292) | Corrected guarded inference demonstrates no >1 kg bootstrap-pretraining advantage over the compute-matched public-only control in the declared cells. | [Current correction notice](docs/studies/g4-reader-corrections-v1.md), [protocol](studies/synthetic_pretraining_transfer/protocol.json) |

G4's original pooled classifications were **98 equivalence, 9 inconclusive, 1 benefit**. RES-510's proposed Monte Carlo-guarded correction gives **97 equivalence, 11 inconclusive, 0 benefit** across 108 cells. Primary percentile and fixed-five-fit conditional interpretations remain separate. RES-511 confirms nonzero initial biases despite the frozen zero-bias specification: the results describe the executed learner. Independent scientific approval of the corrections remains pending.

## Models and benchmark audits

The saved IID panel contains seven model families: context mean, Ridge, histogram boosted stumps, mechanistic midpoint, compact neural, mechanistic plus Ridge residual, and a lift-shared temporal GRU expert. [Model documentation](docs/models/reference-models.md) links their protocols, fitted identities, predictions, and evaluations. Public-native weights are private; saved prediction evaluation does not imply inference from published checkpoints is available.

The [RES-284 synthesis](results/audits/res284-publication/report.md) reports 22 candidate fit/ensemble identities on 3,072 shared prediction keys and three targets. The temporal-expert ensemble leads 11 of 12 target/metric point-estimate comparisons; one expert seed leads squat MAE. This is a bounded descriptive result. All **264 paired-uncertainty cells are unsupported**, and all **36 historical cross-version numeric comparisons are rejected**. No universal model ranking or practical superiority follows. [Audit navigation](docs/audits/index.md#evidence-reading-guide) distinguishes validity axes, attack contracts, execution states, metric sensitivity, and missing evidence; it defines no universal validity score.

## Reproduce and inspect

For a clean locked environment and the ordinary test suite:

```sh
uv sync --locked --all-groups --python 3.12
uv run --locked --no-sync pytest
```

The [reproducibility guide](docs/reproducibility.md) separates artifact preservation from numerical replay and links the [CI local-parity commands](.github/workflows/README.md#local-parity). G3/G4 `--check` verifies existing evidence by rebuilding in memory; fresh generation requires a separate, untracked copy and must never overwrite frozen evidence. The [RES-299 verification record](docs/res299-validation.md) states what was actually executed.

| Location | Contents |
| --- | --- |
| [docs](docs/README.md) | Scientific overview, cards, claim boundaries, and navigation |
| [studies](studies/README.md), [results/studies](results/studies/README.md) | Frozen protocols, lineage, reports, diagnostics, and results |
| [audits](audits/README.md), [results/audits](results/audits/README.md) | Audit contracts, executions, and publication evidence |
| [data](data/README.md), [models](models/README.md) | Dataset and model specifications/manifests; no historical private data or weights |
| [artifacts](artifacts/README.md), [provenance](provenance/README.md) | Generated registries/schemas, rights, and origin records |

## Scientific limitations

All evidence is synthetic, with no demonstrated real-athlete validity or causal training-prescription claim. G2 uncertainty is approximate and excludes optimization uncertainty; noisy retained fits often failed convergence. G3 distribution intervals condition on the fixed donor sample. G4 intervals are approximate per-cell intervals, without family-wise scientific coverage, and use five fitting seeds conditional on fixed upstream data. Unavailable validation truth/entity mapping prevents RES-284 paired inference. Historical numeric comparisons are inadmissible. RES-293 information/representation ablations and RES-294 synthesis remain uncompleted; handoffs are not results. See [study limitations](docs/studies/index.md) and [benchmark claim boundaries](docs/benchmarks/claim-boundaries.md).

## Licensing and publication status

Code is [MIT](LICENSE); project-authored Markdown is [CC BY 4.0](LICENSE-DOCS). Per-artifact notices govern data/results; the public-native IID dataset requires attribution. The [RES-297 clarification](provenance/RES-297-prediction-provenance-clarification.md) records authorization for the four already-public expert prediction artifacts and explains the frozen evaluator's `NOASSERTION` fallback. It does not authorize checkpoint distribution or clear historical private material. This repository is a research portfolio, with independent scientific review pending; it is not a qualified formal archival release.
