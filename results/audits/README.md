# Audits

## Scope

Executed audit outputs by scientific axis. Contract definitions and current evidence-state profiles live in `artifacts/registries/`, not in this results directory.

## Output record

Audit result manifests identify the audit axis, benchmark inputs, method, evidence, and limitations.

## RES-278 execution

Run `uv run --locked python -m powerlifting_state_research.audits.runner --check` for read-only registry/profile and M4 evidence reconciliation. Run the module without `--check` to write a new deterministic bundle under `results/audits/res278/`.

Each bundle contains one result state per registered attack/version, an audit-results manifest, and independent public-native stress realizations where an intervention ran. The bundle keeps the RES-277 six-state distinction and does not rewrite M3/M4 artifacts. A second run must use a new output directory; existing results are immutable.
