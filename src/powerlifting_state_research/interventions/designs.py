"""Typed home for controlled contrasts; no experiment is run at bootstrap."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ControlledContrast:
    slug: str
    changed_axes: tuple[str, ...]
    held_fixed_axes: tuple[str, ...]


CONTROLLED_CONTRASTS: tuple[ControlledContrast, ...] = ()
