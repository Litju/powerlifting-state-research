"""Research question, information boundary, and claim scope."""

from ...contracts.benchmark import ResearchMetadata

RESEARCH = ResearchMetadata(
    canonical_research_question=(
        "Within a synthetic system with heterogeneous training schedules, realized exposure, and "
        "reporting, can models forecast target-load velocity, load at a reference velocity, next-set "
        "velocity loss, and competition-day capacity over 25 days from completed histories? The "
        "available evidence does not establish that added heterogeneity improves prediction."
    ),
    canonical_scientific_objective=(
        "Characterize the same four targets when training schedule, realized exposure, and reporting "
        "vary in a synthetic system."
    ),
    research_question_evidence_class="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
    information_setting="HISTORY_ONLY",
    source_prediction_setting=(
        "Point-in-time completed histories for 25-day forecast; no declared future-plan input in "
        "the recovered interface."
    ),
    historical_objective=(
        "Add variation in training schedules, realized exposure, and reporting while retaining the "
        "four-target 25-day task; the triggering need or expected gain is UNKNOWN."
    ),
    historical_objective_evidence="CONTEMPORANEOUS_OBJECTIVE",
    canonical_claim_scope=(
        "The system varies training schedules, realized exposure, and reporting across athletes.",
        "It has a separate dataset identity and shares the four-target, 25-day task definition.",
    ),
    claim_escalations_prohibited=(
        "Qualification or performance cannot be inferred from a checkpoint trained for another "
        "scientific system.",
        "Human, biological, intervention-effect, parameter-ID, or OOD claims.",
        "Do not claim unresolved intermediate variants or treat a branch/version discrepancy as "
        "settled.",
    ),
    unresolved_questions=(
        "What need motivated the added schedule, exposure, and reporting variation?",
        "Were unresolved intermediate datasets or component variants materialized?",
        "Was this historical specimen independently evaluated or qualified?",
    ),
)
