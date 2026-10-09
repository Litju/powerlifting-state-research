# Reference Implementations

## Scope

Lightweight public research comparators.

## Model artifact rules

The RES-275 public-native IID suite includes a plan/horizon context mean, Ridge, NumPy gradient-boosted regression stumps, a fixed-midpoint mechanistic forecast, a compact neural model, and a mechanistic-plus-Ridge-residual hybrid. The frozen protocol and model IDs are in `artifacts/training-protocols/public-native-comparator-suite.json` and `artifacts/registries/public-native-comparator-registry.json`.

The suite uses only the locked NumPy and PyTorch dependencies. It trains on the frozen IID TRAIN split, uses the RES-274 hash-ranked internal selection split only for declared tree/neural stopping, and evaluates with the RES-271 evaluator. The RES-274 temporal expert is an immutable pre-existing comparator; its predictions and EvaluationResults are referenced in place.

The initial repository contains no historical checkpoint or private model bytes. Every future model artifact needs a model card and explicit rights/provenance metadata.
