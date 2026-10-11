"""Independent checks of the scientific claims and observation information firewall."""

import csv
import hashlib
import io
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting.observations import (  # noqa: E501
    VELOCITY_CONSTANTS,
    PerformanceObservation,
)
from powerlifting_state_research.benchmarks.latent_capacity_change_with_transient_expression_forecasting.population import (  # noqa: E501
    LIFTS,
    parameters_from_coordinates,
)
from powerlifting_state_research.contracts.serialization import sha256_record
from powerlifting_state_research.studies import observation_inversion as study
from powerlifting_state_research.studies.observation_inversion_protocol import (
    PROTOCOL,
    PROTOCOL_DIGEST,
    STUDY_ID,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("lift", LIFTS)
def test_noiseless_inverse_and_derivative(lift: str) -> None:
    e, b, _ = VELOCITY_CONSTANTS[lift]
    p, load = 200.0, 140.0
    v = e + b * (1 - load / p) / 0.6
    observation = PerformanceObservation(223, p, load, v)
    for channel in ("assessment", "velocity", "combined"):
        assert study.reconstruct((observation,), lift, channel, "last", 0) == pytest.approx(p)
    # Independently differentiate the closed-form inverse at fixed measured load.
    step = 1e-6
    plus = study.reconstruct(
        (replace(observation, velocity_mps=v + step),), lift, "velocity", "last", 1
    )
    minus = study.reconstruct(
        (replace(observation, velocity_mps=v - step),), lift, "velocity", "last", 1
    )
    assert plus is not None and minus is not None
    assert (plus - minus) / (2 * step) == pytest.approx(0.6 * load / (b * 0.7**2), rel=1e-8)


def test_invalid_and_future_inputs_are_not_silently_used() -> None:
    observation = PerformanceObservation(223, 200, 140, 2)
    assert study.reconstruct((observation,), "squat", "velocity", "last", 1) is None
    assert study.reconstruct((observation,), "squat", "combined", "last", 1) is None
    with pytest.raises(ValueError, match="boundary"):
        study.reconstruct((replace(observation, day=224),), "squat", "assessment", "last", 1)
    with pytest.raises(ValueError):
        study.reconstruct(
            (replace(observation, velocity_mps=math.nan),), "squat", "assessment", "last", 1
        )


def test_transition_derivatives_and_counterexamples() -> None:
    world = parameters_from_coordinates([0.5] * 16)
    p = world.lifts["squat"]
    for gap in (1, 7, 28):
        np.testing.assert_allclose(
            study.rest_jacobian(p, (0.3, 0.3), (0, gap)),
            study.numerical_rest_jacobian(p, (0.3, 0.3), (0, gap)),
            atol=1e-6,
            rtol=1e-8,
        )
    result = study.diagnostics()
    single = result["instantaneous"]
    assert single["C1_kg"] != single["C2_kg"]
    assert result["constant_input_equivalence"]["max_P_difference_kg"] < 1e-10
    assert abs(result["constant_input_equivalence"]["A223_difference"]) > 0.1
    for template in range(4):
        np.testing.assert_allclose(
            study.sensitivity(template, 1e-5),
            study.sensitivity(template, 5e-6),
            rtol=1e-4,
            atol=1e-5,
        )


def test_noise_matching_truth_and_seed_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs, truth = study.generate_data()
    assert len(inputs) == 96 and len(truth) == 96
    assert all(set(row) == {"entity", "lift", "template", "observations"} for row in inputs)
    row, target = inputs[0], truth[0]
    base = PerformanceObservation(**row["observations"][-1])
    expressed = target["P223_kg"]
    assert study.scaled_observation(base, expressed, 1, "squat") == base
    zero = study.scaled_observation(base, expressed, 0, "squat")
    assert zero.assessment_kg == expressed
    assert zero.prescribed_load_kg / zero.assessment_kg == pytest.approx(
        base.prescribed_load_kg / base.assessment_kg
    )
    monkeypatch.setattr(study, "PROTOCOL", replace(PROTOCOL, observation_seed=287202))
    other_inputs, other_truth = study.generate_data()
    assert other_truth == truth and other_inputs != inputs
    monkeypatch.setattr(study, "PROTOCOL", replace(PROTOCOL, bootstrap_seed=287203))
    assert study.generate_data() == (inputs, truth)
    monkeypatch.setattr(study, "PROTOCOL", replace(PROTOCOL, population_seed=287201))
    assert study.generate_data()[1] != truth
    assert study.observation_days(32, 7) == tuple(range(6, 224, 7))
    assert max(study.observation_days(32, 1)) == 223


def test_frozen_design_and_integrity() -> None:
    study.verify_design(ROOT)
    assert sha256_record(PROTOCOL) == PROTOCOL_DIGEST
    assert STUDY_ID.endswith(PROTOCOL_DIGEST[7:19])
    frozen = json.loads((ROOT / study.DESIGN / "frozen-m0-m5.json").read_bytes())
    assert any("public-native-temporal-expert" in path for path in frozen)
    assert all(
        hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == value[7:]
        for path, value in frozen.items()
    )


def test_full_replay_metrics_and_claim_semantics() -> None:
    bundle = study.build_bundle(ROOT)
    for name, content in bundle.items():
        assert (ROOT / study.HOME / name).read_bytes() == content, name
    manifest = json.loads(bundle["manifest.json"])
    assert manifest["metric_cells"] == 2304
    assert manifest["split"]["training_entities"] == manifest["split"]["selection_entities"] == []
    assert manifest["rights"]["historical_private_artifacts_used"] is False
    assert manifest["realization_digest"] == sha256_record(manifest["realization"])
    assert manifest["split_digest"] == sha256_record(manifest["split"])
    for path, digest in manifest["outputs"].items():
        assert study.digest((ROOT / path).read_bytes()) == digest
    metrics = list(csv.DictReader(io.StringIO(bundle["metrics.csv"].decode())))
    errors = list(csv.DictReader(io.StringIO(bundle["errors.csv"].decode())))
    # Independently recover one metric and its signed bias from saved entity-level errors.
    selected = metrics[0]
    keys = ("lift", "noise_scale", "length", "cadence_days", "channel", "method", "target")
    values = [float(r["error_kg"]) for r in errors if all(r[k] == selected[k] for k in keys)]
    assert len(values) == 32
    assert float(selected["rmse_kg"]) == pytest.approx(math.sqrt(sum(v * v for v in values) / 32))
    assert float(selected["bias_kg"]) == pytest.approx(sum(values) / 32)
    claims = list(csv.DictReader(io.StringIO(bundle["claims.csv"].decode())))
    assert any(row["status"] == "FAIL" for row in claims)
    assert any(row["status"] == "INCONCLUSIVE" for row in claims)
    assert any(row["status"] == "UNSUPPORTED_BY_EVIDENCE" for row in claims)
    assert all(
        not r["rmse_kg"] and r["status"] == "INCONCLUSIVE"
        for r in metrics
        if int(r["invalid_count"]) > 0
    )
