"""Public model-family identities."""

from __future__ import annotations

from typing import TypeAlias

from .temporal_expert import MODEL_SPEC_ID

ModelFamilyDeclarations: TypeAlias = tuple[str, ...]
MODEL_FAMILIES: ModelFamilyDeclarations = (MODEL_SPEC_ID,)
