"""In-sample diagnostic for an already fitted recipient probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from goal_takeover.phase2.argument_probe import (
    _declaration_sha256,
    _load_json,
    _sha256,
    extract_features,
)


def score_matrix(vectors: Any, mean: Any, scale: Any, coef: Any, intercept: Any) -> Any:
    """Apply saved StandardScaler and binary linear-probe parameters."""
    import numpy as np

    vectors = np.asarray(vectors, dtype=np.float64)
    mean = np.asarray(mean, dtype=np.float64)
    scale = np.asarray(scale, dtype=np.float64)
    coef = np.asarray(coef, dtype=np.float64)
    intercept = np.asarray(intercept, dtype=np.float64)
    if (
        vectors.ndim != 2
        or mean.shape != (vectors.shape[1],)
        or scale.shape != mean.shape
        or coef.shape != (1, vectors.shape[1])
        or intercept.shape != (1,)
        or not all(np.isfinite(array).all() for array in (vectors, mean, scale, coef, intercept))
        or np.any(scale <= 0)
    ):
        raise ValueError("invalid saved probe parameter or feature shape")
    return ((vectors - mean) / scale) @ coef[0] + intercept[0]


def lexical_present_auc(labels: Any, scores: Any, lexical_presence: Any) -> dict[str, Any]:
    """Score recipient positives against reference-account negatives only."""
    import numpy as np
    from sklearn.metrics import roc_auc_score

    labels = np.asarray(labels)
    scores = np.asarray(scores, dtype=np.float64)
    lexical_presence = np.asarray(lexical_presence)
    if (
        labels.ndim != 1
        or scores.shape != labels.shape
        or lexical_presence.shape != labels.shape
        or not np.isin(labels, [0, 1]).all()
        or not np.isin(lexical_presence, [0, 1]).all()
        or not np.isfinite(scores).all()
        or np.any((labels == 1) & (lexical_presence == 0))
    ):
        raise ValueError("invalid or unexposed lexical-present labels")
    selected = lexical_presence == 1
    y = labels[selected]
    if len(np.unique(y)) != 2:
        raise ValueError("lexical-present subset needs recipient and reference rows")
    return {
        "count": int(selected.sum()),
        "recipient_positives": int(y.sum()),
        "reference_negatives": int((y == 0).sum()),
        "auc": float(roc_auc_score(y, scores[selected])),
    }


def run(spec_path: Path, runs_root: Path, fitted_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Verify raw captures and saved fit, then write a separate derived report."""
    import numpy as np

    if output_dir.exists():
        raise FileExistsError(output_dir)
    spec = _load_json(spec_path)
    original = _load_json(fitted_dir / "report.json")
    parameters_path = fitted_dir / "probe_parameters.npz"
    freeze_path = Path(spec["design_freeze_path"])
    if not freeze_path.is_absolute():
        freeze_path = spec_path.parent / freeze_path
    if (
        spec.get("status") != "frozen_research"
        or _sha256(freeze_path) != spec["design_freeze_sha256"]
        or _load_json(freeze_path).get("probe_declaration_sha256") != _declaration_sha256(spec)
        or original["spec_sha256"] != _sha256(spec_path)
        or original["probe_declaration_sha256"] != _declaration_sha256(spec)
    ):
        raise ValueError("saved fit and frozen input declaration differ")
    extracted, missing, manifests = extract_features(spec, runs_root)
    if missing or manifests != original["run_manifests_sha256"]:
        raise ValueError("current raw captures differ from the saved fit")
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "in_sample_training_diagnostic_not_independent_validation",
        "fit_spec_sha256": _sha256(spec_path),
        "fitted_report_sha256": _sha256(fitted_dir / "report.json"),
        "fitted_parameters_sha256": _sha256(parameters_path),
        "metric": "per_candidate_auc_with_lexical_presence_equal_1",
        "label_source": "frozen_condition_argument_present",
        "features": {},
    }
    with np.load(parameters_path, allow_pickle=False) as arrays:
        for feature in spec["feature_specs"]:
            feature_id = feature["feature_id"]
            rows = extracted[feature_id]
            train = [row for row in rows if row.split == "train"]
            validation = [row for row in rows if row.split == "validation"]
            saved_feature = original["features"][feature_id]
            if (
                len(train) != saved_feature["train_count"]
                or len(validation) != saved_feature["validation_count"]
            ):
                raise ValueError(f"unexpected row count for {feature_id}")
            for row, saved in zip(rows, original["row_keys"][feature_id], strict=True):
                if any(
                    getattr(row, key) != saved[key]
                    for key in (
                        "condition_id",
                        "run_id",
                        "split",
                        "prefix_id",
                        "token_index",
                        "token_id",
                    )
                ):
                    raise ValueError(f"saved row alignment differs for {feature_id}")
            x_train = np.stack([row.vector for row in train])
            x_validation = np.stack([row.vector for row in validation])
            candidate_results = {}
            for candidate in spec["candidate_values"]:
                labels = [row.labels[candidate] for row in train]
                lexical = [row.lexical_presence[candidate] for row in train]
                by_c = {}
                for c in spec["fit"]["regularization_c"]:
                    c_key = str(c)
                    stem = f"{feature_id}__{candidate}__c{c_key}"
                    params = [
                        arrays[f"{stem}__{name}"] for name in ("mean", "scale", "coef", "intercept")
                    ]
                    train_scores = score_matrix(x_train, *params)
                    validation_scores = score_matrix(x_validation, *params)
                    saved_scores = original["features"][feature_id]["candidates"][candidate][
                        "by_c"
                    ][c_key]["scores"]
                    if not np.allclose(validation_scores, saved_scores, rtol=1e-10, atol=1e-10):
                        raise ValueError(f"saved validation scores differ for {stem}")
                    by_c[c_key] = {
                        "train": lexical_present_auc(labels, train_scores, lexical),
                        "validation_auc": original["features"][feature_id]["candidates"][candidate][
                            "by_c"
                        ][c_key]["validation"]["auc_lexical_present"],
                    }
                candidate_results[candidate] = by_c
            report["features"][feature_id] = {
                "train_count": len(train),
                "validation_count": len(validation),
                "candidates": candidate_results,
            }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("runs_root", type=Path)
    parser.add_argument("fitted_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    run(args.spec, args.runs_root, args.fitted_dir, args.output_dir)


if __name__ == "__main__":
    main()
