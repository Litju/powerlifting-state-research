from pathlib import Path

from powerlifting_state_research.contracts.serialization import canonical_json_bytes
from powerlifting_state_research.models.training import (
    COMPARATOR_TRAINING_PROTOCOL_ID,
    PUBLIC_NATIVE_COMPARATOR_PROTOCOL,
    comparator_training_protocol_manifest,
)


def test_comparator_protocol_manifest_is_generated_from_frozen_authority() -> None:
    root = Path(__file__).resolve().parents[2]
    artifact = root / "artifacts/training-protocols/public-native-comparator-suite.json"

    assert (
        artifact.read_bytes()
        == canonical_json_bytes(comparator_training_protocol_manifest()) + b"\n"
    )
    assert COMPARATOR_TRAINING_PROTOCOL_ID.startswith(
        "psr:training-protocol:public-native-comparator-suite@1.0.0~"
    )
    assert PUBLIC_NATIVE_COMPARATOR_PROTOCOL.benchmark_id.endswith("~f99463d55ba0")
    assert PUBLIC_NATIVE_COMPARATOR_PROTOCOL.evaluation_id.endswith("~cd4fe982e7b8")
    assert PUBLIC_NATIVE_COMPARATOR_PROTOCOL.train_sha256 == (
        "914dc51fcf9a0dca30224a8093431e97fe29272bf830160bf46a78396026d550"
    )
    assert PUBLIC_NATIVE_COMPARATOR_PROTOCOL.validation_sha256 == (
        "0d7bd0c9291e7af5627ec18e2b82025aa1f5f3d46de07d502f7df90eace24b9a"
    )
    assert PUBLIC_NATIVE_COMPARATOR_PROTOCOL.seeds == (383001, 383002, 383003)
    assert dict(PUBLIC_NATIVE_COMPARATOR_PROTOCOL.feature_representation)["feature_count"] == 127
