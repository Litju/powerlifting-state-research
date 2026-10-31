# Powerlifting State Research

Scientific software for studying **latent capacity forecasts from noisy performance histories** in a specified synthetic dynamical system. The research connects mechanistic simulation, scientific machine learning, probabilistic forecasting and benchmark validity. All experimental evidence is synthetic; real-athlete validity has not been demonstrated.

Start with the [system equations](docs/science/system-model.md), [research findings and claims](docs/studies/probabilistic-capacity-forecasting.md), [public study evidence](docs/studies/index.md), and [reproduction boundaries](docs/reproducibility.md). The [current model release](models/published/CURRENT_RELEASE.md) identifies the available weights. Independent external human methodological review remains pending.

## Scientific question

Observed strength can reflect lasting capacity, transient suppression and measurement noise. A good observed-performance forecast does not establish recovery of latent capacity or individual physiological parameters. The state-space question is

$$x_{t+1}=f_\theta(x_t,u_t),\qquad y_t=g_\theta(x_t,u_t,\epsilon_t).$$

Hidden state $x_t$, exposure $u_t$, athlete-specific parameters $\theta$ and observations $y_t$ have distinct roles. The executable task predicts $C_{t_0+h-1}-C_{t_0-1}$ for squat, bench press and deadlift, with origin day 224 and horizons 14, 28 and 56 days. Inputs contain histories through day 223, observed schedules and a declared future plan. Latent capacity, true time constants and future realized observations are excluded. See the [dataset card](artifacts/dataset-cards/iid-latent-capacity-change-with-transient-expression-forecasting.md) and [information contract](docs/contracts/public-benchmark-contract.md).

## Software and methods

Typed contracts bind world, population, observation, intervention, task, quantity of interest, realization, model and evaluation identities. Public algorithms include a deterministic simulator, noisy assessment/load/velocity observations, an IID generator, strict prediction alignment and four point-score metrics. Six standard comparator families accompany a three-seed lift-shared temporal GRU. Source and executable examples are indexed in the [reproducibility guide](docs/reproducibility.md).

The GRU is an ordinary data-driven predictor: it has no differential-equation residual loss, learned physical identification or physics-constrained training. Mechanistic knowledge enters the simulator, the declared mechanistic comparators and the later cessation-support restriction. That last probabilistic operation enforces a known synthetic support law after fitting. This is a bounded science-informed forecasting component, not evidence that the entire learning system is a physics-informed neural network. [Research positioning and references](docs/science/research-positioning.md) explain the distinction.

## Research findings

