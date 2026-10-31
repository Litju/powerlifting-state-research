# Current model artifact release

This repository publishes 33 original model files: three public-native temporal GRU checkpoints and all 30 representation-study fitted states. Historical study identifiers below locate the exact original artifacts. The per-file SHA-256 values, model identities, source evidence, and rights records are in the [model artifact inventory](model-artifact-inventory.json).

Read the [normalization metadata clarification](../../provenance/normalization-and-rights-clarification.md) for the conflicting frozen summary hash and verified byte identity. The private uncertainty-head parameters and later probabilistic scoring adapters are outside this release.

For loading details, GPU-to-CPU replay limits, and the RES-293 configuration/seed mapping, see the [RES-274 card](public-native-temporal-expert/MODEL_CARD.md) and [RES-293 card](res293-definition-b/MODEL_CARD.md). Historical World-V2 checkpoints and other task candidates remain private while their redistribution rights are unresolved.

From a clean clone, verify every released hash and run the safe loading/inference checks with:

```sh
uv sync --locked
uv run python scripts/verify_published_model_artifacts.py
```

Optional CPU-only numerical replays are separate from the hash and loading check:

```sh
uv run python scripts/verify_published_model_artifacts.py --replay-res293
uv run python scripts/verify_published_model_artifacts.py --replay-res274-cpu
```

RES-293 requires byte-identical replay of all 60 original prediction files and performs no fitting. RES-274 compares its three seeds and ensemble with the saved GPU outputs; CPU differences are allowed up to 0.0167 kg per prediction and 0.000280 per evaluation metric. The measured maxima were 0.0166435 kg and 0.000279797. Frozen prediction and evaluation files are read-only inputs.

The release covers only project-owned PUBLIC_NATIVE artifacts. The authorization record is in [model-artifact-redistribution.md](../../provenance/model-artifact-redistribution.md); dataset attribution remains CC-BY-4.0.
