"""Small attention helpers; attention is treated as a descriptive metric only."""

from __future__ import annotations

import math
from collections.abc import Sequence


def attention_mass(weights: Sequence[float], token_indices: Sequence[int]) -> float:
    """Sum attention probability assigned to a declared token region."""

    if not weights:
        raise ValueError("weights cannot be empty")
    if any(not math.isfinite(float(value)) or value < 0 for value in weights):
        raise ValueError("attention weights must be finite and non-negative")
    if any(index < 0 or index >= len(weights) for index in token_indices):
        raise IndexError("attention token index is outside the sequence")
    return math.fsum(float(weights[index]) for index in token_indices)
