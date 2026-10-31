# Contributing

Contributions should preserve scientific identity, explicit information boundaries, reproducibility, and the public/private firewall.

## Before changing a benchmark

Read its research card and typed declaration. Use the scientific display name and canonical slug for paths, modules, tests, and citations. Historical identifiers belong only in provenance metadata. Do not infer unresolved component IDs.

## Evidence and claims

Separate contemporaneous evidence from retrospective characterization. State which targets, inputs, population, intervention support, observation process, dataset realization, model, and evaluation support each result. Keep claims within the declared synthetic system. Record negative results and unresolved limitations.

## Reproducibility and artifacts

Bind generated results to benchmark, realization, model, and evaluation identities. Record checksums and the origin/license state of each artifact. Do not commit large generated data, checkpoints, or external data without an explicit rights and tracking decision.

## License scope

Code is MIT-licensed. Project-authored Markdown is CC BY 4.0. Dataset and model rights are declared per artifact; the repository licenses no historical private source, data, models, or reports.

## Verification and scientific preservation

Use the locked [local CI commands](.github/workflows/README.md#local-parity), [reproduction guide](docs/reproducibility.md) and documentation-link check before proposing a change. Frozen scientific source and result bytes require separately identified correction evidence; never silently rewrite them for terminology cleanup. Keep historical identifiers in necessary provenance records while using descriptive scientific labels in current navigation.

The [probabilistic study summary](docs/studies/probabilistic-capacity-forecasting.md) states public versus restricted evidence. Do not add private fitted heads, test cohorts, predictions, truth or manuscripts. New public files need origin-ledger entries and artifact-specific rights. Reference toy tests do not qualify a private study replay. No external reviewer contact, automatic merge or release follows from passing CI.
