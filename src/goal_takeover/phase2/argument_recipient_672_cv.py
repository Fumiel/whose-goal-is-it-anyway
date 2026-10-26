"""Choose one layer and C on B1 training series before G/H evaluation."""

from __future__ import annotations

from collections import Counter
from typing import Any

from goal_takeover.phase2.argument_probe import FeatureRow
from goal_takeover.phase2.argument_recipient_672_metric import (
    ROLE_SWAP_VARIANTS,
    score_role_swap_rows,
)


def select_b1_layer_and_c(
    declaration: dict[str, Any],
    extracted: dict[str, list[FeatureRow]],
    *,
    seed: int,
    layer_grid: list[int],
    regularization_c_grid: list[float],
    max_iter: int,
) -> dict[str, Any]:
    """Pool leave-one-series-out scores, choose max role-swap AUROC.

    Ties choose the earlier declared layer, then the smaller C. Each
    fold fits scaler and classifier using only the other seven B1 series.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if (
        not layer_grid
        or len(layer_grid) != len(set(layer_grid))
        or not regularization_c_grid
        or len(regularization_c_grid) != len(set(regularization_c_grid))
        or any(c <= 0 for c in regularization_c_grid)
        or max_iter < 1
    ):
        raise ValueError("invalid B1 CV hyperparameter grid")

    b1 = [
        row
        for row in declaration["condition_specs"]
        if row["split_candidate"] == "train" and row["training_batch"] == "B1"
    ]
    if len(b1) != 96 or len({row["condition_id"] for row in b1}) != 96:
        raise ValueError("B1 must contain 96 unique training conditions")
    lookup = {row["condition_id"]: row for row in b1}
    series = sorted({row["semantic_series_id"] for row in b1})
    if len(series) != 8 or Counter(row["semantic_series_id"] for row in b1) != {
        key: 12 for key in series
    }:
        raise ValueError("B1 must contain eight complete 12-condition series")
    role_rows = [row for row in b1 if row["condition_variant"] in ROLE_SWAP_VARIANTS]
    if len(role_rows) != 48:
        raise ValueError("B1 role-swap count differs")
    candidates = sorted(declaration["account_value_ids"])
    for candidate in candidates:
        exposed = [
            row
            for row in role_rows
            if candidate in {row["recipient_value_id"], row["reference_value_id"]}
        ]
        if (len(exposed), sum(row["argument_present"][candidate] for row in exposed)) != (24, 12):
            raise ValueError(f"B1 role-swap class balance differs for {candidate}")
    expected_features = {f"model.layers.{index}" for index in layer_grid}
    if set(extracted) != expected_features:
        raise ValueError("B1 CV feature layer grid differs from declared grid")
    settings = []
    for layer_index in layer_grid:
        layer = f"model.layers.{layer_index}"
        features = {row.condition_id: row for row in extracted[layer]}
        if set(features) != set(lookup) or len(extracted[layer]) != 96:
            raise ValueError(f"B1 CV missing or duplicate feature rows: {layer}")
        for condition_id, feature in features.items():
            declared = lookup[condition_id]
            if (
                feature.split != "train"
                or feature.layer != layer
                or feature.labels != declared["argument_present"]
                or feature.position_name != "Tend_assistant"
                or feature.boundary != declared["exposure"]["boundary"]
            ):
                raise ValueError(f"B1 CV feature identity differs: {condition_id}")
        size = {len(np.asarray(row.vector)) for row in features.values()}
        if len(size) != 1 or not all(np.isfinite(row.vector).all() for row in features.values()):
            raise ValueError("B1 CV feature shape or finiteness differs")
        for c in regularization_c_grid:
            oof: dict[str, dict[str, float]] = {condition_id: {} for condition_id in lookup}
            fold_counts = {}
            for heldout in series:
                training_ids = [
                    condition_id
                    for condition_id, row in lookup.items()
                    if row["semantic_series_id"] != heldout
                ]
                heldout_ids = [
                    condition_id
                    for condition_id, row in lookup.items()
                    if row["semantic_series_id"] == heldout
                ]
                if len(training_ids) != 84 or len(heldout_ids) != 12:
                    raise ValueError("B1 CV fold composition differs")
                x_train = np.stack([features[cid].vector for cid in training_ids])
                x_heldout = np.stack([features[cid].vector for cid in heldout_ids])
                for candidate in candidates:
                    labels = np.asarray(
                        [lookup[cid]["argument_present"][candidate] for cid in training_ids]
                    )
                    if len(set(labels)) != 2:
                        raise ValueError(
                            f"B1 CV training fold lacks a class: {heldout}/{candidate}"
                        )
                    probe = make_pipeline(
                        StandardScaler(),
                        LogisticRegression(C=c, max_iter=max_iter, random_state=seed),
                    )
                    probe.fit(x_train, labels)
                    scores = probe.decision_function(x_heldout)
                    for condition_id, score in zip(heldout_ids, scores, strict=True):
                        oof[condition_id][candidate] = float(score)
                fold_counts[heldout] = {"train": 84, "heldout": 12}
            metric = score_role_swap_rows(role_rows, candidates, oof)
            if metric["status"] != "complete":
                raise ValueError(f"B1 CV metric incomplete: {layer}/C={c}")
            settings.append(
                {
                    "layer": layer,
                    "regularization_c": c,
                    "role_swap_auc": metric["auc"],
                    "fold_counts": fold_counts,
                }
            )
    chosen = min(
        settings,
        key=lambda item: (
            -item["role_swap_auc"],
            layer_grid.index(int(item["layer"].rsplit(".", 1)[-1])),
            sorted(regularization_c_grid).index(item["regularization_c"]),
        ),
    )
    return {
        "selection": "B1_train_leave_one_semantic_series_out_pooled_role_swap_auc",
        "seed": seed,
        "series": series,
        "position_name": "Tend_assistant",
        "layer_grid": list(layer_grid),
        "regularization_c_grid": list(regularization_c_grid),
        "max_iter": max_iter,
        "tie_break": "earlier_declared_layer_then_smaller_c",
        "chosen": {key: chosen[key] for key in ("layer", "regularization_c", "role_swap_auc")},
        "settings": settings,
    }
