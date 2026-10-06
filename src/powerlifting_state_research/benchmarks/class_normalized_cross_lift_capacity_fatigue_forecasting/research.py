"""Research question, information boundary, and claim scope."""

from ...contracts.benchmark import ResearchMetadata

RESEARCH = ResearchMetadata(
    canonical_research_question=(
        "Within a class-normalized synthetic cross-lift capacity-fatigue world, how well can a model "
        "forecast five performance outputs from past or completed records? The result is conditional "
        "on the synthetic generator and does not establish real-athlete validity or latent-state "
        "recovery."
    ),
    canonical_scientific_objective=(
        "Characterize the same five target meanings in a class-normalized cross-lift synthetic world "
        "with changed observation and population generation."
    ),
    research_question_evidence_class="RETROSPECTIVE_TECHNICAL_CHARACTERIZATION",
    information_setting="HISTORY_ONLY",
    source_prediction_setting="Past/completed context at each query; future outcomes excluded; no declared future-plan input.",
    historical_objective="UNKNOWN",
    historical_objective_evidence="UNKNOWN_ORIGINAL_MOTIVATION",
    canonical_claim_scope=(
        "Five source-defined synthetic outputs can be evaluated after scorer is fixed.",
        "Common canonical comparison with other normalized legacy specimens.",
    ),
    claim_escalations_prohibited=(
        "Human/biological/coaching/digital-twin/intervention/identification/OOD claims.",
        "Raw historical ranking or undocumented claim the rewrite fixed a known defect.",
    ),
    unresolved_questions=(
        "What problem triggered the July rewrite and what effect was expected?",
        "What scorer aggregation/seed governs canonical replay?",
        "Was qualification performed?",
    ),
)
