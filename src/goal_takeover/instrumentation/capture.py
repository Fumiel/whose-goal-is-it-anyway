"""Prefix-bound activation records that prevent cross-consumer misalignment."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from goal_takeover.serialization.prefix import SerializedPrefix


@dataclass(frozen=True)
class ActivationRecord:
    prefix_id: str
    token_ids: tuple[int, ...]
    positions: tuple[int, ...]
    values: Mapping[str, Any]

    def assert_matches(self, prefix: SerializedPrefix) -> None:
        if self.prefix_id != prefix.prefix_id or self.token_ids != prefix.token_ids:
            raise ValueError("activation record does not match serialized prefix")


class ActivationExtractor(Protocol):
    def capture(
        self, prefix: SerializedPrefix, *, positions: Sequence[int]
    ) -> ActivationRecord: ...
