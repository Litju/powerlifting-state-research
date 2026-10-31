# Normalization identity and artifact-specific rights

The original temporal-model artifact manifest contains inconsistent normalization metadata. This notice preserves the original and resolves the identity of the actual published file; it does not silently replace the frozen field.

| Record | SHA-256 |
| --- | --- |
| Frozen top-level `normalization.sha256` | `f5aade7089c5bd962140501f842d9aacd39d34af45928077c1228fbbbf6d21ca` |
| Artifact entry and actual published normalization JSON bytes | `f5aade7089c5bd962140501f842d9aacd39a34df45928077c1228fbbbf6d21ca` |
| Internal structured-statistics digest | `sha256:a8ad5b193e2d0e78ebdc341e550bed5be4b8352bfb72d3328a12add247c6f320` |

The [manifest](../models/published/public-native-temporal-expert/artifact-manifest.json), original inventory and actual file agree through the artifact entry. The internal statistics digest identifies structured values rather than serialized file bytes and is a separate identity. The summary field is a documented transcription discrepancy. A consumer trusting only that field will reject the authentic file. The [artifact verifier](../scripts/verify_published_model_artifacts.py) binds actual bytes to the original inventory and reports this specific discrepancy explicitly; it must reject any other conflict. No normalization statistics or model outputs are changed.

The [named model permission](model-artifact-redistribution.md) covers three public-native GRU checkpoints, 30 representation-study fitted states and their listed project-owned training metadata under MIT. It excludes historical private models and does not extend to private uncertainty coefficients or group factors. The canonical generated dataset is CC BY 4.0 with attribution; generated schema/manifest software files can separately be MIT. Some private experiment metadata uses overly broad MIT-for-dataset shorthand. That historical conflict is not repaired by relicensing data.

The [probabilistic study summary](../docs/studies/probabilistic-capacity-forecasting.md) contains newly authored owner-authorized public methods and aggregate findings under the documentation license. Original private cohorts, parameters, row scores, predictions, reports, audit, dossier and adapters remain excluded; no blanket release grant is inferred. Public inspection is available while their numerical reproduction requires artifact-specific access and rights clarification. Unresolved private redistribution does not mean the named public checkpoint identity is unknown.
