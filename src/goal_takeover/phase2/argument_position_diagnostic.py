"""Exploratory recipient probes at positions retained in the 96-run captures."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from goal_takeover.phase2.argument_probe import (
    _artifact,
    _load_json,
    _sha256,
    validate_spec,
)


@dataclass(frozen=True)
class PositionSelection:
    indices: tuple[int, ...]
    anchor: int


def select_saved_position(
    name: str, positions: dict[str, Any], saved: list[int]
) -> PositionSelection | None:
    """Return only fully saved positions; never substitute a nearby token."""
    named = {p["name"]: p["token_index"] for p in positions["positions"]}
    if name in {"tpre", "tpost", "tend_assistant"}:
        anchor = named[{"tpre": "Tpre", "tpost": "Tpost", "tend_assistant": "Tend_assistant"}[name]]
        indices = (anchor,)
    elif name in {"post4", "post8", "post16", "post_mean_0_8"}:
        anchor = named["Tpost"]
        indices = (
            tuple(range(anchor, anchor + 9))
            if name == "post_mean_0_8"
            else (anchor + int(name[4:]),)
        )
    else:
        raise ValueError(f"unknown position rule: {name}")
    if not set(indices).issubset(saved):
        return None
    return PositionSelection(indices, anchor)


def load_rows(
    source: dict[str, Any], runs_root: Path, position_names: list[str], layers: list[str]
) -> tuple[dict[str, dict[str, Any]], dict[str, str], list[dict[str, str]]]:
    """Verify original run identity and artifact checksums before reading residuals."""
    import numpy as np
    from safetensors import safe_open

    validate_spec(source)
    rows: dict[str, dict[str, Any]] = {}
    manifests: dict[str, str] = {}
    missing: list[dict[str, str]] = []
    identities = set()
    for condition in source["conditions"]:
        run_id = condition["run_id"]
        if Path(run_id).name != run_id:
            raise ValueError("unsafe run ID")
        bundle = runs_root / run_id
        manifest_path = bundle / "manifest.json"
        manifest = _load_json(manifest_path)
        if manifest["run_id"] != run_id:
            raise ValueError("run manifest identity mismatch")
        manifests[run_id] = _sha256(manifest_path)
        run = _load_json(_artifact(bundle, manifest, "run.json"))
        raw_condition = _load_json(_artifact(bundle, manifest, "condition.json"))
        if (
            run["run_id"] != run_id
            or run["condition_id"] != condition["condition_id"]
            or run["status"] not in {"completed", "model_failure"}
            or run["split"] != condition["split"]
            or run["group_id"] != condition["component_id"]
            or raw_condition["argument_present"] != condition["argument_present"]
            or raw_condition["user_instruction"] != condition["user_instruction"]
            or run.get("git_dirty") is not False
        ):
            raise ValueError(f"{run_id}: run or condition mismatch")
        identity = (
            run["model"]["name"],
            run["model"]["revision"],
            run["tokenizer"]["name"],
            run["tokenizer"]["revision"],
        )
        identities.add(identity)
        prefixes = _load_json(_artifact(bundle, manifest, "prefixes.json"))
        matches = [
            (i, p, m)
            for i, (p, m) in enumerate(zip(prefixes, run["measurements"], strict=True))
            if m["scope"] == "actual"
            and p["boundary"] == "user_to_assistant"
            and m["positions"].get("exposed")
        ]
        if len(matches) != 1:
            raise ValueError(f"{run_id}: expected one exposed first user boundary")
        measure_index, prefix, measure = matches[0]
        if prefix["text"].count(condition["user_instruction"]) != 1:
            raise ValueError(f"{run_id}: prompt mismatch")
        activation = _load_json(
            _artifact(bundle, manifest, f"measurements/{measure_index}/activation.json")
        )
        saved = activation["positions"]
        token_ids = prefix["token_ids"]
        if (
            measure["prefix_id"] != prefix["prefix_id"]
            or activation["prefix_id"] != prefix["prefix_id"]
            or activation["token_ids"] != token_ids
            or saved != sorted(set(saved))
            or measure["positions"]["position_rule_version"] != "protocol_offsets_v1"
        ):
            raise ValueError(f"{run_id}: prefix or position alignment mismatch")
        selections = {}
        for name in position_names:
            selection = select_saved_position(name, measure["positions"], saved)
            if selection is None:
                missing.append({"run_id": run_id, "position": name, "reason": "not_saved"})
                continue
            if any(i < 0 or i >= len(token_ids) for i in selection.indices):
                raise ValueError(f"{run_id}: position outside prefix")
            selections[name] = selection
        tensor_path = _artifact(
            bundle, manifest, f"measurements/{measure_index}/residual.safetensors"
        )
        vectors: dict[str, dict[str, Any]] = {name: {} for name in selections}
        with safe_open(tensor_path, framework="pt", device="cpu") as handle:
            for layer in layers:
                if layer not in activation["layers"] or layer not in handle.keys():
                    raise ValueError(f"{run_id}: missing layer {layer}")
                tensor = handle.get_tensor(layer)
                if list(tensor.shape) != activation["layers"][layer]["shape"] or tensor.shape[
                    :2
                ] != (1, len(saved)):
                    raise ValueError(f"{run_id}: residual shape mismatch")
                for name, selection in selections.items():
                    values = tensor[0, [saved.index(i) for i in selection.indices]].float().numpy()
                    vector = np.asarray(values.mean(axis=0), dtype=np.float64)
                    if vector.ndim != 1 or not np.isfinite(vector).all():
                        raise ValueError(f"{run_id}: invalid residual")
                    vectors[name][layer] = vector
        for name, selection in selections.items():
            if name == "tpre" and selection.anchor >= next(
                p["token_index"] for p in measure["positions"]["positions"] if p["name"] == "Tpost"
            ):
                raise ValueError("Tpre must precede Tpost")
        rows[run_id] = {
            "condition": condition,
            "prefix_id": prefix["prefix_id"],
            "token_indices": {k: list(v.indices) for k, v in selections.items()},
            "token_ids": {k: [token_ids[i] for i in v.indices] for k, v in selections.items()},
            "vectors": vectors,
        }
    if len(identities) != 1:
        raise ValueError("mixed model or tokenizer revisions")
    return rows, manifests, missing


def fit_positions(
    source: dict[str, Any], rows: dict[str, dict[str, Any]], positions: list[str], layers: list[str]
) -> dict[str, Any]:
    """Use the original labels, split, layers, C grid and train-only scaler."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    result = {}
    for position in positions:
        available = [row for row in rows.values() if position in row["vectors"]]
        train = [row for row in available if row["condition"]["split"] == "train"]
        val = [row for row in available if row["condition"]["split"] == "validation"]
        if len(train) != 64 or len(val) != 32:
            result[position] = {
                "status": "skipped_incomplete_96",
                "train": len(train),
                "validation": len(val),
            }
            continue
        result[position] = {"status": "evaluated", "train": 64, "validation": 32, "settings": {}}
        for layer in layers:
            x_train = np.stack([row["vectors"][position][layer] for row in train])
            x_val = np.stack([row["vectors"][position][layer] for row in val])
            for c in source["fit"]["regularization_c"]:
                key = f"{layer}/C={c}"
                by_candidate = {}
                for candidate, value in source["candidate_values"].items():
                    y_train = np.asarray(
                        [row["condition"]["argument_present"][candidate] for row in train]
                    )
                    y_val = np.asarray(
                        [row["condition"]["argument_present"][candidate] for row in val]
                    )
                    lexical = np.asarray(
                        [value in row["condition"]["user_instruction"] for row in val]
                    )
                    model = make_pipeline(
                        StandardScaler(),
                        LogisticRegression(
                            C=float(c),
                            max_iter=source["fit"]["max_iter"],
                            random_state=source["fit"]["seed"],
                        ),
                    )
                    model.fit(x_train, y_train)
                    scores = model.decision_function(x_val)
                    subset = lexical & np.isfinite(scores)
                    auc = (
                        float(roc_auc_score(y_val[subset], scores[subset]))
                        if len(set(y_val[subset])) == 2
                        else None
                    )
                    component_aucs = {}
                    for component in sorted({row["condition"]["component_id"] for row in val}):
                        part = subset & np.asarray(
                            [row["condition"]["component_id"] == component for row in val]
                        )
                        component_aucs[component] = (
                            float(roc_auc_score(y_val[part], scores[part]))
                            if len(set(y_val[part])) == 2
                            else None
                        )
                    by_candidate[candidate] = {
                        "auc_lexical_present_full_prompt": auc,
                        "auc_all_rows": float(roc_auc_score(y_val, scores)),
                        "lexical_present_count": int(subset.sum()),
                        "validation_by_component": component_aucs,
                        "validation_scores": {
                            row["condition"]["condition_id"]: float(score)
                            for row, score in zip(val, scores, strict=True)
                        },
                    }
                values = [x["auc_lexical_present_full_prompt"] for x in by_candidate.values()]
                result[position]["settings"][key] = {
                    "mean_auc_lexical_present": float(np.mean(values))
                    if all(x is not None for x in values)
                    else None,
                    "candidates": by_candidate,
                }
    return result


