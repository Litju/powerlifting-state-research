"""Typed study identities, separate from benchmark identities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StudyReference:
    slug: str
    purpose: str
    classification: str
    historical_aliases: tuple[str, ...]


STUDIES: tuple[StudyReference, ...] = (
    StudyReference(
        "domain_faithfulness_and_reconstructability",
        "Domain faithfulness and reconstructability; retrospective study.",
        "research study, not benchmark version",
        ("G0 / ALI-540", "pl_study_g0_domain_scientific_audit"),
    ),
    StudyReference(
        "observation_inversion",
        "Observation inversion and latent-state observability; retrospective study.",
        "research study, not benchmark version",
        ("G1 / ALI-541", "pl_study_g1_observation_inversion"),
    ),
    StudyReference(
        "target_sufficient_structural_reconstruction",
        "Target-sufficient structural reconstruction; retrospective study.",
        "research study, not benchmark version",
        ("G2 / ALI-542", "pl_study_g2_structural_reconstruction"),
    ),
    StudyReference(
        "public_surrogate_reconstruction",
        "Public-surrogate reconstruction; retrospective study.",
        "research study, not benchmark version",
        ("G3 / ALI-543", "pl_study_g3_public_surrogate"),
    ),
    StudyReference(
        "synthetic_pretraining_transfer",
        "Synthetic-pretraining transfer; retrospective study.",
        "research study, not benchmark version",
        ("G4 / ALI-544", "pl_study_g4_synthetic_pretraining"),
    ),
    StudyReference(
        "representation_dependence",
        "Representation dependence and information ablations.",
        "future research study",
        (),
    ),
    StudyReference(
        "simple_model_frontier",
        "Simple-model frontier and comparator evaluation.",
        "future research study",
        (),
    ),
    StudyReference(
        "history_cadence_sensitivity",
        "History and observation-cadence sensitivity.",
        "future research study",
        (),
    ),
    StudyReference(
        "residual_learnability",
        "Residual learnability and model attribution.",
        "future research study",
        (),
    ),
    StudyReference(
        "cross_benchmark_synthesis",
        "Synthesis of benchmark validity and negative results.",
        "future research study",
        (),
    ),
    StudyReference(
        "controlled_intervention_comparisons",
        "Controlled intervention comparisons with declared changed/held-fixed axes.",
        "future research study",
        (),
    ),
)
STUDIES_BY_SLUG: dict[str, StudyReference] = {study.slug: study for study in STUDIES}
