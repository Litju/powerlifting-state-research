# Data topology

The data tree separates dataset specifications, immutable realization manifests, newly generated public synthetic realizations, and external or empirical data manifests. A realization is identified independently of the benchmark semantics. The [PUBLIC_NATIVE IID latent-capacity dataset card](../../artifacts/dataset-cards/iid-latent-capacity-change-with-transient-expression-forecasting.md) is its authoritative row and regeneration contract.

No historical dataset bytes are included in the bootstrap. New synthetic data can be published only with generator/configuration identity, seeds or replicates, schema, splits, coverage, checksums, origin class, and CC BY 4.0 rights in its realization manifest. External data needs explicit source rights, consent where applicable, access terms, and a redistribution decision. Rights are never inferred from availability.
