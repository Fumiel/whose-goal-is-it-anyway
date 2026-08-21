"""Explicit selection of representative token positions."""

from __future__ import annotations

from collections.abc import Sequence

from goal_takeover.schemas import ProcessingStage, StagePosition


def last_token_position(token_ids: Sequence[int], stage: ProcessingStage) -> StagePosition:
    """Record the final token rather than relying on an implicit index."""

    if not token_ids:
        raise ValueError("cannot select a position from an empty token sequence")
    return StagePosition(
        stage=stage,
        token_index=len(token_ids) - 1,
        token_id=int(token_ids[-1]),
        sequence_length=len(token_ids),
        selection_rule="last_token",
    )


def trailing_window_indices(sequence_length: int, window_size: int) -> tuple[int, ...]:
    """Return indices for the optional trailing-token sensitivity analysis."""

    if sequence_length <= 0:
        raise ValueError("sequence_length must be positive")
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    start = max(0, sequence_length - window_size)
    return tuple(range(start, sequence_length))
