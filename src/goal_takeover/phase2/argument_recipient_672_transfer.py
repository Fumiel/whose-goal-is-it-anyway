"""Canonical-to-actual consistency of a fixed recipient probe (RDR-2026-10-27-03).

This applies an already fitted probe; it never refits, selects a layer, or
recomputes labels from the generated calls.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from goal_takeover.phase2.argument_recipient_672_analysis import STAGES
from goal_takeover.phase2.argument_recipient_672_features import (
    _verified_artifact,
    load_canonical_features,
)
from goal_takeover.phase2.argument_recipient_672_metric import _auc
from goal_takeover.phase2.argument_recipient_672_runner import load_frozen_plan
from goal_takeover.storage.run_writer import sha256_file

PRIMARY_FAMILIES = frozenset({"G", "H"})


def load_actual_rows(
    declaration: dict[str, Any],
    runs_root: Path,
    run_ids: list[str],
    *,
    layer: str,
    design_freeze_sha256: str,
    runtime_freeze_sha256: str,
) -> dict[str, dict[str, Any]]:
    """Load the verified actual `Tend_assistant` residual and prefix per condition."""
    import numpy as np
    from safetensors import safe_open

    declared = {row["condition_id"]: row for row in declaration["condition_specs"]}
    rows: dict[str, dict[str, Any]] = {}
    for run_id in run_ids:
        bundle = runs_root / run_id
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        run = json.loads(_verified_artifact(bundle, manifest, "run.json").read_text("utf-8"))
        condition_id = run["condition_id"]
        provenance = run["provenance"]
        condition = json.loads(_verified_artifact(bundle, manifest, "condition.json").read_text())
        position = run.get("selected_position")
        if (
            run["run_id"] != run_id
            or run["status"] != "completed"
            or run["capture_role"] != "actual_behavior_and_transfer"
            or condition_id not in declared
            or condition_id in rows
            or condition != declared[condition_id]
            or provenance["git_dirty"] is not False
            or provenance["design_freeze_sha256"] != design_freeze_sha256
            or provenance["runtime_freeze_sha256"] != runtime_freeze_sha256
            or not position
            or position["name"] != "Tend_assistant"
        ):
            raise ValueError(f"{run_id}: actual run declaration or provenance differs")
        prefixes = json.loads(_verified_artifact(bundle, manifest, "prefixes.json").read_text())
        matches = [item for item in prefixes if item["prefix_id"] == position["prefix_id"]]
        if len(matches) != 1:
            raise ValueError(f"{run_id}: selected prefix missing or duplicated")
        token_ids = matches[0]["token_ids"]
        index = position["token_index"]
        if index != len(token_ids) - 1 or token_ids[index] != position["token_id"]:
            raise ValueError(f"{run_id}: actual selected token differs from prefix")
        tensor_path = _verified_artifact(bundle, manifest, "residual.safetensors")
        with safe_open(tensor_path, framework="pt", device="cpu") as handle:
            if layer not in handle.keys():
                raise ValueError(f"{run_id}: residual layer missing: {layer}")
            tensor = handle.get_tensor(layer)
        if tuple(tensor.shape[:2]) != (1, 1):
            raise ValueError(f"{run_id}: residual shape differs")
        vector = np.asarray(tensor[0, 0].float().numpy(), dtype=np.float64)
        if vector.ndim != 1 or not np.isfinite(vector).all():
            raise ValueError(f"{run_id}: residual vector invalid")
        rows[condition_id] = {
            "run_id": run_id,
            "vector": vector,
            "token_ids": token_ids,
            "boundary": matches[0]["boundary"],
        }
    return rows


def load_canonical_rows(
    declaration: dict[str, Any],
    split: dict[str, Any],
    runs_root: Path,
    run_ids_by_condition: dict[str, str],
    *,
    layer: str,
    design_freeze_sha256: str,
    runtime_freeze_sha256: str,
) -> dict[str, dict[str, Any]]:
    features, _ = load_canonical_features(
        declaration,
        split,
        runs_root,
        run_ids_by_condition,
        layers=[layer],
        design_freeze_sha256=design_freeze_sha256,
        runtime_freeze_sha256=runtime_freeze_sha256,
    )
    rows = {}
    for feature in features[layer]:
        bundle = runs_root / feature.run_id
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        prefix = json.loads(_verified_artifact(bundle, manifest, "prefix.json").read_text())
        rows[feature.condition_id] = {
            "run_id": feature.run_id,
            "vector": feature.vector,
            "token_ids": prefix["token_ids"],
            "boundary": feature.boundary,
        }
    return rows


def decision_values(vector: Any, probe: dict[str, Any]) -> float:
    return float(((vector - probe["mean"]) / probe["scale"]) @ probe["coef"] + probe["intercept"])


def _descriptive_role_swap(
    items: list[dict[str, Any]], candidates: list[str], key: str
) -> dict[str, Any]:
    by_candidate: dict[str, Any] = {}
    for candidate in candidates:
        exposed = [
            item
            for item in items
            if candidate in (item["recipient_value_id"], item["reference_value_id"])
        ]
        labels = [item["labels"][candidate] for item in exposed]
        scores = [item[key][candidate] for item in exposed]
        positives = sum(labels)
        defined = 0 < positives < len(labels)
        by_candidate[candidate] = {
            "positive_count": positives,
            "negative_count": len(labels) - positives,
            "auc": _auc(labels, scores) if defined else None,
        }
    aucs = [value["auc"] for value in by_candidate.values()]
    return {
        "by_candidate": by_candidate,
        "mean_auc": sum(aucs) / len(aucs) if all(a is not None for a in aucs) else None,
        "descriptive_only": True,
    }


def compute_transfer(
    declaration: dict[str, Any],
    canonical: dict[str, dict[str, Any]],
    actual: dict[str, dict[str, Any]],
    probes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compare fixed-probe decisions and residuals; thresholds and tests are not defined."""
    import numpy as np

    if set(canonical) != set(actual):
        raise ValueError("canonical and actual condition sets differ")
    candidates = sorted(probes)
    declared = {row["condition_id"]: row for row in declaration["condition_specs"]}
    items = []
    for condition_id in sorted(actual):
        spec = declared[condition_id]
        can, act = canonical[condition_id], actual[condition_id]
        cosine = float(
            can["vector"] @ act["vector"]
            / (np.linalg.norm(can["vector"]) * np.linalg.norm(act["vector"]))
        )
        relative_l2 = float(
            np.linalg.norm(can["vector"] - act["vector"]) / np.linalg.norm(can["vector"])
        )
        items.append(
            {
                "condition_id": condition_id,
                "canonical_run_id": can["run_id"],
                "actual_run_id": act["run_id"],
                "split": spec["split_candidate"],
                "family_id": spec["family_id"],
                "boundary": act["boundary"],
                "recipient_value_id": spec["recipient_value_id"],
                "reference_value_id": spec["reference_value_id"],
                "labels": spec["argument_present"],
                "prefix_identical": can["token_ids"] == act["token_ids"],
                "cosine": cosine,
                "relative_l2": relative_l2,
                "canonical_decision": {
                    c: decision_values(can["vector"], probes[c]) for c in candidates
                },
                "actual_decision": {c: decision_values(act["vector"], probes[c]) for c in candidates},
            }
        )

    def summarize(subset: list[dict[str, Any]]) -> dict[str, Any]:
        if not subset:
            return {"condition_count": 0}
        can_values = [item["canonical_decision"][c] for item in subset for c in candidates]
        act_values = [item["actual_decision"][c] for item in subset for c in candidates]
        diffs = np.abs(np.asarray(can_values) - np.asarray(act_values))
        identical = [item for item in subset if item["prefix_identical"]]
        argmax_same = sum(
            max(candidates, key=item["canonical_decision"].get)
            == max(candidates, key=item["actual_decision"].get)
            for item in subset
        )
        return {
            "condition_count": len(subset),
            "prefix_identical_count": len(identical),
            "max_relative_l2_when_prefix_identical": (
                max(item["relative_l2"] for item in identical) if identical else None
            ),
            "min_cosine": min(item["cosine"] for item in subset),
            "median_relative_l2": float(np.median([item["relative_l2"] for item in subset])),
            "decision_pearson": (
                float(np.corrcoef(can_values, act_values)[0, 1])
                if len(subset) > 1 and np.std(can_values) > 0 and np.std(act_values) > 0
                else None
            ),
            "decision_abs_diff_max": float(diffs.max()),
            "decision_abs_diff_median": float(np.median(diffs)),
            "argmax_candidate_agreement": argmax_same,
            "descriptive_role_swap_auc": {
                "canonical": _descriptive_role_swap(subset, candidates, "canonical_decision"),
                "actual": _descriptive_role_swap(subset, candidates, "actual_decision"),
            },
        }

    validation = [item for item in items if item["split"] == "validation"]
    return {
        "metric_spec": "RDR-2026-10-27-03",
        "candidates": candidates,
        "all": summarize(items),
        "validation_split": summarize(validation),
        "validation_gh": summarize([item for item in validation if item["family_id"] in PRIMARY_FAMILIES]),
        "train_split_in_sample_consistency": summarize(
            [item for item in items if item["split"] == "train"]
        ),
        "by_prefix_identity": {
            "identical": summarize([item for item in items if item["prefix_identical"]]),
            "different": summarize([item for item in items if not item["prefix_identical"]]),
        },
        "by_boundary": {
            boundary: summarize([item for item in items if item["boundary"] == boundary])
            for boundary in sorted({item["boundary"] for item in items})
        },
        "conditions": items,
    }


