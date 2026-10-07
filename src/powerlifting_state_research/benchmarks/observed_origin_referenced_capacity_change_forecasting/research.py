"""Research question, information boundary, and claim scope."""

from ...contracts.benchmark import ResearchMetadata

RESEARCH = ResearchMetadata(
    canonical_research_question=(
        "At the forecast origin, can a model using noisy performance observations through that origin "
        "and the participant-visible declared dose/intensity plan predict future modeled capacity "
        "relative to the noisy observed-origin assessment for squat, bench, and deadlift at horizons "
        "14, 28, and 56 days? This is not a difference between two observed performance assessments, "
        "a causal effect, or the same estimand as latent-origin capacity change."
    ),
    canonical_scientific_objective=(
        "Forecast future capacity relative to a noisy observed-origin assessment under a declared "
        "future plan in a synthetic dose-history world."
    ),
    research_question_evidence_class="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
    information_setting="DECLARED_FUTURE_PLAN_VISIBLE",
    source_prediction_setting=(
        "Origin 224; use observations through origin and complete declared future dose/intensity "
        "plan. Future realized outcomes are unavailable."
    ),
    historical_objective="UNKNOWN",
    historical_objective_evidence="UNKNOWN_ORIGINAL_MOTIVATION",
    canonical_claim_scope=(
        "The target is future modeled capacity relative to a noisy observed-origin assessment, "
        "not observed-to-observed performance change.",
        "dose-history interface exposes future dose/intensity plan and measurements through origin.",
    ),
    claim_escalations_prohibited=(
        "Pure latent-capacity-change, causal effect, responder classification, real-athlete validity, "
        "biological parameter ID.",
        "Do not rank raw scores across the observed-origin target, latent-origin target, or different "
        "dynamical systems.",
    ),
    unresolved_questions=(
        "Was the schedule/exposure formulation the direct dose-history parent and observed-origin "
        "authorized target?",
        "What was authoritative observed-origin scorer/truth and final result?",
        "Can import/runtime provenance be made exact?",
    ),
)
