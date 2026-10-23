"""Condition-labelled recipient probes over immutable residual capture bundles.

The input specification is deliberately separate from a task draft. Research use
requires a frozen collection declaration; ``synthetic_fixture`` is test-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FeatureRow:
    condition_id: str
    run_id: str
    split: str
    component_id: str
    task_template_id: str
    user_instruction: str
    prefix_id: str
    boundary: str
    token_index: int
    token_id: int
    layer: str
    position_name: str
    labels: dict[str, int]
    lexical_presence: dict[str, int]
    vector: Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _declaration_sha256(spec: dict[str, Any]) -> str:
    declaration = {
        key: spec[key]
        for key in ("candidate_values", "feature_specs", "conditions", "fit", "missing_policy")
    }
    encoded = json.dumps(declaration, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _artifact(bundle: Path, manifest: dict[str, Any], name: str) -> Path:
    entries = [item for item in manifest["artifacts"] if item["relative_path"] == name]
    if len(entries) != 1:
        raise ValueError(f"{bundle.name}: missing or duplicate artifact {name}")
    path = bundle / name
    if not path.is_file() or path.stat().st_size != entries[0]["bytes"]:
        raise ValueError(f"{bundle.name}: artifact size mismatch {name}")
    if _sha256(path) != entries[0]["sha256"]:
        raise ValueError(f"{bundle.name}: artifact checksum mismatch {name}")
    return path


def validate_spec(spec: dict[str, Any]) -> None:
    if spec.get("status") not in {"frozen_research", "synthetic_fixture"}:
        raise ValueError("probe input must be frozen_research or synthetic_fixture")
    if spec.get("missing_policy") != "exclude_with_reason":
        raise ValueError("missing policy must explicitly be exclude_with_reason")
    if spec["status"] == "frozen_research" and not spec.get("design_freeze_sha256"):
        raise ValueError("research input requires a design freeze checksum")
    if spec["status"] == "frozen_research" and not spec.get("design_freeze_path"):
        raise ValueError("research input requires a design freeze path")
    values = spec.get("candidate_values", {})
    if len(values) < 2 or len(set(values.values())) != len(values):
        raise ValueError("candidate values must be unique and include at least two values")
    if not spec.get("feature_specs") or not spec.get("conditions"):
        raise ValueError("feature specs and conditions are required")
    if len({row["feature_id"] for row in spec["feature_specs"]}) != len(spec["feature_specs"]):
        raise ValueError("feature IDs must be unique")
    if len({row["condition_id"] for row in spec["conditions"]}) != len(spec["conditions"]):
        raise ValueError("condition IDs must be unique")
    if len({row["run_id"] for row in spec["conditions"]}) != len(spec["conditions"]):
        raise ValueError("run IDs must be unique")
    group_splits: dict[str, dict[str, str]] = {
        key: {} for key in ("component_id", "task_template_id", "pair_id", "paraphrase_family_id")
    }
    for row in spec["conditions"]:
        split = row["split"]
        if split not in {"train", "validation"}:
            raise ValueError("this development path accepts train and validation only")
        if set(row["argument_present"]) != set(values):
            raise ValueError("candidate label keys do not match candidate values")
        if any(value not in (0, 1) for value in row["argument_present"].values()):
            raise ValueError("candidate labels must be binary")
        for field, mapping in group_splits.items():
            key = row.get(field)
            if key is None:
                continue
            if key in mapping and mapping[key] != split:
                raise ValueError(f"{field} crosses train and validation: {key}")
            mapping[key] = split
    if {"train", "validation"} - set(group_splits["component_id"].values()):
        raise ValueError("both train and independent validation components are required")
    for feature in spec["feature_specs"]:
        if not all(
            feature.get(key)
            for key in ("feature_id", "layer", "boundary", "position_name", "position_rule_version")
        ):
            raise ValueError("incomplete feature specification")
        if feature.get("scope", "actual") != "actual":
            raise ValueError("only actual trajectory captures are supported")
    fit = spec["fit"]
    if not fit.get("regularization_c") or any(float(c) <= 0 for c in fit["regularization_c"]):
        raise ValueError("positive regularization C values are required")
    if fit.get("max_iter", 0) < 1 or not isinstance(fit.get("seed"), int):
        raise ValueError("max_iter and integer seed are required")
    if (
        fit.get("calibration_bins", 0) < 2
        or fit.get("random_label_repeats", 0) < 1
        or fit.get("cluster_bootstrap_repeats", 0) < 1
    ):
        raise ValueError("calibration bins, random controls and cluster bootstrap are required")


def extract_features(
    spec: dict[str, Any], runs_root: Path
) -> tuple[dict[str, list[FeatureRow]], list[dict[str, str]], dict[str, str]]:
    """Verify raw bundle identities and extract aligned, already-exposed positions."""
    import numpy as np
    from safetensors import safe_open

    validate_spec(spec)
    rows = {feature["feature_id"]: [] for feature in spec["feature_specs"]}
    missing: list[dict[str, str]] = []
    manifests: dict[str, str] = {}
    hidden_sizes: dict[str, int] = {}
    model_identities: set[tuple[str, str, str, str]] = set()
    for condition in spec["conditions"]:
        run_id = condition["run_id"]
        if Path(run_id).name != run_id or run_id in {".", ".."}:
            raise ValueError("unsafe run ID")
        bundle = runs_root / run_id
        manifest_path = bundle / "manifest.json"
        manifest = _load_json(manifest_path)
        if manifest["run_id"] != run_id:
            raise ValueError("bundle run ID mismatch")
        manifests[run_id] = _sha256(manifest_path)
        run = _load_json(_artifact(bundle, manifest, "run.json"))
        if (
            run["run_id"] != run_id
            or run["condition_id"] != condition["condition_id"]
            or run["status"] != "completed"
            or run["split"] != condition["split"]
        ):
            raise ValueError(f"{run_id}: run identity, status or split mismatch")
        if run.get("group_id") != condition["component_id"]:
            raise ValueError(f"{run_id}: relationship component mismatch")
        if spec["status"] == "frozen_research":
            model = run.get("model") or {}
            tokenizer = run.get("tokenizer") or {}
            identity = (
                model.get("name"),
                model.get("revision"),
                tokenizer.get("name"),
                tokenizer.get("revision"),
            )
            if (
                not all(identity)
                or run.get("git_dirty") is not False
                or not run.get("git_commit")
                or not run.get("runtime_freeze_sha256")
            ):
                raise ValueError(f"{run_id}: model/tokenizer or execution provenance missing")
            model_identities.add(identity)
        raw_condition = _load_json(_artifact(bundle, manifest, "condition.json"))
        if (
            raw_condition.get("condition_id") != condition["condition_id"]
            or raw_condition.get("user_instruction") != condition["user_instruction"]
            or raw_condition.get("argument_present") != condition["argument_present"]
        ):
            raise ValueError(f"{run_id}: condition label or prompt mismatch")
        prefixes = _load_json(_artifact(bundle, manifest, "prefixes.json"))
        if len(prefixes) != len(run["measurements"]):
            raise ValueError(f"{run_id}: prefix/measurement count mismatch")
        for feature in spec["feature_specs"]:
            feature_id = feature["feature_id"]
            matches = [
                (i, prefix, measure)
                for i, (prefix, measure) in enumerate(
                    zip(prefixes, run["measurements"], strict=True)
                )
                if measure["scope"] == feature.get("scope", "actual")
                and prefix["boundary"] == feature["boundary"]
                and any(
                    p["name"] == feature["position_name"] for p in measure["positions"]["positions"]
                )
            ]
            if not matches:
                missing.append(
                    {
                        "condition_id": condition["condition_id"],
                        "run_id": run_id,
                        "feature_id": feature_id,
                        "reason": "position_missing",
                    }
                )
                continue
            if len(matches) != 1:
                raise ValueError(f"{run_id}: ambiguous feature boundary {feature_id}")
            index, prefix, measure = matches[0]
            prompt = condition["user_instruction"]
            if prefix["text"].count(prompt) != 1:
                raise ValueError(f"{run_id}: declared user prompt absent or ambiguous")
            positions = measure["positions"]
            if positions["position_rule_version"] != feature["position_rule_version"]:
                raise ValueError(f"{run_id}: position rule version mismatch")
            selected = next(
                p for p in positions["positions"] if p["name"] == feature["position_name"]
            )
            token_index = selected["token_index"]
            token_ids = prefix["token_ids"]
            if (
                token_index < 0
                or token_index >= len(token_ids)
                or selected["token_id"] != token_ids[token_index]
                or measure["prefix_id"] != prefix["prefix_id"]
            ):
                raise ValueError(f"{run_id}: selected token identity mismatch")
            offsets = prefix["offsets"]
            if (
                offsets[token_index]["token_index"] != token_index
                or offsets[token_index]["token_id"] != selected["token_id"]
            ):
                raise ValueError(f"{run_id}: selected offset identity mismatch")
            prompt_start = prefix["text"].index(prompt)
            seen_end = max(0, min(len(prompt), offsets[token_index]["end"] - prompt_start))
            seen_text = prompt[:seen_end]
            lexical = {
                key: int(value in seen_text) for key, value in spec["candidate_values"].items()
            }
            if any(
                label and not lexical[key] for key, label in condition["argument_present"].items()
            ):
                missing.append(
                    {
                        "condition_id": condition["condition_id"],
                        "run_id": run_id,
                        "feature_id": feature_id,
                        "reason": "positive_argument_not_yet_exposed",
                    }
                )
                continue
            activation = _load_json(
                _artifact(bundle, manifest, f"measurements/{index}/activation.json")
            )
            if (
                activation["prefix_id"] != prefix["prefix_id"]
                or activation["token_ids"] != token_ids
            ):
                raise ValueError(f"{run_id}: activation prefix/token mismatch")
            indices = activation["positions"]
            if token_index not in indices or indices != sorted(set(indices)):
                raise ValueError(f"{run_id}: activation position mismatch")
            if feature["layer"] not in activation["layers"]:
                raise ValueError(f"{run_id}: requested layer absent")
            tensor_path = _artifact(bundle, manifest, f"measurements/{index}/residual.safetensors")
            with safe_open(tensor_path, framework="pt", device="cpu") as handle:
                if feature["layer"] not in handle.keys():
                    raise ValueError(f"{run_id}: residual layer missing from tensor file")
                tensor = handle.get_tensor(feature["layer"])
                expected = activation["layers"][feature["layer"]]
                if list(tensor.shape) != expected["shape"] or tensor.shape[:2] != (
                    1,
                    len(indices),
                ):
                    raise ValueError(f"{run_id}: residual shape mismatch")
                if str(tensor.dtype) != expected["dtype"]:
                    raise ValueError(f"{run_id}: residual dtype mismatch")
                vector = np.asarray(
                    tensor[0, indices.index(token_index)].float().numpy(), dtype=np.float64
                )
            if vector.ndim != 1 or not np.isfinite(vector).all():
                raise ValueError(f"{run_id}: invalid residual vector")
            if feature_id in hidden_sizes and hidden_sizes[feature_id] != len(vector):
                raise ValueError(f"{run_id}: hidden dimension mismatch")
            hidden_sizes[feature_id] = len(vector)
            rows[feature_id].append(
                FeatureRow(
                    condition_id=condition["condition_id"],
                    run_id=run_id,
                    split=condition["split"],
                    component_id=condition["component_id"],
                    task_template_id=condition["task_template_id"],
                    user_instruction=condition["user_instruction"],
                    prefix_id=prefix["prefix_id"],
                    boundary=prefix["boundary"],
                    token_index=token_index,
                    token_id=selected["token_id"],
                    layer=feature["layer"],
                    position_name=feature["position_name"],
                    labels=dict(condition["argument_present"]),
                    lexical_presence=lexical,
                    vector=vector,
                )
            )
    if len(model_identities) > 1:
        raise ValueError("research probe inputs mix model or tokenizer revisions")
    return rows, missing, manifests


def _metrics(
    labels: Any, scores: Any, probabilities: Any, lexical: Any, *, calibration_bins: int
) -> dict[str, Any]:
    import numpy as np
    from sklearn.metrics import balanced_accuracy_score, brier_score_loss, roc_auc_score

    result: dict[str, Any] = {
        "count": int(len(labels)),
        "positives": int(np.sum(labels)),
        "lexical_present_count": int(np.sum(lexical)),
    }
    if len(labels) and len(set(labels)) == 2:
        result["auc_all"] = float(roc_auc_score(labels, scores))
        result["balanced_accuracy"] = float(balanced_accuracy_score(labels, scores >= 0))
        result["brier"] = float(brier_score_loss(labels, probabilities))
    else:
        result.update(auc_all=None, balanced_accuracy=None, brier=None)
    subset = np.asarray(lexical, dtype=bool)
    result["auc_lexical_present"] = (
        float(roc_auc_score(labels[subset], scores[subset]))
        if subset.any() and len(set(labels[subset])) == 2
        else None
    )
    bin_indices = np.minimum(
        (np.asarray(probabilities) * calibration_bins).astype(int), calibration_bins - 1
    )
    calibration = []
    for index in range(calibration_bins):
        selected = bin_indices == index
        if selected.any():
            calibration.append(
                {
                    "bin": index,
                    "count": int(selected.sum()),
                    "mean_probability": float(np.mean(probabilities[selected])),
                    "observed_fraction": float(np.mean(labels[selected])),
                }
            )
    result["calibration_bins"] = calibration
    result["ece"] = (
        float(
            sum(
                item["count"] * abs(item["mean_probability"] - item["observed_fraction"])
                for item in calibration
            )
            / len(labels)
        )
        if len(labels)
        else None
    )
    return result


def _cluster_bootstrap_auc(
    rows: list[FeatureRow], labels: Any, scores: Any, lexical: Any, *, seed: int, repeats: int
) -> dict[str, Any]:
    import numpy as np
    from sklearn.metrics import roc_auc_score

    components = sorted({row.component_id for row in rows})
    result: dict[str, Any] = {"components": len(components), "requested_repeats": repeats}
    if len(components) < 2:
        return {**result, "valid_repeats": 0, "ci95": None}
    indices_by_component = {
        component: np.asarray(
            [index for index, row in enumerate(rows) if row.component_id == component], dtype=int
        )
        for component in components
    }
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(repeats):
        selected_components = rng.choice(components, size=len(components), replace=True)
        indices = np.concatenate([indices_by_component[key] for key in selected_components])
        indices = indices[np.asarray(lexical)[indices] == 1]
        if len(indices) and len(set(np.asarray(labels)[indices])) == 2:
            estimates.append(
                float(roc_auc_score(np.asarray(labels)[indices], np.asarray(scores)[indices]))
            )
    return {
        **result,
        "valid_repeats": len(estimates),
        "ci95": [float(x) for x in np.quantile(estimates, [0.025, 0.975])] if estimates else None,
    }


def fit_and_evaluate(
    spec: dict[str, Any], extracted: dict[str, list[FeatureRow]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fit all transforms on train only; report every declared feature/C candidate."""
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    validate_spec(spec)
    report: dict[str, Any] = {"features": {}}
    fitted: dict[str, Any] = {}
    seed = spec["fit"]["seed"]
    bins = spec["fit"]["calibration_bins"]
    for feature_id, rows in extracted.items():
        train = [row for row in rows if row.split == "train"]
        validation = [row for row in rows if row.split == "validation"]
        if not train or not validation:
            raise ValueError(f"{feature_id}: train or validation has no usable rows")
        x_train = np.stack([row.vector for row in train])
        x_validation = np.stack([row.vector for row in validation])
        if not np.isfinite(x_train).all() or not np.isfinite(x_validation).all():
            raise ValueError("nonfinite features")
        feature_report: dict[str, Any] = {
            "train_count": len(train),
            "validation_count": len(validation),
            "candidates": {},
        }
        fitted[feature_id] = {}
        for candidate in spec["candidate_values"]:
            y_train = np.asarray([row.labels[candidate] for row in train], dtype=int)
            y_validation = np.asarray([row.labels[candidate] for row in validation], dtype=int)
            lexical = np.asarray([row.lexical_presence[candidate] for row in validation], dtype=int)
            if len(set(y_train)) != 2:
                raise ValueError(f"{feature_id}/{candidate}: train lacks one label class")
            candidate_report: dict[str, Any] = {"by_c": {}}
            for c in spec["fit"]["regularization_c"]:
                probe = make_pipeline(
                    StandardScaler(),
                    LogisticRegression(
                        C=float(c), max_iter=spec["fit"]["max_iter"], random_state=seed
                    ),
                )
                probe.fit(x_train, y_train)
                scores = probe.decision_function(x_validation)
                probabilities = probe.predict_proba(x_validation)[:, 1]
                key = str(c)
                by_component = {}
                for component in sorted({row.component_id for row in validation}):
                    indices = [
                        i for i, row in enumerate(validation) if row.component_id == component
                    ]
                    by_component[component] = _metrics(
                        y_validation[indices],
                        scores[indices],
                        probabilities[indices],
                        lexical[indices],
                        calibration_bins=bins,
                    )
                candidate_report["by_c"][key] = {
                    "validation": _metrics(
                        y_validation, scores, probabilities, lexical, calibration_bins=bins
                    ),
                    "cluster_bootstrap_auc_lexical_present": _cluster_bootstrap_auc(
                        validation,
                        y_validation,
                        scores,
                        lexical,
                        seed=seed,
                        repeats=spec["fit"]["cluster_bootstrap_repeats"],
                    ),
                    "validation_by_component": by_component,
                    "scores": [float(value) for value in scores],
                    "probabilities": [float(value) for value in probabilities],
                }
                fitted[feature_id][(candidate, key)] = probe
            baseline = make_pipeline(
                TfidfVectorizer(analyzer="char", ngram_range=(2, 5)),
                LogisticRegression(C=1.0, max_iter=spec["fit"]["max_iter"], random_state=seed),
            )
            baseline.fit([row.user_instruction for row in train], y_train)
            lexical_scores = baseline.decision_function(
                [row.user_instruction for row in validation]
            )
            candidate_report["tfidf_baseline"] = _metrics(
                y_validation,
                lexical_scores,
                baseline.predict_proba([row.user_instruction for row in validation])[:, 1],
                lexical,
                calibration_bins=bins,
            )
            # Shuffle condition labels within each training task. This keeps each
            # task's label counts and multi-label condition structure intact.
            groups: dict[str, list[int]] = defaultdict(list)
            for index, row in enumerate(train):
                groups[row.task_template_id].append(index)
            rng = np.random.default_rng(seed)
            controls = []
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
                        C=float(spec["fit"]["regularization_c"][0]),
                        max_iter=spec["fit"]["max_iter"],
                        random_state=seed,
                    ),
                )
                control.fit(x_train, shuffled)
                control_scores = control.decision_function(x_validation)
                controls.append(
                    _metrics(
                        y_validation,
                        control_scores,
                        control.predict_proba(x_validation)[:, 1],
                        lexical,
                        calibration_bins=bins,
                    )
                )
            candidate_report["random_label_control"] = {
                "metrics": controls,
                "uninformative_permutations": uninformative,
                "requested_repetitions": spec["fit"]["random_label_repeats"],
            }
            valid_control_auc = [
                item["auc_lexical_present"]
                for item in controls
                if item["auc_lexical_present"] is not None
            ]
            first_c = str(spec["fit"]["regularization_c"][0])
            actual_auc = candidate_report["by_c"][first_c]["validation"]["auc_lexical_present"]
            candidate_report["selectivity_lexical_present_first_c"] = (
                float(actual_auc - np.mean(valid_control_auc))
                if actual_auc is not None and valid_control_auc
                else None
            )
            feature_report["candidates"][candidate] = candidate_report
        report["features"][feature_id] = feature_report
    return report, fitted


