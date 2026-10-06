"""
Shared metric component declarations.

Metric identity home; no metric is bound directly by the initial benchmark declarations.
"""

from __future__ import annotations

from ..contracts.components import ComponentReference

metric_references: dict[str, ComponentReference] = {}
