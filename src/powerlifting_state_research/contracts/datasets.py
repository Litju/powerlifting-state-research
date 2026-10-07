"""Immutable descriptions of concrete dataset realizations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..artifacts.manifests import RightsMetadata
from .serialization import canonical_json, require_scientific_id, sha256_record


@dataclass(frozen=True, slots=True)
class SplitIdentity:
    split_id: str
    purpose: str
    entity_count: int
    row_count: int

    def __post_init__(self) -> None:
        if not self.split_id.strip() or not self.purpose.strip():
            raise ValueError("split identity and purpose must be non-empty")
        if min(self.entity_count, self.row_count) < 0:
            raise ValueError("split counts cannot be negative")


@dataclass(frozen=True, slots=True)
class ArtifactHash:
    artifact_id: str
    sha256: str
    media_type: str

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or not self.media_type.strip():
            raise ValueError("artifact identity and media type must be non-empty")
        if not re.fullmatch(r"[a-f0-9]{64}", self.sha256):
            raise ValueError("artifact hash must be 64 lowercase hexadecimal characters")


@dataclass(frozen=True, slots=True)
class TemporalCoverage:
    event_index: str
    start: int | str
    end: int | str

    def __post_init__(self) -> None:
        if not self.event_index.strip():
            raise ValueError("temporal event index must be non-empty")
        if isinstance(self.start, int) and isinstance(self.end, int) and self.start > self.end:
            raise ValueError("temporal coverage start must not follow its end")
        if isinstance(self.start, str) and isinstance(self.end, str) and self.start > self.end:
            raise ValueError("temporal coverage start must not follow its end")
        if not (
            isinstance(self.start, int)
            and isinstance(self.end, int)
            or isinstance(self.start, str)
            and isinstance(self.end, str)
        ):
            raise ValueError("temporal coverage bounds must use the same index type")


@dataclass(frozen=True, slots=True)
class SupportSummary:
    axis: str
    description: str

    def __post_init__(self) -> None:
        if not self.axis.strip() or not self.description.strip():
            raise ValueError("support summaries need an axis and description")


@dataclass(frozen=True, slots=True)
class ObservationAvailability:
    field: str
    available_count: int
    missing_count: int

    def __post_init__(self) -> None:
        if not self.field.strip() or min(self.available_count, self.missing_count) < 0:
            raise ValueError("observation availability needs a field and non-negative counts")


@dataclass(frozen=True, slots=True)
class DatasetRealizationManifest:
    dataset_spec_id: str
    realization_id: str
    generator_identity: str | None
    source_identity: str | None
    seeds: tuple[tuple[str, int], ...]
    replicate_ids: tuple[str, ...]
    entity_count: int
    row_count: int
    split_identities: tuple[SplitIdentity, ...]
    artifact_hashes: tuple[ArtifactHash, ...]
    schema_identity: str
    temporal_coverage: TemporalCoverage
    realized_intervention_support: tuple[SupportSummary, ...]
    observation_availability: tuple[ObservationAvailability, ...]
    provenance: str
    rights: RightsMetadata

    def __post_init__(self) -> None:
        if not self.dataset_spec_id.strip() or not self.realization_id.strip():
            raise ValueError("dataset spec and realization IDs must be non-empty")
        require_scientific_id(
            self.dataset_spec_id, "dataset-spec ID", expected_class="dataset-spec"
        )
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.realization_id):
            raise ValueError("realization ID must be a lowercase hyphenated slug")
        if not (self.generator_identity or self.source_identity):
            raise ValueError("a realization needs a generator or collection source identity")
        if not self.schema_identity.strip() or not self.provenance.strip():
            raise ValueError("schema identity and provenance must be explicit")
        if min(self.entity_count, self.row_count) < 0:
            raise ValueError("realization counts cannot be negative")
        if len({name for name, _ in self.seeds}) != len(self.seeds):
            raise ValueError("RNG seed names must be unique")
        if len({split.split_id for split in self.split_identities}) != len(self.split_identities):
            raise ValueError("split identities must be unique")
        if len({item.artifact_id for item in self.artifact_hashes}) != len(self.artifact_hashes):
            raise ValueError("artifact identities must be unique")

    def identity_payload(self) -> dict[str, object]:
        return {
            "dataset_spec_id": self.dataset_spec_id,
            "realization_id": self.realization_id,
            "generator_identity": self.generator_identity,
            "source_identity": self.source_identity,
            "seeds": sorted(self.seeds),
            "replicate_ids": sorted(self.replicate_ids),
            "entity_count": self.entity_count,
            "row_count": self.row_count,
            "split_identities": sorted(self.split_identities, key=lambda item: item.split_id),
            "artifact_hashes": sorted(self.artifact_hashes, key=lambda item: item.artifact_id),
            "schema_identity": self.schema_identity,
            "temporal_coverage": self.temporal_coverage,
            "realized_intervention_support": sorted(
                self.realized_intervention_support, key=lambda item: item.axis
            ),
            "observation_availability": sorted(
                self.observation_availability, key=lambda item: item.field
            ),
        }

    def manifest_payload(self) -> dict[str, object]:
        return {
            **self.identity_payload(),
            "provenance": self.provenance,
            "rights": self.rights,
        }

    @property
    def canonical_serialization(self) -> str:
        return canonical_json(self.manifest_payload())

    @property
    def realization_digest(self) -> str:
        return sha256_record(self.identity_payload())

    @property
    def manifest_digest(self) -> str:
        return sha256_record(self.manifest_payload())

    @property
    def digest(self) -> str:
        return self.realization_digest

    @property
    def identity_id(self) -> str:
        return f"psr:dataset-realization:{self.realization_id}@{self.realization_digest}"
