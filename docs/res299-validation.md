# RES-299 documentation verification

**Point-in-time note:** This record predates the authorized RES-293/RES-294 campaign. The current study results and closeout limits are in the [Definition B final synthesis](../results/studies/res294-definition-b-final-synthesis.md); the checks below remain the record of the earlier 2026-10-18/19 verification.

Scope: research portfolio documentation from main `b6ac38adc866ee36c829841d6a39ce87053ab691`, on `docs/res299-research-portfolio`, 2026-10-18; final documentation repair verified 2026-10-19. The draft PR's checks provide candidate CI results; this record distinguishes local checks from historical receipts and numerical replays. No independent scientific approval is asserted.

## Local engineering verification

The following commands were recorded for the original 2026-10-18 portfolio verification on Linux, Python 3.12.13, uv 0.12.2:

```sh
uv sync --locked --all-groups --python 3.12
uv run --locked --no-sync ruff check .
uv run --locked --no-sync ruff format --check .
uv run --locked --no-sync mypy
uv run --locked --no-sync pytest
uv run --locked --no-sync python scripts/check_repository_integrity.py
uv run --locked --no-sync python -m powerlifting_state_research.exports --check
uv run --locked --no-sync python scripts/verify_release_freeze.py
uv run --locked --no-sync python scripts/verify_res284_execution.py
```

The locked environment installation passed. The commands above do not select an isolated environment for pytest; the explicit isolated rerun is recorded below. Ruff and format checks passed; strict mypy checked 111 source files; 23 generated exports were current. Preservation verified 481 frozen upstream files, 17 G4 source files, and 160 publication files with no changes. RES-284 replay verified 184 execution-era source files and 41 builder outputs, then the current 42-file bundle. Its reported current-source drift includes the mutable audit documentation and appended origin ledger; no historical hash was replaced.

The [CI local-parity wheel block](../.github/workflows/README.md#local-parity) was executed verbatim: sdist/wheel build, locked isolated runtime/research dependency installation, package and NumPy/SciPy/Torch imports, model instantiation, nine registry records, historical digest, and independent public-native identities passed. The build outputs stayed under a temporary directory and were not published.

Gitleaks 8.18.4 was downloaded from the workflow's release URL, checked against its pinned archive SHA-256 `ba6dbb656933921c775ee5a2d1c13a91046e7952e9d919f9bac4cec61d628e7d`, and used by `scripts/verify_gitleaks.py`; its full-history JSON report had zero findings.

The original reported full pytest result was **226 passed, 1 skipped** (53.56 s). The explicit isolated-environment execution below supersedes the earlier ambiguous environment description. The skip is the opt-in full-production regeneration gate. Repository integrity passed for nine benchmark records and 647 origin-ledger rows, including RES-275 validation isolation and artifact hashes. During drafting, preservation/tests rejected an edit to the hash-bound roadmap and the incomplete new-document inventory; the roadmap was restored and the two new prose files registered before the final passing run. No frozen verifier or scientific hash was relaxed.

## 2026-10-19 isolated pytest verification

A fresh empty temporary environment was created, populated solely from the lock, and selected explicitly for both setup and pytest in the same shell:

```sh
set -e
clean_env="$(mktemp -d)"
UV_PROJECT_ENVIRONMENT="$clean_env" uv sync --locked --all-groups --python 3.12
UV_PROJECT_ENVIRONMENT="$clean_env" uv run --locked --no-sync pytest
```

The isolated rerun completed on Linux with Python 3.12.13 and uv 0.12.2: **226 passed, 1 skipped** (41.40 s). The skipped test is the opt-in full-production regeneration gate. Local documentation checks, `scripts/verify_release_freeze.py`, and `scripts/check_repository_integrity.py` were rerun successfully within their documented scopes; the two frozen G4 report link defects remain disclosed below. No numerical evidence was regenerated, and no frozen artifact was modified.

## Link, figure, and scientific evidence checks

A one-off Python standard-library scan covered 146 Markdown files, 424 local links, and 19 well-formed SVGs. It checked local Markdown inline/reference links, local heading fragments, HTML link/image targets, and XML parsing of tracked SVGs. It excluded fenced code and external URLs. There are two preserved link defects in the frozen [original G4 report](../results/studies/synthetic_pretraining_transfer/public-native/report.md): its introductory protocol and lineage destinations are one directory short. The separately identified [current reader notice](studies/g4-reader-corrections-v1.md#editorial-corrections-to-the-original-report) provides working links and corrects the denominator to 9 cells per population, 18 combined. These known historical defects are disclosed rather than silently edited or reported as a completely clean original corpus. External URL availability and visual rendering in every Markdown client were not checked.

Direct CSV counts verified all four 108-cell G4 classification tracks against [comparison.csv](../results/corrections/RES-510-v1/comparison.csv): original 98/9/1/0, corrected percentile 97/10/1/0, corrected guarded 97/11/0/0, and fixed-five-fit conditional guarded 99/8/1/0 (equivalence/inconclusive/benefit/harm). The [RES-284 uncertainty table](../results/audits/res284-publication/tables/paired-uncertainty-evidence.csv) has 264 unsupported cells, and the [historical-comparison table](../results/audits/res284-publication/tables/historical-comparability.csv) has 36 rejected comparisons. No new intervals or classifications were computed.

Both correction packages' checksum inventories matched all four listed entries each. RES-510's nine bound source hashes and RES-511's published-artifact/source bindings matched. G1/G2/G3 descriptions and numerical examples were checked against their linked reports, protocols, convergence diagnostics, and limitation sections. Model family counts, metric dependence, panel size, lead counts, and ranking limitations follow the frozen RES-283/284 reports and comparator/model cards. The [study index](studies/index.md), [audit guide](audits/index.md#evidence-reading-guide), and [model guide](models/reference-models.md) link exact evidence paths.

Licensing/provenance language was checked against LICENSE, LICENSE-DOCS, the per-artifact cards and manifests, and the [RES-297 clarification](../provenance/RES-297-prediction-provenance-clarification.md). New prose is recorded in the existing origin ledger. No author identities, citations, or review approvals were invented.

## Not run and interpretation limits

Public IID generation, the opt-in two-generation gate, G1–G4 full numerical replay, G3/G4 `--check`, and the RES-510 bootstrap campaign verifier were not run under the no-numerical-regeneration instruction. Their actual behavior and correct commands are documented in [reproducibility](reproducibility.md). Ordinary pytest uses small synthetic test fixtures; this is distinct from regenerating frozen study evidence. Earlier RES-281/298 execution receipts are attributed to their original work, not claimed as new executions.

No GPU training, new experiment, checkpoint publication, formal archive, DOI, tag, or merge was performed. Evidence remains synthetic-only; historical numeric comparisons and the 264 uncertainty cells remain inadmissible/unsupported. RES-510/511 await independent scientific approval, and RES-293/294 research remains uncompleted. Engineering checks do not resolve those scientific limitations.
