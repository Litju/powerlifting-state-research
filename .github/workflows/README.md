# Public CI

[`ci.yml`](ci.yml) runs on PRs to `main`, pushes to `main`, and manual dispatch with read-only repository permissions and the checked-in lock. Five jobs cover:

| Job | Python | Checks |
| --- | --- | --- |
| Quality / integrity | 3.12 | Gitleaks JSON full-history scan, locked sync, Ruff, strict mypy, exports, repository integrity, Markdown links/anchors, published model hashes/loading, frozen-source preservation, execution-era RES-284 publication replay |
| Compatibility (three jobs) | 3.11, 3.12, 3.13 | Locked sync, package import, pytest; opt-in full IID production skipped |
| Package smoke | 3.12 | Build sdist/wheel, isolated wheel install with locked runtime/research dependencies, dependency imports, model instantiation, nine registry records and distinct historical/public-native identities |

## Local parity

Use a full Git clone and Gitleaks 8.18.4 on PATH, matching the checksum-pinned installation in the workflow. From the repository root:

```sh
uv sync --locked --all-groups --python 3.12
uv run --locked --no-sync python scripts/verify_gitleaks.py
uv run --locked --no-sync ruff check .
uv run --locked --no-sync ruff format --check .
uv run --locked --no-sync mypy
uv run --locked --no-sync pytest
uv run --locked --no-sync python -m powerlifting_state_research.exports --check
uv run --locked --no-sync python scripts/check_repository_integrity.py
uv run --locked --no-sync python scripts/check_documentation_links.py
uv run --locked --no-sync python scripts/verify_published_model_artifacts.py
uv run --locked --no-sync python scripts/verify_release_freeze.py
uv run --locked --no-sync python scripts/verify_res284_execution.py
```

To exercise the isolated wheel job without repository `dist/` output, use the same locked dependency setup and assertions as CI:

```sh
parity_tmp="$(mktemp -d)"
uv build --sdist --wheel --no-build-isolation --out-dir "$parity_tmp/psr-dist"
UV_PROJECT_ENVIRONMENT="$parity_tmp/psr-wheel" uv sync --locked --no-default-groups --group research --no-install-project --python 3.12
uv pip install --no-deps --python "$parity_tmp/psr-wheel/bin/python" "$parity_tmp/psr-dist"/*.whl
(
cd "$parity_tmp"
"$parity_tmp/psr-wheel/bin/python" -I - <<'PY'
import sys
from pathlib import Path

import numpy
import scipy
import torch
import powerlifting_state_research
from powerlifting_state_research.models.temporal_expert import (
    LiftSharedTemporalExpert,
    parameter_count,
)
from powerlifting_state_research.studies.target_sufficient_structural_reconstruction import model_with_jacobian
from powerlifting_state_research.studies.target_sufficient_structural_reconstruction_protocol import STUDY_ID
from powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting.prediction import PREDICTION_CONTRACT
from powerlifting_state_research.evaluation.identity import METRIC_IDENTITIES
from powerlifting_state_research.evaluation.prediction import PREDICTION_SCHEMA_ID
from powerlifting_state_research.registry import BENCHMARKS, resolve_benchmark
from powerlifting_state_research.contracts.benchmark import BenchmarkIdentityAuthority

assert Path(powerlifting_state_research.__file__).resolve().is_relative_to(
    Path(sys.prefix).resolve()
), powerlifting_state_research.__file__
assert numpy.__version__ == "2.4.4"
assert scipy.__version__ == "1.18.1"
assert torch.__version__.startswith("2.9.1")
model = LiftSharedTemporalExpert()
assert isinstance(model, torch.nn.Module)
assert parameter_count(model) > 0
assert STUDY_ID == (
    "psr:study:target-sufficient-structural-reconstruction-public-native"
    "@1.0.0~12aafcbac716"
)
assert callable(model_with_jacobian)
assert len(BENCHMARKS) == 9
historical = resolve_benchmark(
    "latent_capacity_change_with_transient_expression_forecasting"
)
assert historical.identity_mintable
assert historical.semantic_digest == (
    "sha256:fbfbe59eb0a8e94b12b424c6d6837dfd455a6c5a55084bb2898b53f741cc6472"
)
public = resolve_benchmark(
    "iid_latent_capacity_change_with_transient_expression_forecasting"
)
assert public.identity_authority is BenchmarkIdentityAuthority.PUBLIC_NATIVE
assert public.semantic_digest != historical.semantic_digest
assert public.benchmark_id == (
    "psr:benchmark-spec:iid-latent-capacity-change-with-transient-expression-forecasting"
    "@1.0.0~f99463d55ba0"
)
assert public.semantic_digest == (
    "sha256:f99463d55ba0902595a1866032ba94b803ac97d9b4985a89e208293da9c7fed0"
)
assert public.semantic_identity is not None
assert public.semantic_identity.evaluation_id == (
    "psr:evaluation:iid-latent-capacity-change-four-metric-validation"
    "@1.0.0~cd4fe982e7b8"
)
assert public.semantic_identity.dataset_spec_id == (
    "psr:dataset-spec:latent-capacity-transient-iid-sampling-design"
    "@1.0.0~1d079eb645ed"
)
assert {item.metric_id for item in METRIC_IDENTITIES} == {
    "psr:metric:rmse@1.0.0~0a9b0918a7aa",
    "psr:metric:mae@1.0.0~7319598a8a18",
    "psr:metric:r-squared@1.0.0~00bad728358d",
    "psr:metric:sre-population-sd-ddof-0@1.0.0~f3341587fd14",
}
assert PREDICTION_CONTRACT.information_boundary.history_observation_last_day == 223
assert PREDICTION_SCHEMA_ID == (
    "psr:prediction-schema:iid-latent-capacity-change-jsonl-row"
    "@1.0.0~cad5c74acd66"
)
assert historical.semantic_identity is not None
assert historical.semantic_identity.evaluation_id == (
    "psr:evaluation:world-v2-canonical-sre-evaluation@1.0.0~2b606bcf527f"
)
print("PASS: wheel imports; native evaluation identity and frozen historical digest match")
PY
)
```

The locked `research` group supplies SciPy/stubs with Python-version conditions; no ad-hoc dependency install is needed. CI verifies Linux Python 3.11/3.12/3.13. Other platforms and original G1–G4 numerical replay are not covered. See [reproducibility](../../docs/reproducibility.md) for public IID regeneration and G3/G4 `--check` semantics, and the [RES-299 verification record](../../docs/res299-validation.md) for commands actually run.

The public Gitleaks/integrity checks do not consume private historical fingerprints. Engineering checks do not imply formal archival release qualification or scientific approval. Authorized checkpoints are available in the [current model release](../../models/published/CURRENT_RELEASE.md); private uncertainty parameters remain excluded. No new release workflow is introduced here.
