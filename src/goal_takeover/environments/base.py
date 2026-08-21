"""Environment contracts independent of a specific benchmark domain."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class ToolEnvironment(Protocol):
    """Minimum interface needed by the model-agnostic agent runner."""

    @property
    def tools(self) -> Mapping[str, Any]: ...

    def evaluate_user_task(self) -> bool: ...

    def evaluate_attack(self) -> bool: ...
