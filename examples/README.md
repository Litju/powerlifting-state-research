# Examples

Examples belong here when they demonstrate a public package workflow using generated, rights-cleared data. Each example should pin the benchmark and realization identities it uses and should state the visible input boundary.

At bootstrap the registry is importable, but no benchmark has public mechanics or a generated realization. The smallest current smoke example is:

    from powerlifting_state_research.registry import BENCHMARKS

    for benchmark in BENCHMARKS:
        print(benchmark.slug, benchmark.public_implementation_status.value)

This enumerates research declarations; it does not run a forecast.
