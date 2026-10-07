"""Research metadata for the independently authored IID public-native benchmark."""

from ...contracts.benchmark import ResearchMetadata

RESEARCH = ResearchMetadata(
    canonical_research_question=(
        "Why provide an independently implemented public benchmark for conditional synthetic "
        "latent-capacity-change forecasting, and can a learner predict squat, bench-press, and "
        "deadlift capacity change from the declared plan and pre-origin observations?"
    ),
    canonical_scientific_objective=(
        "Independently implement the stated synthetic world and evaluate conditional forecasts "
        "under an explicit IID population measure, without claiming to reproduce historical "
        "scrambled-Sobol dataset bytes."
    ),
    research_question_evidence_class="INDEPENDENT_PUBLIC_NATIVE_OBJECTIVE",
    information_setting="DECLARED_FUTURE_PLAN_VISIBLE",
    source_prediction_setting=(
        "At origin day 224, expose history through day 223 and the declared future plan; hide "
        "future realized outcomes, observations, intervention deviations, latent coordinates, "
        "and target fields from participants."
    ),
    historical_objective=None,
    historical_objective_evidence=None,
    canonical_claim_scope=(
        "Conditional prediction of synthetic latent-capacity changes within this named world, "
        "population, schedule, observation law, and same-law validation design.",
    ),
    claim_escalations_prohibited=(
        "Real-athlete validation, coaching response, or biological parameter identification.",
        "Causal intervention efficacy or broad out-of-distribution evidence.",
    ),
    unresolved_questions=(),
    dataset_spec_difference=(
        "The historical projection specifies scrambled Sobol sampling; this PUBLIC_NATIVE "
        "DatasetSpec specifies IID pseudorandom Uniform[0,1) coordinates. They are distinct "
        "DatasetSpecs, and historical train/validation bytes are not realizations of this one."
    ),
    limitations=(
        "Synthetic benchmark with three lifts, finite schedule and plan support, and a fixed "
        "observation law.",
        "IID finite-sample geometry and same-law validation do not establish real-athlete "
        "external validity or broad OOD performance.",
        "Targets describe synthetic latent capacity change and do not estimate causal effects.",
    ),
    related_benchmark_relationship=(
        "Shares specified world mechanics, task, QOI, representation, and evaluation with the "
        "separate historical projection. Population sampling, DatasetSpec, BenchmarkSpec, and "
        "realization identity remain public-native and distinct."
    ),
)
