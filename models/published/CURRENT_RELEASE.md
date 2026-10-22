# Current model artifact release

The recovery branch publishes 33 original model files: three RES-274 PUBLIC_NATIVE temporal expert checkpoints and all 30 RES-293 Definition B fitted states. The per-file SHA-256 values, model identities, source evidence, and rights records are in the [model artifact inventory](model-artifact-inventory.json).

For loading details, GPU-to-CPU replay limits, and the RES-293 configuration/seed mapping, see the [RES-274 card](public-native-temporal-expert/MODEL_CARD.md) and [RES-293 card](res293-definition-b/MODEL_CARD.md). Historical World-V2 checkpoints and other task candidates remain private while their redistribution rights are unresolved.

From a clean clone, verify every released hash and run the safe loading/inference checks with:

```sh
uv sync --locked
uv run python scripts/verify_published_model_artifacts.py
```

The release covers only project-owned PUBLIC_NATIVE artifacts. The authorization record is in [model-artifact-redistribution.md](../../provenance/model-artifact-redistribution.md); dataset attribution remains CC-BY-4.0.
