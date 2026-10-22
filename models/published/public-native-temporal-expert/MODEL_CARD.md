# RES-274 PUBLIC_NATIVE temporal expert

This release contains the original three seed checkpoints from RES-274 run `20261008T071545Z-827f338c`. They are the `PUBLIC_NATIVE` model `psr:model:public-native-lift-shared-temporal-gru-capacity-change@1.0.0~34d23123138f`, trained under protocol `psr:training-protocol:public-native-temporal-expert@1.0.0~dc47230f3465` on the generated IID realization `psr:dataset-realization:latent-capacity-transient-iid-production@sha256:2659bad8979e5a00829a50580c14bfbc90579c4520c46c8159dec8c34f1c8cad`.

The original Drive bundle SHA-256 is `fa31764220dbca936275b07965e7b4b4adb146251fc38db063dc5e88de8eaec4`. All three checkpoint bytes match their sealed SHA-256 identities. The publication includes the original train-only normalization, three training histories, runtime and training receipts, checkpoint seal, and final source receipts. Existing checkpoint manifests, fitted-instance records, predictions, and EvaluationResults remain at their original repository paths and match the same source inventory.

| Seed | Checkpoint ID | SHA-256 | Selected epoch |
| ---: | --- | --- | ---: |
| 383001 | `psr:checkpoint:public-native-temporal-expert-seed-383001@sha256:f8889305226cbac69874a2a983809e2b12adfdbfb8dd6446dbce932ac02904bb` | `f8889305226cbac69874a2a983809e2b12adfdbfb8dd6446dbce932ac02904bb` | 54 |
| 383002 | `psr:checkpoint:public-native-temporal-expert-seed-383002@sha256:eb6c858e20e3a0cba5a542db605494359df83c15fac54b068ed938866d1398c4` | `eb6c858e20e3a0cba5a542db605494359df83c15fac54b068ed938866d1398c4` | 44 |
| 383003 | `psr:checkpoint:public-native-temporal-expert-seed-383003@sha256:c8f6bb329ee6b9e37155d95515e071b98d0aacf720f163bbe060804a0ecdef18` | `c8f6bb329ee6b9e37155d95515e071b98d0aacf720f163bbe060804a0ecdef18` | 68 |

The original `checkpoint-publication.json` retains its run-time `release pending` status. The separate [artifact manifest](artifact-manifest.json) records the later owner authorization and current Git distribution state. The original predictions, metrics, and evaluation records were not regenerated or modified.

## Loading

Install the locked project environment, then verify the release:

```sh
uv sync --locked
uv run python scripts/verify_published_model_artifacts.py
```

Load a seed model and its matching normalization with the frozen public implementation:

```python
import json
from pathlib import Path

from powerlifting_state_research.models.temporal_expert import (
    LiftSharedTemporalExpert,
    NormalizationStats,
    load_weights,
)

model = load_weights(
    Path("models/published/public-native-temporal-expert/checkpoints/seed-383001.pt"),
    LiftSharedTemporalExpert(),
)
stats = NormalizationStats.from_dict(
    json.loads(
        Path(
            "models/published/public-native-temporal-expert/source-run/normalization/normalization-stats.json"
        ).read_text()
    )["stats"]
)
```

Use `predict` for one seed or `predict_three_seed_ensemble` for the recorded ensemble rule. Checkpoint loading uses PyTorch's restricted `weights_only=True` loader.

## Numerical replay

The source run used PyTorch 2.9.1+cu128 on an NVIDIA RTX PRO 6000 Blackwell. A replay with PyTorch 2.9.1+cpu, the original 256-row inference batching, the exact normalization, and the original RES-271 evaluator reproduced the saved predictions numerically but not byte-for-byte. Across the three seeds and ensemble, the maximum absolute prediction difference was 0.0167 kg and the mean absolute difference was 0.00069 kg. The largest change in any saved evaluation metric was 0.000280. The saved GPU prediction and EvaluationResult files remain unchanged. The verification receipt records per-seed details.

## Rights and scope

The three weights and associated training metadata are project-owned PUBLIC_NATIVE artifacts released under MIT with repository-owner authorization recorded in [the rights note](../../../provenance/model-artifact-redistribution.md). They were fitted on project-generated synthetic data; the dataset itself remains CC-BY-4.0 and requires attribution. The model does not use real-athlete data or third-party pretrained weights. Historical World-V2 expert checkpoints are a separate model family and remain private while their redistribution rights are unresolved.
