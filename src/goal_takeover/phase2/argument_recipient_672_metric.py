"""Strict role-swap AUROC for the reviewed 672-condition collection.

This computes an evaluation statistic; it does not fit or select a probe.
"""

from __future__ import annotations

import math
from typing import Any

ROLE_SWAP_VARIANTS = frozenset({"rx_ref_y", "ry_ref_x"})
PRIMARY_FAMILIES = frozenset({"G", "H"})


def primary_metric_rows(declaration: dict[str, Any]) -> list[dict[str, Any]]:
    """Return exactly the declared independent primary role-swap conditions."""
    rows = [
        row
        for row in declaration["condition_specs"]
        if row["family_id"] in PRIMARY_FAMILIES and row["condition_variant"] in ROLE_SWAP_VARIANTS
    ]
    if len(rows) != 48 or len({row["condition_id"] for row in rows}) != 48:
        raise ValueError("expected 48 unique G/H role-swap conditions")
    candidates = set(declaration["account_value_ids"])
    for row in rows:
        if row["split_candidate"] != "validation":
            raise ValueError("primary metric condition is outside validation")
        if set(row["argument_present"]) != candidates:
            raise ValueError("candidate label set differs from declaration")
        if sum(row["argument_present"].values()) != 1:
            raise ValueError("role-swap condition must have one recipient")
    for candidate in candidates:
        labels = [row["argument_present"][candidate] for row in rows]
        if (sum(labels), len(labels) - sum(labels)) != (12, 36):
            raise ValueError(f"unbalanced primary labels for {candidate}")
        # The two-account subset has 24 rows per candidate, of which 12 are
        # recipient and 12 are reference. Other 24 rows omit that candidate.
        exposed = [
            row
            for row in rows
            if row["recipient_value_id"] == candidate or row["reference_value_id"] == candidate
        ]
        if len(exposed) != 24 or sum(row["argument_present"][candidate] for row in exposed) != 12:
            raise ValueError(f"unbalanced exposed role-swap rows for {candidate}")
    return rows


def _auc(labels: list[int], scores: list[float]) -> float:
    positives = [score for label, score in zip(labels, scores, strict=True) if label == 1]
    negatives = [score for label, score in zip(labels, scores, strict=True) if label == 0]
    if not positives or not negatives:
        raise ValueError("AUROC requires both classes")
    return sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives) / (
        len(positives) * len(negatives)
    )


def role_swap_auc(
    declaration: dict[str, Any], scores_by_condition: dict[str, dict[str, float]]
) -> dict[str, Any]:
    """Use exposed candidates only; any missing score makes the mean undefined.

    ``scores_by_condition`` may include diagnostic rows; only reviewed G/H
    role-swap IDs enter this metric. A missing row, candidate, or finite score
    produces a null metric and explicit missing records, never a partial mean.
    """
    return score_role_swap_rows(
        primary_metric_rows(declaration),
        sorted(declaration["account_value_ids"]),
        scores_by_condition,
    )


def score_role_swap_rows(
    rows: list[dict[str, Any]],
    candidates: list[str],
    scores_by_condition: dict[str, dict[str, float]],
) -> dict[str, Any]:
    """Calculate a complete-case role-swap mean for a prevalidated row set."""
    missing: list[dict[str, str]] = []
    by_candidate: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        exposed = [
            row
            for row in rows
            if row["recipient_value_id"] == candidate or row["reference_value_id"] == candidate
        ]
        labels: list[int] = []
        scores: list[float] = []
        for row in exposed:
            condition_id = row["condition_id"]
            score = scores_by_condition.get(condition_id, {}).get(candidate)
            if (
                score is None
                or isinstance(score, bool)
                or not isinstance(score, (float, int))
                or not math.isfinite(score)
            ):
                missing.append({"condition_id": condition_id, "candidate": candidate})
                continue
            labels.append(row["argument_present"][candidate])
            scores.append(float(score))
        by_candidate[candidate] = {
            "positive_count": sum(labels),
            "negative_count": len(labels) - sum(labels),
            "expected_positive_count": 12,
            "expected_negative_count": 12,
            "auc": _auc(labels, scores) if len(scores) == 24 else None,
        }
    complete = not missing and all(item["auc"] is not None for item in by_candidate.values())
    return {
        "metric": "role_swap_auc",
        "status": "complete" if complete else "undefined_incomplete_scores",
        "condition_count": len(rows),
        "candidate_count": len(candidates),
        "auc": (
            sum(item["auc"] for item in by_candidate.values()) / len(candidates)
            if complete
            else None
        ),
        "by_candidate": by_candidate,
        "missing": missing,
    }