| Study | Finding and limitation |
| --- | --- |
| [Observation inversion](results/studies/observation_inversion/report.md) | Exact expressed-performance inversion is insufficient for latent-capacity recovery; averaging can mix changing states. |
| [Structural reconstruction](results/studies/target_sufficient_structural_reconstruction/report.md) | Local sensitivity does not prove global identification. Most noisy full maximum-likelihood starts did not converge. |
| [Public-surrogate reconstruction](results/studies/public_surrogate_reconstruction/public-native/report.md) | Donor copying and predictive approximation do not establish mechanism recovery; the tested non-identification comparison is inconclusive. |
| [Synthetic-pretraining transfer](docs/studies/g4-reader-corrections-v1.md) | Corrected guarded inference finds no demonstrated >1 kg bootstrap-pretraining advantage over the compute-matched public-only control. Original findings and initialization deviations remain preserved. |
| [Representation, learner and information ablations](results/studies/res293_representation_learner_information/report.md) | Six fixed procedures differ descriptively; uncertainty is not coverage-qualified and does not establish nonlinear necessity. [Bounded synthesis](results/studies/res294-definition-b-final-synthesis.md). |
| [Conditional uncertainty and support restriction](docs/studies/probabilistic-capacity-forecasting.md) | Conditional scale H improves macro CRPS over a calibrated plan/horizon baseline by 2.75%/2.96% on two same-law tests. Group calibration and truncation H_GT add small gains of 0.358%/0.313% over H on two subsequent tests. Both point-correction attempts failed. |
| [Controlled distribution shifts](docs/studies/probabilistic-capacity-forecasting.md#controlled-shifts) | Relative H_GT score gains survive two prescribed shifts within original parameter support. Absolute error increases; worst nominal 90% subgroup coverage is **81.25%/79.30%**. Conditional reliability is not established. |

The last two rows summarize restricted studies; their raw evidence, fitted uncertainty parameters and scoring adapters are **not distributed here**. [Public versus restricted reproduction](docs/reproducibility.md#public-and-restricted-reproduction) separates method inspection from numerical reproduction. They use two independent test parents per stage and shared fitted models, not independent training replications. Sequential hypothesis selection and incomplete historical chronology limit confirmatory interpretation.

## Benchmarks, model comparisons and availability

The [nine-entry registry](docs/benchmarks/index.md) contains eight historical specimens across six shared worlds and one independent executable IID variant. Historical scrambled-Sobol production and public IID sampling have different identities; shared mechanics do not make their scores comparable. [Naming provenance](docs/provenance/scientific-naming-decisions.md) retains original aliases without treating them as current scientific names.

The [model comparison](docs/models/reference-models.md) contains seven families and 22 candidate fit/ensemble identities on one canonical IID realization. The GRU ensemble leads 11 of 12 target/metric point comparisons; one seed leads squat MAE. All 264 paired-uncertainty cells are unsupported, and all 36 historical cross-version numerical comparisons are rejected. No universal ranking or statistical superiority follows. No trained cross-family model-of-models or learned stacking system is present; three-seed averaging is the demonstrated ensemble.

The [authorized artifact release](models/published/CURRENT_RELEASE.md) contains three original GRU checkpoints and 30 representation-study fitted states. [Artifact verification](scripts/verify_published_model_artifacts.py) checks hashes, identities and safe loading. Read the [normalization metadata clarification](provenance/normalization-and-rights-clarification.md): an inconsistent frozen summary hash is disclosed alongside the verified file hash. Historical private checkpoints remain excluded.

## Reproduce and inspect

```sh
uv sync --locked --all-groups --python 3.12
uv run --locked --no-sync pytest
uv run --locked --no-sync python scripts/verify_published_model_artifacts.py
uv run --locked --no-sync python scripts/check_documentation_links.py
```

Use a full Git clone for frozen-history checks. The [reproducibility guide](docs/reproducibility.md) distinguishes byte preservation, numerical replay and fresh generation; the [CI commands](.github/workflows/README.md#local-parity) cover Linux Python 3.11–3.13, strict typing, lint, security, exports and isolated wheel loading. No training or new probabilistic-study test generation is required for repository qualification.

| Location | Contents |
| --- | --- |
| [Science and studies](docs/README.md) | Equations, literature, methods, evidence, negative findings and claim limits |
| [Models](docs/models/reference-models.md), [data](data/README.md) | Specifications, rights and available artifacts |
| [Study protocols](studies/README.md), [results](results/README.md), [audits](docs/audits/index.md) | Frozen evidence and correction notices |
| [Provenance](provenance/README.md) | Per-file origins, artifact authorization and metadata discrepancies |
| [Engineering qualification](REPOSITORY_ENGINEERING_CLOSEOUT_REPORT.md) | Cleanup dispositions, verification receipts and remaining limitations |

## Rights and scientific limits

Code is [MIT](LICENSE); authored Markdown is [CC BY 4.0](LICENSE-DOCS). The public generated dataset requires CC BY 4.0 attribution; individual manifests govern model/data/result artifacts. [Model redistribution authority](provenance/model-artifact-redistribution.md) covers named public artifacts only. The [public/private boundary](docs/current-research-state.md#artifact-access-and-rights) excludes restricted cohorts, truth, predictions, uncertainty parameters and manuscripts.

No real-athlete validation, universal out-of-distribution guarantee, confirmed conditional reliability, causal training prescription, physiological identification or external human peer review has been established. Engineering qualification is separate from scientific acceptance and formal archival release; no DOI or publication claim is made.
