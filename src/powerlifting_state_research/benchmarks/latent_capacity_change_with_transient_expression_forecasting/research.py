"""Research question, information boundary, and claim scope."""

from ...contracts.benchmark import ResearchMetadata

RESEARCH = ResearchMetadata(
    canonical_research_question=(
        "At day 224, given 32 weekly performance observations per lift through day 223, the declared "
        "future plan, and task-allowed context, can a model predict latent capacity change for three "
        "lifts at horizons 14, 28, and 56 days in a synthetic system that separates latent capacity "
        "from transient performance expression? This is conditional "
        "synthetic prediction, not human response, biological identification, intervention efficacy, "
        "or broad out-of-domain generalization."
    ),
    canonical_scientific_objective=(
        "Evaluate latent capacity-change forecasting in a synthetic system separating "
        "chronic adaptation, latent capacity, transient expression, and recorded observations."
    ),
    research_question_evidence_class="CONTEMPORANEOUS_RESEARCH_QUESTION",
    information_setting="DECLARED_FUTURE_PLAN_VISIBLE",
    source_prediction_setting=(
        "Cutoff day 224; 32 weekly observations/lift through day223 plus declared plan/context "
        "visible; latent coordinates, targets, future realized outcomes/observations hidden."
    ),
    historical_objective=(
        "Replace under-supported target-bearing training-exposure formulations with a simpler empirically "
        "bounded synthetic world that preserves latent capacity-change target meaning and "
        "origin/horizons."
    ),
    historical_objective_evidence="CONTEMPORANEOUS_OBJECTIVE",
    canonical_claim_scope=(
        "Qualified conditional synthetic prediction within the named latent-capacity and "
        "transient-expression system, support, and evaluation, subject to a missing readiness receipt.",
        "Later audit studies support only their named findings and tested protocols.",
    ),
    claim_escalations_prohibited=(
        "Real athlete/biological/coaching/digital twin, causal intervention effect, broad OOD.",
        "Biological parameter/full-coordinate identification.",
        "Bayes ceiling, exact hidden-model recovery, replayed sealed result, unsupported G4 "
        "load-bearing claim.",
        "Treating audits/model branches as benchmarks.",
    ),
    unresolved_questions=(
        "Where is the expected model readiness receipt?",
        "Do observation/data support geometry warrant future change after controlled evaluation?",
        "Can claims beyond synthetic support be separately validated?",
    ),
)
