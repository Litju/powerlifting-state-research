"""Typed model-family home.

No model family is asserted at bootstrap. Add a declaration only when a public
research method and its evidence are specified.
"""

from __future__ import annotations

from typing import TypeAlias

ModelFamilyDeclarations: TypeAlias = tuple[()]
MODEL_FAMILIES: ModelFamilyDeclarations = ()
