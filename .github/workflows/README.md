# Public CI

[`ci.yml`](ci.yml) runs on pull requests to `main`, pushes to `main`, and manual dispatch. It has read-only repository permissions and uses the checked-in `uv.lock`.

| Job | Python | Checks |
|---|---|---|
| Quality / integrity | 3.12 | Locked sync, Ruff check and format, strict mypy, generated-export drift, repository integrity and rights ledger |
| Compatibility (Python 3.11/3.12/3.13) | 3.11, 3.12, 3.13 | Locked sync, package import, full pytest suite |
| Package smoke | 3.12 | Build sdist and wheel, install wheel in an isolated environment, verify import, nine benchmark records, frozen historical digest, and distinct public-native identity |

## Local parity

Run from a clean checkout with Python 3.12 and `uv`:

```sh
uv sync --locked --all-groups --python 3.12
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked pytest
uv run --locked python -m powerlifting_state_research.exports --check
uv run --locked python scripts/check_repository_integrity.py
uv build --sdist --wheel --no-build-isolation
wheel_env="$(mktemp -d)"
uv venv "$wheel_env"
uv pip install --no-deps --python "$wheel_env/bin/python" dist/*.whl
(
  cd "$wheel_env"
  "$wheel_env/bin/python" -I - <<'PY'
import sys
from pathlib import Path

import powerlifting_state_research
from powerlifting_state_research.registry import BENCHMARKS, resolve_benchmark

assert Path(powerlifting_state_research.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert len(BENCHMARKS) == 8
benchmark = resolve_benchmark("latent_capacity_change_with_transient_expression_forecasting")
assert benchmark.identity_mintable
assert benchmark.semantic_digest == "sha256:fbfbe59eb0a8e94b12b424c6d6837dfd455a6c5a55084bb2898b53f741cc6472"
PY
)
```

The integrity command uses public repository rules only. `PUBLIC_CI_SAFETY_SCAN != PRIVATE_HISTORICAL_FINGERPRINT_SCAN`; private historical fingerprint comparison remains local/pre-release and is reserved for M7 hardening. M7 will add release-grade packaging, archival verification, and heavy artifact validation. CI does not consume private fingerprint data.
