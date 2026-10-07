"""Research question, information boundary, and claim scope."""

from ...contracts.benchmark import ResearchMetadata

RESEARCH = ResearchMetadata(
    canonical_research_question=(
        "From completed records at each query time, how well can a model forecast five source-defined "
        "powerlifting performance outputs in an early synthetic seasonal system: target-load bar "
        "velocity, load at a reference velocity, session shift, next-set velocity loss, and "
        "competition-day capacity? This describes the synthetic task and does not establish "
        "real-athlete validity or latent-state identification."
    ),
    canonical_scientific_objective=(
        "Characterize forecasts for five source-defined outputs, including load-velocity observations, "
        "within-session velocity loss, and competition-day capacity."
    ),
    research_question_evidence_class="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
    information_setting="HISTORY_ONLY",
    source_prediction_setting=(
        "Use past/completed records available at each query time; future meet outcomes and "
        "future/in-session records are excluded. No declared future-plan input."
    ),
    historical_objective="UNKNOWN",
    historical_objective_evidence="UNKNOWN_ORIGINAL_MOTIVATION",
    canonical_claim_scope=(
        "Source-bound historical specimen and five synthetic target definitions.",
        "Common canonical reevaluation after target/support alignment.",
    ),
    claim_escalations_prohibited=(
        "Human/biological/coaching/digital-twin/intervention/identification/OOD claims.",
        "Raw score ranking or claims that early equals later legacy worlds.",
    ),
    unresolved_questions=(
        "What objective motivated the first task?",
        "What were the exact RNG seed and final scorer aggregation?",
        "Was benchmark qualification performed?",
    ),
)
