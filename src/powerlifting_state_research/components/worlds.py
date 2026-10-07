"""Six named world references shared across the historical specimens."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution


@dataclass(frozen=True, slots=True)
class WorldDeclaration:
    slug: str
    display_name: str
    component_identity_id: str
    historical_aliases: tuple[str, ...]
    scientific_summary: str

    @property
    def reference(self) -> ComponentReference:
        return ComponentReference(
            ComponentClass.WORLD,
            self.slug,
            ComponentResolution.DIRECT_HISTORICAL_IDENTITY,
        )


WORLD_DECLARATIONS: tuple[WorldDeclaration, ...] = (
    WorldDeclaration(
        "athlete_latent_state_dynamics",
        "Athlete Latent-State Dynamics",
        "psr:world:refined-class-normalized-seasonal-cross-lift-world@1.0.0~c7dcec83d1f8",
        (
            "class_normalized_cross_lift_performance",
            "Class-Normalized Cross-Lift Performance World",
            "class_normalized_cross_lift_capacity_fatigue",
            "WORLD_LEGACY_REFINED_CROSS_LIFT.v2",
        ),
        "The historical specimen's specific latent-state transition law is not characterized.",
    ),
    WorldDeclaration(
        "longitudinal_athlete_state_dynamics",
        "Longitudinal Athlete-State Dynamics",
        "psr:world:c21-athlete-state-stable-slope-tilt-world@1.0.0~8956f2327a14",
        (
            "four_target_longitudinal_performance_state",
            "Four-Target Longitudinal Performance-State World",
            "stable_slope_tilt_athlete_state",
            "C21",
            "C21.2",
            "C21-athlete-state-stable-slope-tilt-seed3115",
            "WORLD_C21_ATHLETE_STATE_STABLE_SLOPE_TILT.v1",
        ),
        "Longitudinal synthetic athlete-state trajectories; the specific transition law is not "
        "characterized.",
    ),
    WorldDeclaration(
        "athlete_state_transition_dynamics",
        "Athlete-State Transition Dynamics",
        "psr:world:c22-heterogeneous-schedule-exposure-world@1.0.0~55a292e3b1c6",
        (
            "heterogeneous_training_schedule_exposure_and_reporting",
            "Heterogeneous Training Schedule, Exposure, and Reporting World",
            "schedule_exposure_heterogeneity",
            "C22",
            "C22.4",
            "C22-schedule-exposure-v4",
            "WORLD_C22_HETEROGENEOUS_SCHEDULE_EXPOSURE.v1",
        ),
        "The historical specimen's specific athlete-state transition law is not characterized.",
    ),
    WorldDeclaration(
        "latent_capacity_transient_performance_expression_dynamics",
        "Latent Capacity and Transient Performance-Expression Dynamics",
        "psr:world:world-v2-parsimonious-response-world@1.0.0~a1afbf2f5c1e",
        (
            "parsimonious_capacity_expression",
            "World-V2",
            "WORLD_RESPONSE_PARSIMONIOUS.v2",
            "powerlifting.big3.response.parsimonious.v2",
        ),
        "Separates chronic adaptation, latent capacity, and transient performance expression.",
    ),
    WorldDeclaration(
        "latent_state_transition_dynamics",
        "Latent-State Transition Dynamics",
        "psr:world:early-seasonal-capacity-load-velocity-world@1.0.0~168dadf66c15",
        (
            "seasonal_load_velocity_and_performance",
            "Seasonal Load–Velocity and Performance World",
            "seasonal_capacity_fatigue",
            "WORLD_LEGACY_EARLY_CAPACITY_FATIGUE.v1",
            "initial Powerlifting task",
        ),
        "The historical specimen's specific latent-state transition law is not characterized.",
    ),
    WorldDeclaration(
        "training_dose_history_capacity_dynamics",
        "Training Dose-History Capacity Dynamics World",
        "psr:world:v1-dose-memory-response-world@1.0.0~11b6f0033502",
        (
            "dose_history_capacity_dynamics",
            "World-V1",
            "WORLD_RESPONSE_DOSE_MEMORY.v1",
            "powerlifting.big3.response.dose_memory.v1",
        ),
        "Synthetic capacity dynamics depend on training-dose history.",
    ),
)

world_references: dict[str, ComponentReference] = {
    world.slug: world.reference for world in WORLD_DECLARATIONS
}
