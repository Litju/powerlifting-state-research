# RES-509 — Independent audit preservation and baseline qualification

Scientific v1.0 remains **NO-GO**. PR #27 must remain **DRAFT** pending independent review.
Baseline: `de014231569442c7e83d1774877a8b92a9abc314`.
Initial candidate reviewed: `da5309bf5a18a4dd6dd145737fffc1f49ccf81f8`.

## Evidence recovered on 2026-10-14

The original audit directory was available. Its 90 top-level regular evidence files
were independently hashed and copied byte-for-byte to an owner-only local bundle
outside the repository. All entries in the original checksum index matched; all
58 command records were recovered. Environment trees, historical private artifacts,
and the auditor's checkout were not copied or inspected. No remote backup has been
established: local retention is not archival publication.

[Evidence inventory](RES-509-evidence-inventory.json) gives file sizes, independent
SHA-256 values, original-index comparison and content classification. Reviewed
public synthetic G4 scripts, sensitivity results and summary metadata are separated
from unreviewed operational/security logs. Only sanitized metadata is published here.
Raw logs remain restricted; hashes do not grant redistribution permission.

The previously asserted textual-report retention and specific report SHA-256 were
not independently established. That claim is withdrawn. The separate textual report
is **NOT_RECOVERED**; recovering the command ledger does not recover that narrative.
The previously asserted four passing tests were independently executed before repair
and passed; final regression results and exact commands are recorded below.

Recovered G1–G4 logs report original execution PASS; the RES-284 log reports FAIL at
`results/audits/res284-publication/checksum-index.json`. These are recovered historical
receipts, not newly executed study gates. Independent G4 analysis receipts record
6,804 comparisons with maximum difference 0, shared-entity sensitivity and nonzero
initial biases. Preservation does not adjudicate those scientific findings.

## Frozen dependency and compatibility qualification

[Qualification receipt and dependency map](RES-509-qualification.json) binds every
listed path to independently read baseline Git bytes and candidate worktree bytes.
Git replacement objects and ambient Git-directory overrides are disabled. A separate
clean detached checkout pins the baseline; neither main nor its scientific files
were changed.

| Scope | Paths | Byte-preservation verdict |
| --- | ---: | --- |
| G4 frozen upstream dependencies | 481 | PASS |
| G4 execution-source records | 17 | PASS |
| G1 publication bundle | 14 | PASS |
| G2 publication bundle | 28 | PASS |
| G3 publication bundle | 37 | PASS |
| G4 publication bundle | 39 | PASS |
| RES-284 publication bundle | 42 | PASS |

The 160 publication files include README files. Original protocols, fitted states,
predictions, reports, manifests and checksum indexes remain byte-identical. The G4
protocol also matches pre-fit commit `63098ca91120d2f31b3926098ffd52da190affbf`.
The provenance ledger preserves its original prefix and only appends new entries.

Independent static publication checks verify manifest outputs, G3/G4 checksum-index
entries, G4 input hashes and G1–G4 source records. All recorded publication/output
hashes match. Three RES-284 historical source references to the origin ledger differ
from baseline/current bytes; their recorded hash resolves exactly to historical
commit `b2b664de6bba6372e61afc1a147255a7daecb8a1`. This source-version drift explains
why baseline/current-source replay must not be inferred from preservation success.
G1/G2 have manifest output maps rather than separate SHA256SUMS files.

Do not edit any of the 481 dependencies, the 17 execution sources, or original
publication bundles in place. This includes `res284_publication.py`, G3 source and
RES-284's checksum index. Future corrections require separately versioned validators
or errata with execution-era source resolution. Original G4/RES-292 protocol and
results remain the authority for what executed.

## Verifier repairs and outcomes

The verifier now rejects symlink files/parents, missing evidence, ignored/untracked
or staged additions within publication directories, and protected changes in HEAD
or index hidden by restored worktree bytes. It explicitly protects the protocol and
frozen evidence map. Evidence output must be outside the worktree and atomic output
replacement cannot mutate a protected file through an external hardlink. Malformed
maps and unsafe paths cannot qualify as PASS. Git evidence uses exact commit objects
without replacement refs. These behaviors have disposable-Git regression coverage.

| State | Meaning |
| --- | --- |
| PASS | Executed byte/hash preservation checks succeeded for the declared scope |
| FAIL | A verified preservation mismatch or unsafe output target |
| NOT_RUN | Required Git evidence unavailable, or numerical replay not executed |
| INCONCLUSIVE | Malformed/unusable evidence or scientific release qualification unresolved |
| UNSUPPORTED | Private historical replay excluded from this public verifier |

Missing evidence is never PASS. Structured non-PASS receipts are written for unavailable
Git objects and malformed evidence. Numerical replay and scientific/rights qualification
have separate states even when byte preservation passes.

Use a full-history checkout and keep the output outside it:

```sh
.venv/bin/python scripts/verify_release_freeze.py --baseline de014231569442c7e83d1774877a8b92a9abc314 --json-out ../psr-res509-freeze.json
```

Final regression: **19 passed**. Full pytest: **174 passed, 1 skipped** (opt-in
production regeneration). Ruff lint/format, strict package and verifier mypy,
generated exports, repository integrity and Git object integrity all passed.
Both candidate and detached baseline preservation scans passed.

The qualification JSON records exact commands, exit codes, log hashes, environment,
source hashes and per-file results. The environment includes SciPy installed outside
the lock; passing checks here do not resolve the recovered pure-lock dependency failure.

## Separate verification tracks and remaining blockers

Original execution replay uses the pinned baseline and historical source versions;
its fresh numerical G1–G4 replay is **NOT_RUN** in this preservation task. Recovered
historical receipts are retained without changing their scripts or results. Current
release qualification must use separately versioned validators/errata and independently
review scientific uncertainty, protocol deviations, rights and packaging completeness.

- Independent review of this PR's coverage, receipts and retention is still required.
- RES-284 baseline-source replay failure remains unresolved; historical source resolution
  is evidence, not a newly executed successful replay.
- RES-510 uncertainty adjudication and RES-511 protocol disclosure remain dependencies;
  neither was started here.
- RES-297 rights/security clearance, RES-298 locked environments and reproducibility,
  and RES-299–RES-301 documentation/archive/release authorization remain blockers.
- No private historical replay, new experiment, GPU training, tag, release, DOI,
  merge, or main modification was performed.
