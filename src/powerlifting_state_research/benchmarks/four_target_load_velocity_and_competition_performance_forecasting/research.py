"""Research question, information boundary, and claim scope."""

from ...contracts.benchmark import ResearchMetadata

RESEARCH = ResearchMetadata(
    canonical_research_question=(
        "From point-in-time completed histories, how accurately can models forecast four outputs over "
        "25 days: target-load velocity, load at a reference velocity, next-set velocity loss, and "
        "competition-day capacity? This does not establish causal training effects, real-athlete "
        "accuracy, or state/parameter recovery."
    ),
    canonical_scientific_objective="Characterize four powerlifting performance targets in a longitudinal synthetic system.",
    research_question_evidence_class="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
    information_setting="HISTORY_ONLY",
    source_prediction_setting=(
        "Point-in-time histories; temporal features end at the current completed event. No "
        "future-plan field in the recovered interface."
    ),
    historical_objective="UNKNOWN",
    historical_objective_evidence="UNKNOWN_ORIGINAL_MOTIVATION",
    canonical_claim_scope=(
        "Reconstructed synthetic four-output specimen with source-bound checkpoint/public scalar.",
        "Four target meanings and the historical weighted evaluation identity are recoverable.",
    ),
    claim_escalations_prohibited=(
        "Qualification/performance claim from checkpoint/scalar alone.",
        "Real-athlete, biological, causal, parameter-identification, or OOD claims.",
    ),
    unresolved_questions=(
        "What was the original motivation for the four-target output set?",
        "Was this historical specimen independently qualified?",
        "What metric produced scalar 0.16719849?",
    ),
)
