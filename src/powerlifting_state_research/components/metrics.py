"""
Shared metric component declarations.

Metric identity home; no metric is bound directly by the initial benchmark declarations.
"""

from __future__ import annotations

from ..contracts.components import ComponentClass, ComponentReference, ComponentResolution

metric_references: dict[str, ComponentReference] = {
    name: ComponentReference(
        ComponentClass.METRIC,
        name,
        ComponentResolution.DIRECT_PUBLIC_NATIVE_IDENTITY,
    )
    for name in (
        "iid_public_rmse",
        "iid_public_mae",
        "iid_public_r_squared",
        "iid_public_sre_ddof_0",
    )
}
