"""Research question, information boundary, and claim scope."""

from ...contracts.benchmark import ResearchMetadata

RESEARCH = ResearchMetadata(
    canonical_research_question=(
        "Within a synthetic world with heterogeneous training schedules, exposure, and reporting, can "
        "models forecast target-load velocity, reference-velocity load, next-set velocity loss, and "
        "competition-day capacity over 25 days from completed histories? The available evidence does "
        "not establish that added heterogeneity improves prediction."
    ),
    canonical_scientific_objective=(
        "Characterize the same four targets when training schedule, exposure, and reporting vary in a "
        "synthetic world."
    ),
    research_question_evidence_class="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
    information_setting="HISTORY_ONLY",
    source_prediction_setting=(
        "Point-in-time completed histories for 25-day forecast; no declared future-plan input in "
        "recovered interface."
    ),
    historical_objective=(
        "Add schedule/exposure and reporting heterogeneity over stable-slope/tilt formulation core "
        "while retaining the four-target 25-day contract; triggering need or expected gain is "
        "UNKNOWN."
    ),
    historical_objective_evidence="CONTEMPORANEOUS_OBJECTIVE",
    canonical_claim_scope=(
        "the schedule/exposure formulation adds schedule/exposure and reporting heterogeneity over "
        "stable-slope/tilt state core.",
        "schedule/exposure formulation has separate data identity and shared four-target task "
        "contract.",
    ),
    claim_escalations_prohibited=(
        "schedule/exposure formulation qualification/performance inferred from stable-slope/tilt "
        "formulation checkpoint.",
        "Human, biological, intervention-effect, parameter-ID, or OOD claims.",
        "Do not claim unresolved intermediate variants or treat a branch/version discrepancy as "
        "settled.",
    ),
    unresolved_questions=(
        "What need motivated schedule/exposure heterogeneity?",
        "Which dose-history/v4 label was intended; were unresolved intermediate variants "
        "materialized?",
        "Was schedule/exposure formulation independently evaluated or qualified?",
    ),
)
