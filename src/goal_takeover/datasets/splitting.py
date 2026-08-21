"""Deterministic assignment of whole condition groups to data splits."""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping


def assign_group_splits(
    group_ids: Iterable[str],
    *,
    seed: int,
    proportions: Mapping[str, float] | None = None,
) -> dict[str, str]:
    """Assign each unique group exactly once, preventing within-group leakage."""

    fractions = dict(proportions or {"train": 0.6, "validation": 0.2, "test": 0.2})
    if not fractions or any(value < 0 for value in fractions.values()):
        raise ValueError("split proportions must be non-negative and non-empty")
    total = math.fsum(fractions.values())
    if not math.isclose(total, 1.0, abs_tol=1e-9):
        raise ValueError("split proportions must sum to 1")

    unique_ids = sorted(set(group_ids))
    if not unique_ids:
        return {}
    random.Random(seed).shuffle(unique_ids)

    raw_counts = {name: len(unique_ids) * fraction for name, fraction in fractions.items()}
    counts = {name: math.floor(value) for name, value in raw_counts.items()}
    remainder = len(unique_ids) - sum(counts.values())
    priority = sorted(
        fractions,
        key=lambda name: (raw_counts[name] - counts[name], fractions[name], name),
        reverse=True,
    )
    for name in priority[:remainder]:
        counts[name] += 1

    assignments: dict[str, str] = {}
    cursor = 0
    for split_name in fractions:
        next_cursor = cursor + counts[split_name]
        for group_id in unique_ids[cursor:next_cursor]:
            assignments[group_id] = split_name
        cursor = next_cursor
    return assignments
