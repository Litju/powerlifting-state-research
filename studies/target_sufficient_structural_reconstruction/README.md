# Target Sufficient Structural Reconstruction

## Study identity

Target-sufficient structural reconstruction; retrospective study.

This home is classified as **research study, not benchmark version**. Evidence status at bootstrap: **PROVEN**. A study is not a benchmark version.

## Research record

The historical G2 record contains metadata only. Its bootstrap label `PROVEN` is not a scientific result. No rights-cleared historical protocol, measurements, fitted models, or quantitative findings survive in the public study/result homes. See [historical-lineage.md](historical-lineage.md).

RES-289 adds a separate public-native study realization under the preserved G2 home. It does not reproduce or relabel historical results. The protocol, estimands, model assumptions, split, methods, seeds, solver settings, uncertainty rules, and failure states are frozen in [protocol.json](protocol.json) before outcomes are generated. [formal-specification.md](formal-specification.md) defines the target and identifiability boundaries.

## Bootstrap boundary

No private reports, historical code, datasets, models, or results are copied into this directory. Historical study aliases remain in the study registry's provenance fields. M0–M5 and RES-287 are frozen. The new realization uses the public M2 world and observation law with a separate entity-disjoint split; canonical M3–M5 data and result artifacts remain unchanged.

The study runner uses optional SciPy tools without changing the core project lock, which remains bound to the frozen M5 replay. For byte-for-byte replay, use Python 3.12.13 and SciPy 1.18.1 as recorded in the manifest; the Python 3.11 compatibility job uses SciPy 1.16.3. Install the study tools into the synchronized environment, then run the deterministic check without resyncing:

```sh
uv pip install --python .venv/bin/python scipy==1.18.1 scipy-stubs==1.18.1.1
uv run --locked --no-sync python -m powerlifting_state_research.studies.target_sufficient_structural_reconstruction --check
```