def run(spec_path: Path, runs_root: Path, output_dir: Path) -> dict[str, Any]:
    """Create one new derived artifact directory; never alter raw run bundles."""
    import numpy as np

    spec = _load_json(spec_path)
    if spec.get("status") == "frozen_research":
        freeze_path = Path(spec["design_freeze_path"])
        if not freeze_path.is_absolute():
            freeze_path = spec_path.parent / freeze_path
        if _sha256(freeze_path) != spec["design_freeze_sha256"]:
            raise ValueError("design freeze checksum mismatch")
        if _load_json(freeze_path).get("probe_declaration_sha256") != _declaration_sha256(spec):
            raise ValueError("probe declaration differs from design freeze")
    extracted, missing, manifests = extract_features(spec, runs_root)
    report, fitted = fit_and_evaluate(spec, extracted)
    report.update(
        schema_version=1,
        research_result=False,
        input_status=spec["status"],
        design_freeze_sha256=spec.get("design_freeze_sha256"),
        probe_declaration_sha256=_declaration_sha256(spec),
        spec_sha256=_sha256(spec_path),
        run_manifests_sha256=manifests,
        missing=missing,
        missing_by_reason=dict(Counter(item["reason"] for item in missing)),
        row_keys={
            feature_id: [
                {
                    "condition_id": row.condition_id,
                    "run_id": row.run_id,
                    "split": row.split,
                    "component_id": row.component_id,
                    "task_template_id": row.task_template_id,
                    "prefix_id": row.prefix_id,
                    "boundary": row.boundary,
                    "token_index": row.token_index,
                    "token_id": row.token_id,
                    "layer": row.layer,
                    "position_name": row.position_name,
                    "labels": row.labels,
                    "lexical_presence": row.lexical_presence,
                }
                for row in rows
            ]
            for feature_id, rows in extracted.items()
        },
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    arrays = {}
    for feature_id, models in fitted.items():
        for (candidate, c), pipeline in models.items():
            stem = f"{feature_id}__{candidate}__c{c}"
            arrays[f"{stem}__mean"] = pipeline["standardscaler"].mean_
            arrays[f"{stem}__scale"] = pipeline["standardscaler"].scale_
            arrays[f"{stem}__coef"] = pipeline["logisticregression"].coef_
            arrays[f"{stem}__intercept"] = pipeline["logisticregression"].intercept_
    np.savez_compressed(output_dir / "probe_parameters.npz", **arrays)
    return report


def score_saved_probe(
    parameters_path: Path, *, feature_id: str, candidate: str, c: str, vector: Any
) -> float:
    """Apply one saved continuous decision score to an aligned residual vector."""
    import numpy as np

    stem = f"{feature_id}__{candidate}__c{c}"
    with np.load(parameters_path, allow_pickle=False) as arrays:
        mean = arrays[f"{stem}__mean"]
        scale = arrays[f"{stem}__scale"]
        coefficients = arrays[f"{stem}__coef"]
        intercept = arrays[f"{stem}__intercept"]
    selected = np.asarray(vector, dtype=np.float64)
    if selected.shape != mean.shape or not np.isfinite(selected).all():
        raise ValueError("probe input shape or finiteness mismatch")
    if coefficients.shape != (1, len(mean)) or intercept.shape != (1,):
        raise ValueError("saved probe parameter shape mismatch")
    return float((coefficients @ ((selected - mean) / scale)).item() + intercept[0])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fit development recipient probes from immutable captures"
    )
    parser.add_argument("spec", type=Path)
    parser.add_argument("runs_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    run(args.spec, args.runs_root, args.output_dir)


if __name__ == "__main__":
    main()
