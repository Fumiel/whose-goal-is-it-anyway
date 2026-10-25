"""Leave-one-series-out fits within the original recipient-probe training split."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from goal_takeover.phase2.argument_probe import (
    _declaration_sha256,
    _load_json,
    _metrics,
    _sha256,
    extract_features,
)
from goal_takeover.phase2.argument_probe_train_diagnostic import lexical_present_auc


def fold_indices(
    conditions: list[dict[str, Any]], folds: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """Partition original training rows by whole semantic series and task."""
    original_train = [condition for condition in conditions if condition["split"] == "train"]
    families = {condition["paraphrase_family_id"] for condition in original_train}
    if len(folds) < 2 or set(folds.values()) != families or len(set(folds.values())) != len(folds):
        raise ValueError("folds must cover each original training series exactly once")
    result = {}
    for fold_id, held_out in folds.items():
        train = [
            condition
            for condition in original_train
            if condition["paraphrase_family_id"] != held_out
        ]
        validation = [
            condition
            for condition in original_train
            if condition["paraphrase_family_id"] == held_out
        ]
        if not train or not validation:
            raise ValueError(f"empty fold {fold_id}")
        for field in ("task_template_id", "pair_id"):
            if {row[field] for row in train} & {row[field] for row in validation}:
                raise ValueError(f"{field} crosses fold {fold_id}")
        result[fold_id] = {
            "held_out_series": held_out,
            "train_run_ids": [row["run_id"] for row in train],
            "validation_run_ids": [row["run_id"] for row in validation],
            "train_task_ids": sorted({row["task_template_id"] for row in train}),
            "validation_task_ids": sorted({row["task_template_id"] for row in validation}),
        }
    return result


def run(config_path: Path, runs_root: Path, output_dir: Path) -> dict[str, Any]:
    """Refit each declared fold and save new parameters and row-level diagnostics."""
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if output_dir.exists():
        raise FileExistsError(output_dir)
    config = _load_json(config_path)
    if config.get("status") != "post_result_exploratory_train_series_cv":
        raise ValueError("expected post-result exploratory analysis config")
    if config.get("metric") != "candidate_wise_auc_with_lexical_presence_equal_1":
        raise ValueError("unsupported primary metric")
    if config.get("baseline") != "char_tfidf_2_to_5_logistic_regression_c_1":
        raise ValueError("unsupported baseline")
    if config.get("random_label_control") != "within_training_task_first_c_10_repeats":
        raise ValueError("unsupported random-label control")
    spec_path = Path(config["input_spec"])
    spec = _load_json(spec_path)
    original_path = Path(config["original_fit_report"])
    original = _load_json(original_path)
    freeze_path = Path(spec["design_freeze_path"])
    if not freeze_path.is_absolute():
        freeze_path = spec_path.parent / freeze_path
    if (
        spec.get("status") != "frozen_research"
        or _sha256(freeze_path) != spec["design_freeze_sha256"]
        or _load_json(freeze_path).get("probe_declaration_sha256") != _declaration_sha256(spec)
        or original["spec_sha256"] != _sha256(spec_path)
    ):
        raise ValueError("source fit and frozen declaration differ")
    folds = fold_indices(spec["conditions"], config["folds"])
    extracted, missing, manifests = extract_features(spec, runs_root)
    if missing or manifests != original["run_manifests_sha256"]:
        raise ValueError("raw captures differ from the original fit")
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": config["status"],
        "config_sha256": _sha256(config_path),
        "input_spec_sha256": _sha256(spec_path),
        "source_fit_report_sha256": _sha256(original_path),
        "metric": config["metric"],
        "folds": {},
    }
    parameters: dict[str, Any] = {}
    seed = spec["fit"]["seed"]
    first_c = spec["fit"]["regularization_c"][0]
    for fold_id, declaration in folds.items():
        train_ids = set(declaration["train_run_ids"])
        validation_ids = set(declaration["validation_run_ids"])
        fold_report: dict[str, Any] = {
            **declaration,
            "features": {},
        }
        for feature in spec["feature_specs"]:
            feature_id = feature["feature_id"]
            rows = extracted[feature_id]
            train = [row for row in rows if row.run_id in train_ids]
            validation = [row for row in rows if row.run_id in validation_ids]
            if len(train) != len(train_ids) or len(validation) != len(validation_ids):
                raise ValueError(f"missing or duplicate feature row in {fold_id}/{feature_id}")
            x_train = np.stack([row.vector for row in train])
            x_validation = np.stack([row.vector for row in validation])
            feature_report: dict[str, Any] = {"candidates": {}}
            for candidate, account in spec["candidate_values"].items():
                y_train = np.asarray([row.labels[candidate] for row in train], dtype=int)
                y_validation = np.asarray([row.labels[candidate] for row in validation], dtype=int)
                lexical = np.asarray(
                    [row.lexical_presence[candidate] for row in validation], dtype=int
                )
                if any(
                    row.lexical_presence[candidate] != int(account in row.user_instruction)
                    for row in validation
                ):
                    raise ValueError("validation lexical-presence mismatch")
                candidate_report: dict[str, Any] = {"by_c": {}}
                for c in spec["fit"]["regularization_c"]:
                    model = make_pipeline(
                        StandardScaler(),
                        LogisticRegression(
                            C=float(c),
                            max_iter=spec["fit"]["max_iter"],
                            random_state=seed,
                        ),
                    )
                    model.fit(x_train, y_train)
                    scores = model.decision_function(x_validation)
                    probabilities = model.predict_proba(x_validation)[:, 1]
                    metric = lexical_present_auc(y_validation, scores, lexical)
                    c_key = str(c)
                    candidate_report["by_c"][c_key] = {
                        "lexical_present": metric,
                        "all_rows": _metrics(
                            y_validation,
                            scores,
                            probabilities,
                            lexical,
                            calibration_bins=spec["fit"]["calibration_bins"],
                        ),
                        "validation_scores": [float(value) for value in scores],
                    }
                    stem = f"{fold_id}__{feature_id}__{candidate}__c{c_key}"
                    parameters[f"{stem}__mean"] = model["standardscaler"].mean_
                    parameters[f"{stem}__scale"] = model["standardscaler"].scale_
                    parameters[f"{stem}__coef"] = model["logisticregression"].coef_
                    parameters[f"{stem}__intercept"] = model["logisticregression"].intercept_
                baseline = make_pipeline(
                    TfidfVectorizer(analyzer="char", ngram_range=(2, 5)),
                    LogisticRegression(C=1.0, max_iter=spec["fit"]["max_iter"], random_state=seed),
                )
                baseline.fit([row.user_instruction for row in train], y_train)
                baseline_scores = baseline.decision_function(
                    [row.user_instruction for row in validation]
                )
                candidate_report["tfidf_baseline"] = lexical_present_auc(
                    y_validation, baseline_scores, lexical
                )
                groups: dict[str, list[int]] = defaultdict(list)
                for index, row in enumerate(train):
                    groups[row.task_template_id].append(index)
                rng = np.random.default_rng(seed)
                control_aucs = []
                uninformative = 0
                for _ in range(spec["fit"]["random_label_repeats"]):
                    shuffled = y_train.copy()
                    for indices in groups.values():
                        shuffled[indices] = rng.permutation(shuffled[indices])
                    if np.array_equal(shuffled, y_train):
                        uninformative += 1
                        continue
                    control = make_pipeline(
                        StandardScaler(),
                        LogisticRegression(
                            C=float(first_c),
                            max_iter=spec["fit"]["max_iter"],
                            random_state=seed,
                        ),
                    )
                    control.fit(x_train, shuffled)
                    control_scores = control.decision_function(x_validation)
                    control_aucs.append(
                        lexical_present_auc(y_validation, control_scores, lexical)["auc"]
                    )
                candidate_report["random_label_control_first_c"] = {
                    "requested_repeats": spec["fit"]["random_label_repeats"],
                    "uninformative_permutations": uninformative,
                    "auc_values": control_aucs,
                    "mean_auc": float(np.mean(control_aucs)) if control_aucs else None,
                }
                candidate_report["selectivity_first_c"] = (
                    candidate_report["by_c"][str(first_c)]["lexical_present"]["auc"]
                    - candidate_report["random_label_control_first_c"]["mean_auc"]
                    if control_aucs
                    else None
                )
                feature_report["candidates"][candidate] = candidate_report
            fold_report["features"][feature_id] = feature_report
        report["folds"][fold_id] = fold_report
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    np.savez_compressed(output_dir / "probe_parameters.npz", **parameters)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("runs_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    run(args.config, args.runs_root, args.output_dir)


if __name__ == "__main__":
    main()