def run(config_path: Path, runs_root: Path, output_dir: Path) -> dict[str, Any]:
    config = _load_json(config_path)
    source_path = Path(config["source_spec_path"])
    if not source_path.is_absolute():
        source_path = config_path.parent / source_path
    if _sha256(source_path) != config["source_spec_sha256"]:
        raise ValueError("original probe declaration checksum mismatch")
    source = _load_json(source_path)
    freeze = source_path.parent / source["design_freeze_path"]
    if _sha256(freeze) != source["design_freeze_sha256"]:
        raise ValueError("original probe freeze checksum mismatch")
    rows, manifests, missing = load_rows(source, runs_root, config["positions"], config["layers"])
    result = {
        "status": "exploratory_post_result_development",
        "config_sha256": _sha256(config_path),
        "source_spec_sha256": _sha256(source_path),
        "source_freeze_sha256": _sha256(freeze),
        "run_manifest_sha256": manifests,
        "missing": missing,
        "position_indices_and_ids": {
            k: {
                "indices": v["token_indices"],
                "token_ids": v["token_ids"],
                "prefix_id": v["prefix_id"],
            }
            for k, v in rows.items()
        },
        "results": fit_positions(source, rows, config["positions"], config["layers"]),
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "report.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("runs_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    result = run(args.config, args.runs_root, args.output_dir)
    print(
        json.dumps(
            {
                k: {"status": v["status"], "train": v["train"], "validation": v["validation"]}
                for k, v in result["results"].items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