def load_probes(path: Path, candidates: list[str]) -> dict[str, dict[str, Any]]:
    import numpy as np

    with np.load(path) as stored:
        return {
            c: {
                "mean": stored[f"{c}__mean"],
                "scale": stored[f"{c}__scale"],
                "coef": stored[f"{c}__coef"][0],
                "intercept": float(stored[f"{c}__intercept"][0]),
            }
            for c in candidates
        }


def run_transfer(
    config_path: Path,
    *,
    fit_analysis_dir: Path,
    canonical_prefix: str,
    actual_prefix: str,
    output_id: str,
    runtime_freeze_override: Path,
) -> Path:
    if not output_id or "/" in output_id or "\\" in output_id:
        raise ValueError("invalid output ID")
    config, declaration, split = load_frozen_plan(
        config_path, runtime_freeze_override=runtime_freeze_override
    )
    root = config_path.resolve().parents[2]
    fit_dir = fit_analysis_dir if fit_analysis_dir.is_absolute() else root / fit_analysis_dir
    output = root / "artifacts/processed" / output_id
    if output.exists():
        raise FileExistsError(f"immutable transfer output exists: {output}")
    if not fit_dir.resolve().is_relative_to(root / "artifacts/processed"):
        raise ValueError("fit must be a derived artifact")
    manifest = json.loads((fit_dir / "manifest.json").read_text(encoding="utf-8"))
    for name, entry in manifest["artifacts"].items():
        if sha256_file(fit_dir / name) != entry["sha256"]:
            raise ValueError(f"fit artifact checksum differs: {name}")
    if manifest["stage_id"] not in STAGES:
        raise ValueError("fit stage unknown")
    fit = json.loads((fit_dir / "report.json").read_text(encoding="utf-8"))
    layer, c = fit["report"]["layer"], fit["report"]["regularization_c"]
    design_sha = sha256_file(root / config["references"]["design_freeze"])
    runtime_sha = sha256_file(root / runtime_freeze_override)
    if fit["provenance"]["runtime_freeze_sha256"] != runtime_sha:
        raise ValueError("fit and runs use different runtime freezes")
    sample = json.loads((root / config["references"]["actual_sample"]).read_text())
    sample_ids = {cid for item in sample["selections"] for cid in item["condition_ids"]}
    runs_root = root / "artifacts/runs"
    actual_dirs = sorted(
        path.name for path in runs_root.glob(f"{actual_prefix}-a[0-9][0-9][0-9]") if path.is_dir()
    )
    actual = load_actual_rows(
        declaration,
        runs_root,
        actual_dirs,
        layer=layer,
        design_freeze_sha256=design_sha,
        runtime_freeze_sha256=runtime_sha,
    )
    if set(actual) != sample_ids:
        raise ValueError("actual runs differ from the declared sample")
    run_ids = {
        row["condition_id"]: f"{canonical_prefix}-c{index:03d}"
        for index, row in enumerate(declaration["condition_specs"], start=1)
        if row["condition_id"] in sample_ids
    }
    canonical = load_canonical_rows(
        declaration,
        split,
        runs_root,
        run_ids,
        layer=layer,
        design_freeze_sha256=design_sha,
        runtime_freeze_sha256=runtime_sha,
    )
    candidates = sorted(declaration["account_value_ids"])
    report = compute_transfer(
        declaration, canonical, actual, load_probes(fit_dir / "probe_parameters.npz", candidates)
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=root
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True, cwd=root
    ).stdout.strip()
    if dirty:
        raise ValueError("transfer evaluation requires a clean working tree")
    output.mkdir(parents=True)
    payload = {
        "schema_version": 1,
        "research_result": "development_consistency_not_validity",
        "provenance": {
            "git_commit": commit,
            "git_dirty": False,
            "fit_analysis": fit_dir.name,
            "fit_report_sha256": manifest["artifacts"]["report.json"]["sha256"],
            "fit_parameters_sha256": manifest["artifacts"]["probe_parameters.npz"]["sha256"],
            "layer": layer,
            "regularization_c": c,
            "design_freeze_sha256": design_sha,
            "runtime_freeze_sha256": runtime_sha,
            "canonical_prefix": canonical_prefix,
            "actual_prefix": actual_prefix,
        },
        "report": report,
    }
    with (output / "report.json").open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--fit-analysis-dir", type=Path, required=True)
    parser.add_argument("--canonical-prefix", required=True)
    parser.add_argument("--actual-prefix", required=True)
    parser.add_argument("--output-id", required=True)
    parser.add_argument("--runtime-freeze", type=Path, required=True)
    args = parser.parse_args()
    print(
        run_transfer(
            args.config,
            fit_analysis_dir=args.fit_analysis_dir,
            canonical_prefix=args.canonical_prefix,
            actual_prefix=args.actual_prefix,
            output_id=args.output_id,
            runtime_freeze_override=args.runtime_freeze,
        )
    )


if __name__ == "__main__":
    main()
