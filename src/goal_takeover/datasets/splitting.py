"""Deterministic assignment of whole condition groups to data splits."""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Iterable, Mapping
from typing import Any


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


def connected_component_groups(
    conditions: Iterable[Mapping[str, Any]], *, group_keys: Iterable[str]
) -> dict[str, str]:
    """Group conditions connected by any declared semantic-family identifier."""

    rows = [dict(condition) for condition in conditions]
    condition_ids = [str(row["condition_id"]) for row in rows]
    if len(set(condition_ids)) != len(condition_ids):
        raise ValueError("condition_id values must be unique")
    keys = tuple(group_keys)
    if not keys:
        raise ValueError("at least one group key is required")

    parent = {condition_id: condition_id for condition_id in condition_ids}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    seen_values: dict[tuple[str, str], str] = {}
    for row in rows:
        condition_id = str(row["condition_id"])
        for key in keys:
            value = row.get(key)
            if value is None or value == "":
                continue
            marker = (key, str(value))
            if marker in seen_values:
                union(condition_id, seen_values[marker])
            else:
                seen_values[marker] = condition_id

    members: dict[str, list[str]] = {}
    for condition_id in condition_ids:
        members.setdefault(find(condition_id), []).append(condition_id)
    component_ids = {
        root: "component_" + hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()[:16]
        for root, ids in members.items()
    }
    return {condition_id: component_ids[find(condition_id)] for condition_id in condition_ids}


def assign_condition_splits(
    conditions: Iterable[Mapping[str, Any]],
    *,
    group_keys: Iterable[str],
    seed: int,
    proportions: Mapping[str, float] | None = None,
) -> dict[str, str]:
    """Assign connected semantic components and return condition-level splits."""

    rows = [dict(condition) for condition in conditions]
    components = connected_component_groups(rows, group_keys=group_keys)
    component_splits = assign_group_splits(components.values(), seed=seed, proportions=proportions)
    return {
        condition_id: component_splits[component_id]
        for condition_id, component_id in components.items()
    }
