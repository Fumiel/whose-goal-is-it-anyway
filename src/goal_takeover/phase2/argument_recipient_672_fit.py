"""Fixed-hyperparameter cumulative recipient probe over canonical features."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from goal_takeover.phase2.argument_probe import FeatureRow
from goal_takeover.phase2.argument_recipient_672_metric import (
    ROLE_SWAP_VARIANTS,
    role_swap_auc,
    score_role_swap_rows,
)
from goal_takeover.storage.run_writer import sha256_file


def _group_value(row: dict[str, Any], field: str) -> str:
    return row["exposure"][field] if field in {"source_role", "boundary"} else row[field]


def fit_cumulative_stage(
    declaration: dict[str, Any],
    checkpoint: dict[str, Any],
    stage_id: str,
    features: dict[str, list[FeatureRow]],
    *,
    layer: str,
    regularization_c: float,
    max_iter: int,
    seed: int,
    random_label_repeats: int,
    calibration_bins: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fit on the selected cumulative new-data batch and score fixed validation.

    Missing training captures stop the fit. Missing validation captures remain
    visible and make the strict primary metric undefined instead of changing
    its denominator. I/J scores are reported separately from the G/H primary.
    """
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    stages = [stage for stage in checkpoint["stages"] if stage["stage_id"] == stage_id]
    if len(stages) != 1 or checkpoint["primary_metric"] != "role_swap_auc":
        raise ValueError("stage or primary metric differs from checkpoint plan")
    stage = stages[0]
    if (
        layer not in features
        or regularization_c <= 0
        or max_iter < 1
        or random_label_repeats < 1
        or calibration_bins < 2
    ):
        raise ValueError("selected layer or probe fit configuration invalid")
    declared = {row["condition_id"]: row for row in declaration["condition_specs"]}
    rows = features[layer]
    by_id = {row.condition_id: row for row in rows}
    if len(by_id) != len(rows) or set(by_id) - set(declared):
        raise ValueError("feature IDs are duplicate or undeclared")
    train_ids = stage["train_condition_ids"]
    validation_ids = stage["validation_condition_ids"]
    if (
        len(train_ids) != stage["train_count"]
        or len(validation_ids) != 192
        or set(train_ids) & set(validation_ids)
        or set(train_ids) - set(by_id)
    ):
        raise ValueError("cumulative training features or validation plan differ")
    if any(
        by_id[cid].split != "train" or by_id[cid].labels != declared[cid]["argument_present"]
        for cid in train_ids
    ):
        raise ValueError("training feature labels or split differ")
    available_validation_ids = [cid for cid in validation_ids if cid in by_id]
    if any(
        by_id[cid].split != "validation" or by_id[cid].labels != declared[cid]["argument_present"]
        for cid in available_validation_ids
    ):
        raise ValueError("validation feature labels or split differ")
    train_vectors = np.stack([by_id[cid].vector for cid in train_ids])
    if train_vectors.ndim != 2 or not np.isfinite(train_vectors).all():
        raise ValueError("training feature shape or finiteness differs")
    validation_vectors = (
        np.stack([by_id[cid].vector for cid in available_validation_ids])
        if available_validation_ids
        else np.empty((0, train_vectors.shape[1]))
    )
    if (
        validation_vectors.shape[1] != train_vectors.shape[1]
        or not np.isfinite(validation_vectors).all()
    ):
        raise ValueError("validation feature shape or finiteness differs")
    candidates = sorted(declaration["account_value_ids"])
    score_map: dict[str, dict[str, float]] = {cid: {} for cid in available_validation_ids}
    probability_map: dict[str, dict[str, float]] = {cid: {} for cid in available_validation_ids}
    fitted = {}
    for candidate in candidates:
        labels = np.asarray([declared[cid]["argument_present"][candidate] for cid in train_ids])
        if len(set(labels)) != 2:
            raise ValueError(f"training labels lack a class: {candidate}")
        probe = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=regularization_c,
                max_iter=max_iter,
                random_state=seed,
            ),
        )
        probe.fit(train_vectors, labels)
        if available_validation_ids:
            scores = probe.decision_function(validation_vectors)
            probabilities = probe.predict_proba(validation_vectors)[:, 1]
            for cid, score, probability in zip(
                available_validation_ids, scores, probabilities, strict=True
            ):
                score_map[cid][candidate] = float(score)
                probability_map[cid][candidate] = float(probability)
        fitted[candidate] = probe
    primary = role_swap_auc(declaration, score_map)
    if set(stage["primary_metric_condition_ids"]) != {
        row["condition_id"]
        for row in declaration["condition_specs"]
        if row["family_id"] in "GH" and row["condition_variant"] in ROLE_SWAP_VARIANTS
    }:
        raise ValueError("checkpoint primary metric IDs differ")
    diagnostic_rows = [
        row
        for row in declaration["condition_specs"]
        if row["family_id"] in "IJ" and row["condition_variant"] in ROLE_SWAP_VARIANTS
    ]
    if len(diagnostic_rows) != 48:
        raise ValueError("train-linked diagnostic role-swap count differs")
    diagnostic = score_role_swap_rows(diagnostic_rows, candidates, score_map)
    baseline_scores: dict[str, dict[str, float]] = {cid: {} for cid in available_validation_ids}
    train_text = [by_id[cid].user_instruction for cid in train_ids]
    validation_text = [by_id[cid].user_instruction for cid in available_validation_ids]
    for candidate in candidates:
        labels = np.asarray([declared[cid]["argument_present"][candidate] for cid in train_ids])
        baseline = make_pipeline(
            TfidfVectorizer(analyzer="char", ngram_range=(2, 5)),
            LogisticRegression(C=1.0, max_iter=max_iter, random_state=seed),
        )
        baseline.fit(train_text, labels)
        if available_validation_ids:
            baseline_values = baseline.decision_function(validation_text)
            for cid, score in zip(available_validation_ids, baseline_values, strict=True):
                baseline_scores[cid][candidate] = float(score)
    baseline_metric = role_swap_auc(declaration, baseline_scores)
    rng = np.random.default_rng(seed)
    task_indices: dict[str, list[int]] = {}
    for index, cid in enumerate(train_ids):
        task_indices.setdefault(declared[cid]["draft_task_id"], []).append(index)
    random_controls = []
    for repeat in range(random_label_repeats):
        control_scores: dict[str, dict[str, float]] = {cid: {} for cid in available_validation_ids}
        for candidate in candidates:
            labels = np.asarray([declared[cid]["argument_present"][candidate] for cid in train_ids])
            shuffled = labels.copy()
            for indices in task_indices.values():
                shuffled[indices] = rng.permutation(shuffled[indices])
            control = make_pipeline(
                StandardScaler(),
                LogisticRegression(
                    C=regularization_c,
                    max_iter=max_iter,
                    random_state=seed + repeat,
                ),
            )
            control.fit(train_vectors, shuffled)
            if available_validation_ids:
                values = control.decision_function(validation_vectors)
                for cid, score in zip(available_validation_ids, values, strict=True):
                    control_scores[cid][candidate] = float(score)
        random_controls.append(role_swap_auc(declaration, control_scores))
    primary_role_rows = [
        row
        for row in declaration["condition_specs"]
        if row["family_id"] in "GH" and row["condition_variant"] in ROLE_SWAP_VARIANTS
    ]
    strata = {}
    for field in ("family_id", "recipient_rule", "source_role", "boundary"):
        strata[field] = {}
        for value in sorted({_group_value(row, field) for row in primary_role_rows}):
            subset = [row for row in primary_role_rows if _group_value(row, field) == value]
            by_candidate = {}
            for candidate in candidates:
                exposed = [
                    row
                    for row in subset
                    if candidate in {row["recipient_value_id"], row["reference_value_id"]}
                    and row["condition_id"] in score_map
                ]
                labels = [row["argument_present"][candidate] for row in exposed]
                by_candidate[candidate] = {
                    "count": len(exposed),
                    "positive_count": sum(labels),
                    "auc": (
                        float(
                            roc_auc_score(
                                labels,
                                [score_map[row["condition_id"]][candidate] for row in exposed],
                            )
                        )
                        if len(set(labels)) == 2
                        else None
                    ),
                }
            strata[field][value] = {
                "condition_count": len(subset),
                "by_candidate": by_candidate,
            }
    lexical_by_candidate = {}
    for candidate in candidates:
        selected = [
            cid
            for cid in stage["primary_validation_candidate_ids"]
            if cid in score_map and by_id[cid].lexical_presence[candidate]
        ]
        labels = [declared[cid]["argument_present"][candidate] for cid in selected]
        lexical_by_candidate[candidate] = {
            "count": len(selected),
            "positive_count": sum(labels),
            "auc": (
                float(roc_auc_score(labels, [score_map[cid][candidate] for cid in selected]))
                if len(set(labels)) == 2
                else None
            ),
        }
    lexical_complete = all(item["auc"] is not None for item in lexical_by_candidate.values())
    calibration = {}
    for candidate in candidates:
        selected = [
            cid for cid in stage["primary_validation_candidate_ids"] if cid in probability_map
        ]
        labels = np.asarray([declared[cid]["argument_present"][candidate] for cid in selected])
        probabilities = np.asarray([probability_map[cid][candidate] for cid in selected])
        bins = []
        for index in range(calibration_bins):
            in_bin = (
                np.minimum((probabilities * calibration_bins).astype(int), calibration_bins - 1)
                == index
            )
            if in_bin.any():
                bins.append(
                    {
                        "bin": index,
                        "count": int(in_bin.sum()),
                        "mean_probability": float(probabilities[in_bin].mean()),
                        "observed_fraction": float(labels[in_bin].mean()),
                    }
                )
        calibration[candidate] = {
            "count": len(selected),
            "brier": float(brier_score_loss(labels, probabilities)) if len(selected) else None,
            "ece": (
                sum(
                    item["count"] * abs(item["mean_probability"] - item["observed_fraction"])
                    for item in bins
                )
                / len(selected)
                if len(selected)
                else None
            ),
            "bins": bins,
        }
    report = {
        "stage_id": stage_id,
        "train_condition_count": len(train_ids),
        "validation_expected_count": len(validation_ids),
        "validation_available_count": len(available_validation_ids),
        "validation_missing_condition_ids": sorted(
            set(validation_ids) - set(available_validation_ids)
        ),
        "layer": layer,
        "regularization_c": regularization_c,
        "max_iter": max_iter,
        "seed": seed,
        "random_label_repeats": random_label_repeats,
        "calibration_bins": calibration_bins,
        "primary": primary,
        "development_threshold": checkpoint["primary_metric_threshold"],
        "development_threshold_met": (
            primary["auc"] >= checkpoint["primary_metric_threshold"]
            if primary["auc"] is not None
            else None
        ),
        "train_linked_diagnostic": diagnostic,
        "tfidf_baseline_primary": baseline_metric,
        "random_label_controls_primary": random_controls,
        "primary_role_swap_strata": strata,
        "primary_validation_calibration": calibration,
        "secondary_lexical_present": {
            "by_candidate": lexical_by_candidate,
            "mean_auc": (
                sum(item["auc"] for item in lexical_by_candidate.values()) / len(candidates)
                if lexical_complete
                else None
            ),
        },
        "scores_by_condition": score_map,
        "probabilities_by_condition": probability_map,
    }
    return report, fitted


