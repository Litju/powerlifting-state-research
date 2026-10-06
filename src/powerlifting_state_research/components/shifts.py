"""
Shared shift component declarations.

Shift identity home; the initial benchmark declarations do not assign a standalone shift ID.
"""

from __future__ import annotations

from ..contracts.components import ComponentReference

shift_references: dict[str, ComponentReference] = {}
