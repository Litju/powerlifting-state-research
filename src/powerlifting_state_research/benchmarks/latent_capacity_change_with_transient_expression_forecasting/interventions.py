"""Balanced history schedules and declared future training plans."""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import product

from .dynamics import TrainingSession
from .population import LIFTS

ORIGIN_DAY = 224
MAX_HORIZON_DAYS = 56
HISTORY_DAYS = ORIGIN_DAY
PLAN_START_DAY = ORIGIN_DAY
PLAN_END_DAY = ORIGIN_DAY + MAX_HORIZON_DAYS - 1
INTENSITY_FRACTION = 0.75

DOSE_INTENSITY_PAIRS = {
    "cessation": (0.0, INTENSITY_FRACTION),
    "step_down": (0.4, INTENSITY_FRACTION),
    "continue": (0.8, INTENSITY_FRACTION),
    "step_up": (1.2, INTENSITY_FRACTION),
}
PLAN_IDS = ("continue", "step_up", "step_down", "cessation")
HORIZONS_DAYS = (14, 28, 56)
STRATA = tuple((plan_id, horizon) for plan_id in PLAN_IDS for horizon in HORIZONS_DAYS)

# Each tuple gives consecutive week-block lengths and the public dose-pair key.
HISTORY_TEMPLATES: tuple[tuple[tuple[int, str], ...], ...] = (
    (
        (4, "step_down"),
        (4, "continue"),
        (4, "step_up"),
        (1, "cessation"),
        (4, "step_down"),
        (4, "continue"),
        (4, "step_up"),
        (1, "cessation"),
        (4, "continue"),
        (2, "step_down"),
    ),
    (
        (4, "step_up"),
        (4, "continue"),
        (4, "step_down"),
        (1, "cessation"),
        (4, "step_up"),
        (4, "step_down"),
        (4, "continue"),
        (1, "cessation"),
        (2, "step_up"),
        (2, "continue"),
        (2, "step_down"),
    ),
    (
        (8, "continue"),
        (4, "step_up"),
        (2, "cessation"),
        (4, "step_down"),
        (4, "step_up"),
        (2, "cessation"),
        (4, "continue"),
        (4, "step_down"),
    ),
    (
        (8, "step_down"),
        (2, "cessation"),
        (8, "step_up"),
        (4, "continue"),
        (2, "cessation"),
        (4, "step_up"),
        (4, "step_down"),
    ),
)


@dataclass(frozen=True, slots=True)
class HistorySegment:
    start_day: int
    end_day: int
    dose: float
    intensity: float


@dataclass(frozen=True, slots=True)
class DeclaredFuturePlan:
    plan_id: str
    start_day: int
    end_day: int
    dose: float
    intensity: float


def sample_history_template_combinations(
    rng: random.Random, count: int
) -> list[tuple[int, int, int]]:
    """Balance all 64 per-lift template combinations before shuffling."""
    if count < 1:
        raise ValueError("history assignment count must be positive")
    combinations = [
        (squat, bench, deadlift)
        for squat, bench, deadlift in product(range(len(HISTORY_TEMPLATES)), repeat=len(LIFTS))
    ]
    assignments = combinations * (count // len(combinations))
    if count % len(combinations):
        assignments.extend(rng.sample(combinations, count % len(combinations)))
    rng.shuffle(assignments)
    return assignments


def history_segments(template_index: int) -> tuple[HistorySegment, ...]:
    if not 0 <= template_index < len(HISTORY_TEMPLATES):
        raise ValueError("unknown public history schedule")
    day = 0
    segments: list[HistorySegment] = []
    for weeks, pair_id in HISTORY_TEMPLATES[template_index]:
        dose, intensity = DOSE_INTENSITY_PAIRS[pair_id]
        end_day = day + 7 * weeks - 1
        segments.append(HistorySegment(day, end_day, dose, intensity))
        day = end_day + 1
    if day != HISTORY_DAYS:
        raise ValueError("history schedule must end on day 223")
    return tuple(segments)


def declared_plan(plan_id: str) -> DeclaredFuturePlan:
    if plan_id not in DOSE_INTENSITY_PAIRS:
        raise ValueError(f"unknown declared future plan: {plan_id}")
    dose, intensity = DOSE_INTENSITY_PAIRS[plan_id]
    return DeclaredFuturePlan(plan_id, PLAN_START_DAY, PLAN_END_DAY, dose, intensity)


def training_sessions(template_index: int, plan: DeclaredFuturePlan) -> dict[int, TrainingSession]:
    """Expand one lift's past schedule and the declared plan into daily inputs."""
    if plan.start_day != PLAN_START_DAY or plan.end_day != PLAN_END_DAY:
        raise ValueError("declared plan must cover days 224 through 279")
    sessions: dict[int, TrainingSession] = {}
    for segment in history_segments(template_index):
        for day in range(segment.start_day, segment.end_day + 1):
            sessions[day] = TrainingSession(day, segment.dose, segment.intensity)
    for day in range(plan.start_day, plan.end_day + 1):
        sessions[day] = TrainingSession(day, plan.dose, plan.intensity)
    return sessions
