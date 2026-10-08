# Training Protocols

`artifacts/training-protocols/public-native-temporal-expert.json` is generated from the typed Python authority in `src/powerlifting_state_research/models/training.py`. Its identity binds the corrected model, PUBLIC_NATIVE benchmark, DatasetSpec and DatasetRealization, M3 prediction contract, split rule, exact seeds, optimizer, scheduler, normalization, selection rule, determinism controls, ensemble rule, and artifact format versions.

The production runner is `python -m powerlifting_state_research.models.train_temporal_expert`. It qualifies generated IID data and trains only on the frozen internal fit subset. `evaluate-seeds` refuses to run before all three checkpoints are sealed; `ensemble` requires the per-seed evaluation artifacts. The notebook `notebooks/public-native-temporal-expert-colab.ipynb` is an execution driver and contains no training loop.

The numeric seeds are reused protocol constants only. The resulting PUBLIC_NATIVE fitted instances are unrelated identities to the historical checkpoints with the same numeric seed values.

## Identity and artifact formats

Each run uses separate, content-bound identities for TRAINING_PROTOCOL, INTERNAL_SELECTION_SPLIT, NORMALIZATION_STATS, FITTED_INSTANCE, CHECKPOINT, TRAINING_HISTORY, TRAINING_RUN, RUN_RECEIPT, and EVALUATION_RESULT. Artifact formats are versioned in the typed protocol manifest. Identity payloads contain scientific IDs and content digests, never mutable machine paths.

Public-native checkpoints are new fits. Historical checkpoint bytes, source files, and adapters remain private. A run receipt records the exact source commit, runtime, CUDA hardware, dependency fingerprint, dataset realization, split identity, normalization hash, and checkpoint seal.
