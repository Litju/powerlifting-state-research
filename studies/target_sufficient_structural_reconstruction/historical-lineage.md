# Surviving historical G2 evidence

The historical identity remains `G2 / ALI-542`, with registry alias
`pl_study_g2_structural_reconstruction`. The source registry classifies it as
“Target-sufficient structural reconstruction; retrospective study” and as a
research study rather than a benchmark version. The old study and result
homes state that no private reports, historical code, datasets, fitted models,
or results were copied into the repository. The old result-home label
`PROVEN` records bootstrap classification only; it does not verify a
scientific finding.

| Evidence item | Classification | Surviving source | Limit |
|---|---|---|---|
| G2 name, purpose, aliases | `HISTORICALLY_VERIFIED` metadata | `src/powerlifting_state_research/studies/registry.py`; historical G2 study README | Does not recover the original question wording or protocol |
| Attachment of G2 alias to the historical latent-capacity benchmark | `HISTORICALLY_VERIFIED` provenance metadata | `src/powerlifting_state_research/provenance/historical_sources.py`; `artifacts/registries/benchmark-registry.json` | An attached alias is not a G2 result |
| Parent world and task equations | `HISTORICAL_REPORTED` public projection | M2 world implementation and M3 benchmark specification | Usable as assumptions for new work; not proof these were G2's methods |
| Original G2 measurements, analysis code, fitted models, uncertainty, and numerical findings | `UNSUPPORTED_BY_EVIDENCE` | No rights-cleared artifacts survive in the public G2 study/result homes | No historical result is invented or recomputed |
| This RES-289 experiment | `NEW_PUBLIC_NATIVE_EXPERIMENT` | The separate realization and manifest in `results/studies/target_sufficient_structural_reconstruction/` | Not historical reproduction or recovery of G2 results |

Historical aliases and provenance are retained unchanged. No private
checkpoint, dataset, or historical-only artifact is an input. The exact
surviving files and their hashes are bound in the experiment manifest.
