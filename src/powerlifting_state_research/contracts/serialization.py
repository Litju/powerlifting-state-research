"""Canonical JSON and content hashing helpers for immutable records."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

_SCIENTIFIC_ID = re.compile(r"^psr:(?P<class>[a-z0-9-]+):[a-z0-9][a-z0-9-]*@[^~]+~[a-f0-9]{12}$")
_SHA256_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
_BENCHMARK_ID = re.compile(
    r"^psr:benchmark-spec:[a-z0-9][a-z0-9-]*@[0-9]+\.[0-9]+\.[0-9]+~(?P<prefix>[a-f0-9]{12})$"
)
_DATASET_REALIZATION_ID = re.compile(
    r"^psr:dataset-realization:[a-z0-9]+(?:-[a-z0-9]+)*@(?P<digest>sha256:[a-f0-9]{64})$"
)


def require_scientific_id(value: str, label: str, *, expected_class: str | None = None) -> None:
    """Validate the stable public ID form used by component references."""
    match = _SCIENTIFIC_ID.fullmatch(value)
    if match is None or (expected_class is not None and match["class"] != expected_class):
        raise ValueError(f"{label} must be a complete versioned scientific ID")


def require_benchmark_digest_match(benchmark_id: str, digest: str, label: str) -> None:
    match = _BENCHMARK_ID.fullmatch(benchmark_id)
    if match is None or not _SHA256_DIGEST.fullmatch(digest):
        raise ValueError(f"{label} must reference a minted benchmark ID and full SHA-256 digest")
    if digest[7:19] != match["prefix"]:
        raise ValueError(f"{label} digest prefix does not match the benchmark ID")


def require_dataset_realization_digest_match(realization_id: str, digest: str, label: str) -> None:
    match = _DATASET_REALIZATION_ID.fullmatch(realization_id)
    if match is None or not _SHA256_DIGEST.fullmatch(digest):
        raise ValueError(
            f"{label} must reference a canonical dataset realization ID and full SHA-256 digest"
        )
    if digest != match["digest"]:
        raise ValueError(f"{label} digest does not match the dataset realization ID")


def _plain(value: Any, *, reject_floats: bool) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _plain(getattr(value, field.name), reject_floats=reject_floats)
            for field in fields(value)
        }
    if isinstance(value, Enum):
        return _plain(value.value, reject_floats=reject_floats)
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, float):
        if reject_floats:
            raise TypeError("floating point values are not allowed in semantic identity payloads")
        if not math.isfinite(value):
            raise ValueError("canonical JSON cannot contain non-finite numbers")
        return value
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical JSON object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in output:
                raise ValueError("object keys collide after Unicode NFC normalization")
            output[normalized_key] = _plain(item, reject_floats=reject_floats)
        return output
    if isinstance(value, (list, tuple)):
        return [_plain(item, reject_floats=reject_floats) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [_plain(item, reject_floats=reject_floats) for item in value]
        return sorted(
            normalized, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True)
        )
    if value is None or isinstance(value, (bool, int)):
        return value
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Any, *, reject_floats: bool = False) -> bytes:
    """Serialize records deterministically as compact UTF-8 JSON."""
    plain = _plain(value, reject_floats=reject_floats)
    return json.dumps(
        plain,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json(value: Any, *, reject_floats: bool = False) -> str:
    return canonical_json_bytes(value, reject_floats=reject_floats).decode("utf-8")


def sha256_record(value: Any, *, reject_floats: bool = False) -> str:
    return (
        "sha256:"
        + hashlib.sha256(canonical_json_bytes(value, reject_floats=reject_floats)).hexdigest()
    )
