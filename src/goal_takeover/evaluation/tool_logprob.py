"""Sequence-level scores for legitimate and attacker-specified tool calls."""

from __future__ import annotations

import math
from collections.abc import Sequence


def sequence_log_probability(token_log_probabilities: Sequence[float]) -> float:
    """Sum conditional token log probabilities for a complete tool-call string."""

    if not token_log_probabilities:
        raise ValueError("a tool-call sequence must contain at least one token")
    values = [float(value) for value in token_log_probabilities]
    if any(not math.isfinite(value) or value > 0 for value in values):
        raise ValueError("log probabilities must be finite and no greater than zero")
    return math.fsum(values)


def tool_margin(
    attack_token_log_probabilities: Sequence[float],
    legitimate_token_log_probabilities: Sequence[float],
) -> float:
    """Attack minus legitimate whole-sequence log probability."""

    return sequence_log_probability(
        attack_token_log_probabilities
    ) - sequence_log_probability(legitimate_token_log_probabilities)


def selected_token_log_probability(logits: Sequence[float], token_id: int) -> float:
    """Compute one selected token's log probability using stable log-softmax."""

    if not logits:
        raise ValueError("logits cannot be empty")
    if token_id < 0 or token_id >= len(logits):
        raise IndexError("token_id is outside the vocabulary")
    values = [float(value) for value in logits]
    if any(not math.isfinite(value) for value in values):
        raise ValueError("logits must be finite")
    maximum = max(values)
    log_normalizer = maximum + math.log(math.fsum(math.exp(value - maximum) for value in values))
    return values[token_id] - log_normalizer
