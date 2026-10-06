"""Home for typed training protocols and run configuration.

No historical training protocol or checkpoint is imported. Future records bind
a method to identified public data, code, environment, and evaluation evidence.
"""

from __future__ import annotations

from typing import TypeAlias

TrainingProtocols: TypeAlias = tuple[()]
TRAINING_PROTOCOLS: TrainingProtocols = ()
