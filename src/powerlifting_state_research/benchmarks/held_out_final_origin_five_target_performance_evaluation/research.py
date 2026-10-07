"""Research question, information boundary, and claim scope."""

from ...contracts.benchmark import ResearchMetadata

RESEARCH = ResearchMetadata(
    canonical_research_question=(
        "Using the refined class-normalized synthetic cross-lift system, can predictors trained on "
        "four earlier 25-day origins predict the same five outputs for an independent final-origin "
        "draw at days 340–365? This evaluates transfer within synthetic support, not human or "
        "general-domain transfer."
    ),
    canonical_scientific_objective=(
        "Evaluate five performance targets on an independent held-out final origin within the "
        "class-normalized synthetic system."
    ),
    research_question_evidence_class="CONTEMPORANEOUS_RESEARCH_QUESTION",
    information_setting="HISTORY_ONLY",
    source_prediction_setting=(
        "Past/completed observations only. Training origins 200/260/315/340; validation/hidden at "
        "340→365; no declared future-plan input."
    ),
    historical_objective="Add public validation from the final held-out target domain using independent split streams.",
    historical_objective_evidence="CONTEMPORANEOUS_OBJECTIVE",
    canonical_claim_scope=(
        "Held-out public final-origin validation exists within refined synthetic world.",
        "Five shared legacy target meanings can support matched canonical reevaluation.",
    ),
    claim_escalations_prohibited=(
        "Human transfer, broad OOD generalization, causal effects.",
        "Prediction improvement, qualification, or raw-score superiority inferred from split design.",
    ),
    unresolved_questions=(
        "Did final-origin validation improve selection or prediction?",
        "Can legacy scorer/seed be recovered for normalized reevaluation?",
        "Was benchmark qualification performed?",
    ),
)
