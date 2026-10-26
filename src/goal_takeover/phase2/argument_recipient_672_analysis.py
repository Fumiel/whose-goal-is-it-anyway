"""Run one frozen cumulative probe stage from verified canonical bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from goal_takeover.phase2.argument_recipient_672_cv import select_b1_layer_and_c
from goal_takeover.phase2.argument_recipient_672_features import load_canonical_features
from goal_takeover.phase2.argument_recipient_672_fit import (
    fit_cumulative_stage,
    write_cumulative_fit,
)
from goal_takeover.phase2.argument_recipient_672_runner import load_frozen_plan
from goal_takeover.storage.run_writer import sha256_file

STAGES = ("B1", "B1_to_B2", "B1_to_B3", "B1_to_B4", "B1_to_B5")


def stage_run_ids(
    declaration: dict[str, Any], checkpoint: dict[str, Any], stage_id: str, prefix: str
) -> dict[str, str]:
    """Require exactly the cumulative train and common validation captures."""
    if stage_id not in STAGES or not prefix or "/" in prefix or "\\" in prefix:
        raise ValueError("invalid stage or run prefix")
    stage = next(row for row in checkpoint["stages"] if row["stage_id"] == stage_id)
    wanted = set(stage["train_condition_ids"]) | set(stage["validation_condition_ids"])
    run_ids = {
        row["condition_id"]: f"{prefix}-c{index:03d}"
        for index, row in enumerate(declaration["condition_specs"], start=1)
        if row["condition_id"] in wanted
    }
    if len(run_ids) != stage["train_count"] + 192:
        raise ValueError("stage capture ID count differs")
    return run_ids


def _load_selection(path: Path, expected: dict[str, Any]) -> tuple[dict[str, Any], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("provenance") != expected or payload.get("stage_id") != "B1":
        raise ValueError("B1 selection provenance differs")
    selected = payload.get("selection", {})
    if selected.get("selection") != "B1_train_leave_one_semantic_series_out_pooled_role_swap_auc":
        raise ValueError("B1 selection method differs")
    return selected, sha256_file(path)


def _check_previous_analysis(
    root: Path, analysis_id: str, stage_id: str, selection_sha: str, common: dict[str, Any]
) -> None:
    previous = dict(zip(STAGES[1:], STAGES[:-1], strict=True))[stage_id]
    directory = root / "artifacts/processed" / f"{analysis_id}-{previous}"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    report_path = directory / "report.json"
    entry = manifest["artifacts"]["report.json"]
    if sha256_file(report_path) != entry["sha256"] or report_path.stat().st_size != entry["bytes"]:
        raise ValueError("previous analysis checksum differs")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        manifest["stage_id"] != previous
        or payload["report"]["stage_id"] != previous
        or payload["report"]["primary"]["status"] != "complete"
        or payload["report"]["validation_available_count"] != 192
        or payload["provenance"]["b1_selection_sha256"] != selection_sha
        or any(payload["provenance"].get(key) != value for key, value in common.items())
    ):
        raise ValueError("previous analysis is not the matching completed stage")


def run_stage(
    config_path: Path,
    *,
    stage_id: str,
    run_prefix: str,
    analysis_id: str,
    selection_path: Path | None = None,
    runtime_freeze_override: Path | None = None,
) -> Path:
    """Select on B1 train alone, then score the fixed validation set."""
    if not analysis_id or "/" in analysis_id or "\\" in analysis_id:
        raise ValueError("invalid analysis ID")
    config, declaration, split = load_frozen_plan(
        config_path, runtime_freeze_override=runtime_freeze_override
    )
    root = config_path.resolve().parents[2]
    checkpoint = json.loads((root / config["references"]["checkpoints"]).read_text())
    fit = config["fit"]
    ids = stage_run_ids(declaration, checkpoint, stage_id, run_prefix)
    design_sha = sha256_file(root / config["references"]["design_freeze"])
    runtime_sha = sha256_file(root / config["_resolved_runtime_freeze_path"])
    runtime = json.loads((root / config["_resolved_runtime_freeze_path"]).read_text())
    common = {
        "git_commit": runtime["git_commit"],
        "design_freeze_sha256": design_sha,
        "runtime_freeze_sha256": runtime_sha,
        "run_prefix": run_prefix,
    }
    runs_root = root / "artifacts/runs"
    output = root / "artifacts/processed" / f"{analysis_id}-{stage_id}"
    if output.exists():
        raise FileExistsError(f"derived stage already exists: {output}")
    if stage_id == "B1":
        if selection_path is not None:
            raise ValueError("B1 selects its own layer and C")
        b1_ids = set(checkpoint["stages"][0]["train_condition_ids"])
        b1 = {cid: run_id for cid, run_id in ids.items() if cid in b1_ids}
        train_features, train_hashes = load_canonical_features(
            declaration,
            split,
            runs_root,
            b1,
            layers=[f"model.layers.{index}" for index in fit["layer_grid"]],
            design_freeze_sha256=design_sha,
            runtime_freeze_sha256=runtime_sha,
        )
        selection = select_b1_layer_and_c(
            declaration,
            train_features,
            seed=config["seed"],
            layer_grid=fit["layer_grid"],
            regularization_c_grid=fit["regularization_c_grid"],
            max_iter=fit["max_iter"],
        )
        selection_path = root / "artifacts/processed" / f"{analysis_id}-b1-selection.json"
        selection_path.parent.mkdir(parents=True, exist_ok=True)
        with selection_path.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "schema_version": 1,
                    "stage_id": "B1",
                    "provenance": common,
                    "train_capture_manifest_sha256": train_hashes,
                    "selection": selection,
                },
                stream,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            stream.write("\n")
    else:
        if selection_path is None:
            raise ValueError("later stages require the fixed B1 selection file")
        if not selection_path.is_absolute():
            selection_path = root / selection_path
        selection_path = selection_path.resolve()
        if not selection_path.is_relative_to(root / "artifacts/processed"):
            raise ValueError("selection file must be a derived artifact")
    selection, selection_sha = _load_selection(selection_path, common)
    if stage_id != "B1":
        _check_previous_analysis(root, analysis_id, stage_id, selection_sha, common)
    chosen = selection["chosen"]
    layer = chosen["layer"]
    c = chosen["regularization_c"]
    if (
        layer not in {f"model.layers.{index}" for index in fit["layer_grid"]}
        or c not in fit["regularization_c_grid"]
    ):
        raise ValueError("B1 selected layer or C lies outside frozen grid")
    features, capture_hashes = load_canonical_features(
        declaration,
        split,
        runs_root,
        ids,
        layers=[layer],
        design_freeze_sha256=design_sha,
        runtime_freeze_sha256=runtime_sha,
    )
    report, fitted = fit_cumulative_stage(
        declaration,
        checkpoint,
        stage_id,
        features,
        layer=layer,
        regularization_c=c,
        max_iter=fit["max_iter"],
        seed=config["seed"],
        random_label_repeats=fit["random_label_repeats"],
        calibration_bins=fit["calibration_bins"],
    )
    return write_cumulative_fit(
        output,
        report,
        fitted,
        provenance={
            **common,
            "git_dirty": False,
            "capture_manifest_sha256": capture_hashes,
            "b1_selection_sha256": selection_sha,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument("--analysis-id", required=True)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--runtime-freeze", type=Path)
    args = parser.parse_args()
    print(
        run_stage(
            args.config,
            stage_id=args.stage,
            run_prefix=args.run_prefix,
            analysis_id=args.analysis_id,
            selection_path=args.selection,
            runtime_freeze_override=args.runtime_freeze,
        )
    )


if __name__ == "__main__":
    main()