def write_cumulative_fit(
    output_dir: Path,
    report: dict[str, Any],
    fitted: dict[str, Any],
    *,
    provenance: dict[str, Any],
) -> Path:
    """Atomically publish one derived fit and its parameters under a new ID."""
    import numpy as np

    required = (
        "git_commit",
        "design_freeze_sha256",
        "runtime_freeze_sha256",
        "capture_manifest_sha256",
        "b1_selection_sha256",
    )
    if provenance.get("git_dirty") is not False or not all(provenance.get(key) for key in required):
        raise ValueError("derived fit requires frozen provenance and capture checksums")
    if not fitted or set(fitted) != set(report["primary"]["by_candidate"]):
        raise ValueError("fitted candidates differ from reported primary metric")
    if output_dir.exists():
        raise FileExistsError(f"immutable derived fit already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent))
    try:
        payload = {"schema_version": 1, "report": report, "provenance": provenance}
        (temporary / "report.json").write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        arrays = {}
        for candidate, probe in fitted.items():
            arrays[f"{candidate}__mean"] = probe["standardscaler"].mean_
            arrays[f"{candidate}__scale"] = probe["standardscaler"].scale_
            arrays[f"{candidate}__coef"] = probe["logisticregression"].coef_
            arrays[f"{candidate}__intercept"] = probe["logisticregression"].intercept_
        np.savez_compressed(temporary / "probe_parameters.npz", **arrays)
        manifest = {
            "schema_version": 1,
            "stage_id": report["stage_id"],
            "artifacts": {
                name: {
                    "sha256": sha256_file(temporary / name),
                    "bytes": (temporary / name).stat().st_size,
                }
                for name in ("report.json", "probe_parameters.npz")
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        if output_dir.exists():
            raise FileExistsError(f"immutable derived fit already exists: {output_dir}")
        os.rename(temporary, output_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return output_dir
