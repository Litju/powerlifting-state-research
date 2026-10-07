"""Research question, information boundary, and claim scope."""

from ...contracts.benchmark import ResearchMetadata

RESEARCH = ResearchMetadata(
    canonical_research_question=(
        "At the forecast origin, using noisy pre-origin observations and the participant-visible "
        "declared dose/intensity plan, how accurately can a model forecast latent capacity change for "
        "three lifts at horizons 14, 28, and 56 days while keeping measurement noise in the inputs "
        "and out of target truth? This is conditional synthetic prediction, not a causal effect, "
        "latent-coordinate recovery, or human validity."
    ),
    canonical_scientific_objective=(
        "Forecast latent capacity change while retaining noisy origin assessment as an input rather "
        "than target truth."
    ),
    research_question_evidence_class="CONTEMPORANEOUS_RESEARCH_QUESTION",
    information_setting="DECLARED_FUTURE_PLAN_VISIBLE",
    source_prediction_setting=(
        "Origin 224; dose-history observations through origin and complete declared future "
        "dose/intensity plan; future realized outcomes unavailable."
    ),
    historical_objective=(
        "Replace the observed-origin-referenced capacity target with latent-origin capacity, removing "
        "origin measurement error from target while retaining noisy measurement as input."
    ),
    historical_objective_evidence="CONTEMPORANEOUS_OBJECTIVE",
    canonical_claim_scope=(
        "Target migration isolates latent capacity-change QOI on same 2,048 dose-history inputs.",
        "Public diagnostics support claims only about this task/folds.",
    ),
    claim_escalations_prohibited=(
        "Individual causal treatment effect or responder classification.",
        "Human validity, biological parameter ID, broad OOD, hidden/final qualification.",
        "Raw score ranking against the observed-origin-referenced capacity target or latent capacity change with "
        "transient performance expression.",
    ),
    unresolved_questions=(
        "No fresh latent-origin hidden challenge/final qualification.",
        "Can dose-history import/runtime be reconstructed exactly?",
        "Can dose-history mechanisms/public attacks be assessed under complete protocol?",
    ),
)
