"""Home for small public research comparators.

No reference model is implemented at bootstrap. Future comparators must state
their inputs, tuning procedure, task scope, and reproducibility requirements.
"""

from __future__ import annotations

from typing import TypeAlias

ReferenceModels: TypeAlias = tuple[()]
REFERENCE_MODELS: ReferenceModels = ()
