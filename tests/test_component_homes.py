from powerlifting_state_research.components import COMPONENT_REGISTRIES
from powerlifting_state_research.contracts.components import ComponentClass


def test_all_frozen_component_namespaces_are_importable() -> None:
    assert set(COMPONENT_REGISTRIES) == set(ComponentClass)
    assert len(COMPONENT_REGISTRIES[ComponentClass.WORLD]) == 6
    assert COMPONENT_REGISTRIES[ComponentClass.POPULATION] == {}
    assert COMPONENT_REGISTRIES[ComponentClass.INTERVENTION_REGIME] == {}
    assert COMPONENT_REGISTRIES[ComponentClass.METRIC] == {}
    assert COMPONENT_REGISTRIES[ComponentClass.SHIFT] == {}
