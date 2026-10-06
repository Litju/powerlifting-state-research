"""Shared scientific component reference namespaces."""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference
from .datasets import dataset_spec_references as dataset_spec_references
from .evaluations import evaluation_references as evaluation_references
from .interventions import intervention_regime_references as intervention_regime_references
from .metrics import metric_references as metric_references
from .observation_models import observation_model_references as observation_model_references
from .populations import population_references as population_references
from .qois import qoi_references as qoi_references
from .representations import representation_references as representation_references
from .shifts import shift_references as shift_references
from .tasks import task_references as task_references
from .worlds import world_references as world_references

COMPONENT_REGISTRIES: dict[ComponentClass, dict[str, ComponentReference]] = {
    ComponentClass.WORLD: world_references,
    ComponentClass.POPULATION: population_references,
    ComponentClass.INTERVENTION_REGIME: intervention_regime_references,
    ComponentClass.OBSERVATION_MODEL: observation_model_references,
    ComponentClass.QOI: qoi_references,
    ComponentClass.TASK: task_references,
    ComponentClass.REPRESENTATION: representation_references,
    ComponentClass.DATASET_SPEC: dataset_spec_references,
    ComponentClass.EVALUATION: evaluation_references,
    ComponentClass.METRIC: metric_references,
    ComponentClass.SHIFT: shift_references,
}

__all__ = [
    "COMPONENT_REGISTRIES",
    "world_references",
    "population_references",
    "intervention_regime_references",
    "observation_model_references",
    "qoi_references",
    "task_references",
    "representation_references",
    "dataset_spec_references",
    "evaluation_references",
    "metric_references",
    "shift_references",
]
