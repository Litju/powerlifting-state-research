# Observation inversion and latent-state observability

RES-287 is an independent public-native study, separate from the historical G1 metadata and all benchmark identities. Read [historical lineage](historical-lineage.md), [formal specification](formal-specification.md), and the frozen [protocol](protocol.json).

The protocol is committed before executing the study. No training, tuning, neural tournament, historical private artifacts or canonical M3/M4 data are used. Methods are analytical inversion, last-observation persistence and history means. All realizations belong to this study only.

Reproduce from the repository root:

```sh
uv run --locked python -m powerlifting_state_research.studies.observation_inversion
uv run --locked python -m powerlifting_state_research.studies.observation_inversion --check
```

The runner verifies the frozen protocol and mechanics hashes before calculation. It rejects overwriting divergent artifacts. The results manifest binds scientific identity, separate realization and split identity, source hashes, estimator definitions, raw errors, truth, diagnostics, uncertainty tables and figures. See the [research report](../../results/studies/observation_inversion/report.md) and [RES-289 handoff](../../results/studies/observation_inversion/RES-289-handoff.md).
