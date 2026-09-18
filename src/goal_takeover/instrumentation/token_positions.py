"""Character-to-token alignment for the four protocol positions."""

from __future__ import annotations

from collections.abc import Sequence

from goal_takeover.schemas import TokenPosition, TokenPositionName
from goal_takeover.serialization.prefix import SerializedPrefix, TokenOffset


def overlapping_token_indices(
    offsets: Sequence[TokenOffset], *, start: int, end: int
) -> tuple[int, ...]:
    """Return tokens whose non-empty character offsets overlap a half-open span."""

    if start < 0 or end <= start:
        raise ValueError("character span must be non-empty and ordered")
    return tuple(
        offset.token_index
        for offset in offsets
        if offset.end > offset.start and offset.start < end and offset.end > start
    )


def _position(
    prefix: SerializedPrefix,
    name: TokenPositionName,
    index: int,
    rule: str,
) -> TokenPosition:
    return TokenPosition(
        name=name,
        token_index=index,
        token_id=prefix.token_ids[index],
        sequence_length=len(prefix.token_ids),
        selection_rule=rule,
    )


def select_protocol_positions(
    prefix: SerializedPrefix,
    *,
    injection_span: tuple[int, int],
    tool_content_span: tuple[int, int],
) -> dict[TokenPositionName, TokenPosition]:
    """Select Tpre, Tpost, Tend_tool, and Tend_assistant deterministically."""

    injection_start, injection_end = injection_span
    tool_start, tool_end = tool_content_span
    if not (tool_start <= injection_start < injection_end <= tool_end):
        raise ValueError("injection span must be contained in tool content span")

    preceding = [
        offset.token_index
        for offset in prefix.offsets
        if offset.end > offset.start and offset.end <= injection_start
    ]
    injection_tokens = overlapping_token_indices(
        prefix.offsets, start=injection_start, end=injection_end
    )
    tool_tokens = overlapping_token_indices(prefix.offsets, start=tool_start, end=tool_end)
    if not preceding:
        raise ValueError("Tpre does not exist before the injection span")
    if not injection_tokens:
        raise ValueError("no token overlaps the injection span")
    if not tool_tokens:
        raise ValueError("no token overlaps the tool-content span")

    positions = {
        TokenPositionName.TPRE: _position(
            prefix,
            TokenPositionName.TPRE,
            preceding[-1],
            "last_nonempty_token_ending_before_ipi_start",
        ),
        TokenPositionName.TPOST: _position(
            prefix,
            TokenPositionName.TPOST,
            injection_tokens[-1],
            "last_nonempty_token_overlapping_ipi",
        ),
        TokenPositionName.TEND_TOOL: _position(
            prefix,
            TokenPositionName.TEND_TOOL,
            tool_tokens[-1],
            "last_nonempty_token_overlapping_tool_content",
        ),
        TokenPositionName.TEND_ASSISTANT: _position(
            prefix,
            TokenPositionName.TEND_ASSISTANT,
            len(prefix.token_ids) - 1,
            "last_prompt_token_at_assistant_generation_boundary",
        ),
    }
    return positions


def trailing_window_indices(sequence_length: int, window_size: int) -> tuple[int, ...]:
    """Return indices for the optional trailing-token sensitivity analysis."""

    if sequence_length <= 0:
        raise ValueError("sequence_length must be positive")
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    start = max(0, sequence_length - window_size)
    return tuple(range(start, sequence_length))
