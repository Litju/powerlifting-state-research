# RES-284 publication bundle

Start with report.md and executive-summary.md. Nine version profiles are under profiles/. Exact data tables and rights fields are under tables/; publication figures are under figures/. Every output is linked to verified source hashes in checksum-index.json.

Regenerate with uv run --locked python -m powerlifting_state_research.audits.res284_publication. Verify deterministic replay with uv run --locked python -m powerlifting_state_research.audits.res284_publication --check.
