"""Typed, strict JSONL prediction artifacts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import cast

from ..contracts.serialization import canonical_json_bytes, sha256_record

PREDICTION_SCHEMA_SEMANTICS: dict[str, object] = {
    "format": "UTF-8 canonical compact JSONL; one row per line",
    "fields": {
        "row_id": "string",
        "squat_delta_capacity_kg": "finite number; kg",
        "bench_press_delta_capacity_kg": "finite number; kg",
        "deadlift_delta_capacity_kg": "finite number; kg",
    },
    "additional_fields": "reject",
    "row_key": "row_id",
}
_SCHEMA_DIGEST = sha256_record(
    {
        "format": "PSR_PUBLIC_NATIVE_COMPONENT_ID_V1",
        "component_class": "prediction-schema",
        "slug": "iid-latent-capacity-change-jsonl-row",
        "version": "1.0.0",
        "semantics": PREDICTION_SCHEMA_SEMANTICS,
    },
    reject_floats=True,
)
PREDICTION_SCHEMA_ID = (
    f"psr:prediction-schema:iid-latent-capacity-change-jsonl-row@1.0.0~{_SCHEMA_DIGEST[7:19]}"
)

PREDICTION_FIELDS = frozenset(
    {
        "row_id",
        "squat_delta_capacity_kg",
        "bench_press_delta_capacity_kg",
        "deadlift_delta_capacity_kg",
    }
)
PREDICTION_TARGETS = (
    "squat_delta_capacity_kg",
    "bench_press_delta_capacity_kg",
    "deadlift_delta_capacity_kg",
)


@dataclass(frozen=True, slots=True)
class PredictionRow:
    row_id: str
    squat_delta_capacity_kg: float
    bench_press_delta_capacity_kg: float
    deadlift_delta_capacity_kg: float

    def __post_init__(self) -> None:
        if not isinstance(self.row_id, str) or not self.row_id:
            raise ValueError("prediction row_id must be a non-empty string")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in self.values
        ):
            raise ValueError("prediction targets must be finite JSON numbers")

    @property
    def values(self) -> tuple[float, float, float]:
        return (
            self.squat_delta_capacity_kg,
            self.bench_press_delta_capacity_kg,
            self.deadlift_delta_capacity_kg,
        )


def canonical_prediction_jsonl(rows: tuple[PredictionRow, ...]) -> bytes:
    """Serialize one strict, deterministic compact JSON object per line."""
    ids = [row.row_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("prediction row IDs must be unique")
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON field {key!r}")
        output[key] = value
    return output


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric value {value!r} is rejected")


def parse_prediction_jsonl(content: bytes) -> tuple[PredictionRow, ...]:
    if not content:
        raise ValueError("prediction JSONL is empty")
    if not content.endswith(b"\n"):
        raise ValueError("prediction JSONL must end each row with a newline")
    try:
        lines = content.decode("utf-8", errors="strict").splitlines(keepends=True)
    except UnicodeDecodeError as error:
        raise ValueError("prediction JSONL must be UTF-8") from error
    rows: list[PredictionRow] = []
    seen: set[str] = set()
    for index, line in enumerate(lines, start=1):
        raw_line = line.removesuffix("\n").encode("utf-8")
        if not raw_line:
            raise ValueError(f"prediction JSONL line {index} is empty")
        try:
            value = json.loads(
                raw_line,
                object_pairs_hook=_object,
                parse_constant=_reject_constant,
            )
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError(f"malformed prediction JSONL line {index}: {error}") from error
        if not isinstance(value, dict):
            raise ValueError(f"prediction JSONL line {index} must be an object")
        if set(value) != PREDICTION_FIELDS:
            missing = sorted(PREDICTION_FIELDS - set(value))
            extra = sorted(set(value) - PREDICTION_FIELDS)
            raise ValueError(
                f"prediction JSONL line {index} has invalid fields; "
                f"missing={missing}, extra={extra}"
            )
        try:
            row = PredictionRow(
                row_id=cast(str, value["row_id"]),
                squat_delta_capacity_kg=cast(float, value["squat_delta_capacity_kg"]),
                bench_press_delta_capacity_kg=cast(float, value["bench_press_delta_capacity_kg"]),
                deadlift_delta_capacity_kg=cast(float, value["deadlift_delta_capacity_kg"]),
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid prediction JSONL line {index}: {error}") from error
        if canonical_json_bytes(row) != raw_line:
            raise ValueError(f"prediction JSONL line {index} is not canonical compact JSON")
        if row.row_id in seen:
            raise ValueError(f"duplicate prediction row_id {row.row_id!r}")
        seen.add(row.row_id)
        rows.append(row)
    return tuple(rows)
