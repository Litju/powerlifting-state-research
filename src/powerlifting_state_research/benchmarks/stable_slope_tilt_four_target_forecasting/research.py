"""Research question, information boundary, and claim scope."""

from ...contracts.benchmark import ResearchMetadata

RESEARCH = ResearchMetadata(
    canonical_research_question=(
        "Within a stable-slope/tilt synthetic athlete-state world, how accurately can models forecast "
        "target-load velocity, reference-velocity load, next-set velocity loss, and competition-day "
        "capacity from point-in-time histories at four origins, including day 340–365? This does not "
        "establish causal training effects, real-athlete accuracy, or state/parameter recovery."
    ),
    canonical_scientific_objective="Characterize four performance targets under a stable-slope/tilt synthetic athlete-state model.",
    research_question_evidence_class="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
    information_setting="HISTORY_ONLY",
    source_prediction_setting=(
        "Point-in-time histories; temporal features end at the current completed event. No "
        "future-plan field in recovered public interface."
    ),
    historical_objective="UNKNOWN",
    historical_objective_evidence="UNKNOWN_ORIGINAL_MOTIVATION",
    canonical_claim_scope=(
        "Reconstructed synthetic four-output specimen with source-bound checkpoint/public scalar.",
        "Four target meanings and weighted contract are recoverable.",
    ),
    claim_escalations_prohibited=(
        "Qualification/performance claim from checkpoint/scalar alone.",
        "Real-athlete, biological, causal, parameter-identification, or OOD claims.",
    ),
    unresolved_questions=(
        "What motivated stable-slope/tilt formulation.2 and dropping P3?",
        "Was stable-slope/tilt formulation independently qualified?",
        "What metric produced scalar 0.16719849?",
    ),
)
