# Reproducibility scripts

`export_benchmark_registry.py` regenerates the machine-readable benchmark registry and both schema exports from the Python authority. The schemas describe structure only; semantic and cross-field rules remain in the Python contract validator. Run `python -m powerlifting_state_research.exports --check` to detect drift in the checked-in registry and package schemas.

This directory intentionally has no general command-line framework. Build, test, type-check, and lint commands are provided by the development toolchain in pyproject.toml.
