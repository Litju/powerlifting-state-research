# Registries

## Scope

Generated registry exports; typed Python is authoritative.

## Publication rule

The benchmark registry JSON is generated from the explicit typed package registry. Edit Python declarations, then regenerate the export.

`public-native-comparator-registry.json` records the frozen RES-275 new-comparator model IDs, fitted instances, prediction artifacts, EvaluationResults, and the separately identified immutable RES-274 expert reference.

`validity-axis-registry.json`, `attack-contract-registry.json`, and `version-validity-profiles.json` are generated from the typed RES-277 audit contracts. The profiles record evidence states, not executed results. Their `NOT_RUN`, `NOT_APPLICABLE`, and `UNSUPPORTED_BY_EVIDENCE` distinctions must be preserved by future audit tooling.

No historical private material is included. Unknown rights or untraceable inputs block publication of an artifact.
