"""Train-only post-result readout diagnostic for the 672 recipient probe.

Leave-one-semantic-series-out over the 480 B1-B5 training conditions at the
saved ``Tend_assistant`` residual. No validation capture is loaded. The
frozen-plan objective (candidate-wise, all rows) is compared with an
exposed-only objective, and presence and paired role readouts are reported
separately from the role-swap AUROC. This is diagnostic, not a stage fit.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from goal_takeover.phase2.argument_recipient_672_features import load_canonical_features
from goal_takeover.phase2.argument_recipient_672_metric import ROLE_SWAP_VARIANTS, _auc
from goal_takeover.phase2.argument_recipient_672_runner import load_frozen_plan
from goal_takeover.storage.run_writer import sha256_file

OBJECTIVES = ("all_rows", "exposed_only")


def _exposed(row: dict[str, Any], candidate: str) -> bool:
    return candidate in (row["recipient_value_id"], row["reference_value_id"])


def readout_metrics(
    rows: list[dict[str, Any]],
    scores: dict[str, dict[str, float]],
    candidates: list[str],
) -> dict[str, Any]:
    """Role, presence and paired readouts from one pooled set of scores.

    ``role_swap`` uses only two-account rows; ``presence`` compares rows that
    expose the candidate against rows that omit it; ``paired_within_task``
    compares the same candidate across the matched role-swap pair of one task.
    """
    role = [row for row in rows if row["condition_variant"] in ROLE_SWAP_VARIANTS]
    by_candidate: dict[str, dict[str, float]] = {}
    for candidate in candidates:
        exposed = [row for row in role if _exposed(row, candidate)]
        absent_or_recipient = [
            row
            for row in rows
            if row["argument_present"][candidate] or not _exposed(row, candidate)
        ]
        by_candidate[candidate] = {
            "role_swap_auc": _auc(
                [row["argument_present"][candidate] for row in exposed],
                [scores[row["condition_id"]][candidate] for row in exposed],
            ),
            "presence_auc": _auc(
                [int(_exposed(row, candidate)) for row in rows],
                [scores[row["condition_id"]][candidate] for row in rows],
            ),
            "recipient_vs_absent_auc": _auc(
                [row["argument_present"][candidate] for row in absent_or_recipient],
                [scores[row["condition_id"]][candidate] for row in absent_or_recipient],
            ),
        }
    choice = [
        scores[row["condition_id"]][row["recipient_value_id"]]
        > scores[row["condition_id"]][row["reference_value_id"]]
        for row in role
    ]
    pairs: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in role:
        pairs[row["draft_task_id"]][row["condition_variant"]] = row
    paired = []
    for pair in pairs.values():
        if set(pair) != ROLE_SWAP_VARIANTS:
            raise ValueError("role-swap pair is incomplete")
        first, second = pair["rx_ref_y"], pair["ry_ref_x"]
        x, y = first["recipient_value_id"], first["reference_value_id"]
        if (second["recipient_value_id"], second["reference_value_id"]) != (y, x):
            raise ValueError("role-swap pair does not swap the same two accounts")
        paired.append(scores[first["condition_id"]][x] > scores[second["condition_id"]][x])
        paired.append(scores[second["condition_id"]][y] > scores[first["condition_id"]][y])
    per_series = {}
    for series in sorted({row["semantic_series_id"] for row in role}):
        labels, values = [], []
        for row in role:
            if row["semantic_series_id"] == series:
                for candidate in (row["recipient_value_id"], row["reference_value_id"]):
                    labels.append(row["argument_present"][candidate])
                    values.append(scores[row["condition_id"]][candidate])
        per_series[series] = _auc(labels, values)

    def mean(key: str) -> float:
        return sum(item[key] for item in by_candidate.values()) / len(by_candidate)

    return {
        "by_candidate": by_candidate,
        "role_swap_auc": mean("role_swap_auc"),
        "presence_auc": mean("presence_auc"),
        "recipient_vs_absent_auc": mean("recipient_vs_absent_auc"),
        "within_condition_choice_accuracy": sum(choice) / len(choice),
        "paired_within_task_accuracy": sum(paired) / len(paired),
        "per_series_role_swap_auc": per_series,
        "role_swap_row_count": len(role),
    }


def loso_scores(
    rows: list[dict[str, Any]],
    features: Any,
    candidates: list[str],
    *,
    objective: str,
    regularization_c: float,
    max_iter: int,
    seed: int,
    shuffle_seed: int | None = None,
    text: bool = False,
) -> dict[str, dict[str, float]]:
    """Pool leave-one-semantic-series-out decision values.

    Scaler/vectorizer and classifier are fitted on the remaining series only.
    ``shuffle_seed`` permutes labels within each task, as in the frozen
    random-label control. ``text=True`` treats ``features`` as prompt strings.
    """
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if objective not in OBJECTIVES:
        raise ValueError(f"unknown objective: {objective}")
    if len(features) != len(rows):
        raise ValueError("feature rows and condition rows differ")
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    out: dict[str, dict[str, float]] = {row["condition_id"]: {} for row in rows}
    for series in sorted({row["semantic_series_id"] for row in rows}):
        train = [i for i, row in enumerate(rows) if row["semantic_series_id"] != series]
        heldout = [i for i, row in enumerate(rows) if row["semantic_series_id"] == series]
        for candidate in candidates:
            use = [i for i in train if objective == "all_rows" or _exposed(rows[i], candidate)]
            labels = np.asarray([rows[i]["argument_present"][candidate] for i in use])
            if rng is not None:
                by_task: dict[str, list[int]] = defaultdict(list)
                for position, i in enumerate(use):
                    by_task[rows[i]["draft_task_id"]].append(position)
                for positions in by_task.values():
                    labels[positions] = rng.permutation(labels[positions])
            if len(set(labels.tolist())) != 2:
                raise ValueError(f"fold lacks a class: {series}/{candidate}")
            model = make_pipeline(
                TfidfVectorizer(analyzer="char", ngram_range=(2, 5)) if text else StandardScaler(),
                LogisticRegression(C=regularization_c, max_iter=max_iter, random_state=seed),
            )
            if text:
                model.fit([features[i] for i in use], labels)
                values = model.decision_function([features[i] for i in heldout])
            else:
                model.fit(features[use], labels)
                values = model.decision_function(features[heldout])
            for i, value in zip(heldout, values, strict=True):
                out[rows[i]["condition_id"]][candidate] = float(value)
    return out


def pair_geometry(rows: list[dict[str, Any]], features: Any) -> dict[str, float]:
    """Median distances after train standardization: role-swap pair, rx/ry, task centers."""
    import numpy as np
    from sklearn.preprocessing import StandardScaler

    standardized = StandardScaler().fit_transform(features)
    by_task: dict[str, dict[str, int]] = defaultdict(dict)
    for index, row in enumerate(rows):
        by_task[row["draft_task_id"]][row["condition_variant"]] = index
    tasks = list(by_task.values())
    within_role = [
        np.linalg.norm(standardized[t["rx_ref_y"]] - standardized[t["ry_ref_x"]]) for t in tasks
    ]
    within_single = [np.linalg.norm(standardized[t["rx"]] - standardized[t["ry"]]) for t in tasks]
    centers = np.stack([standardized[list(t.values())].mean(axis=0) for t in tasks])
    between = [
        np.linalg.norm(centers[i] - centers[j])
        for i in range(len(centers))
        for j in range(i + 1, len(centers))
    ]
    return {
        "median_role_swap_pair_distance": float(np.median(within_role)),
        "median_rx_vs_ry_distance": float(np.median(within_single)),
        "median_between_task_center_distance": float(np.median(between)),
    }


def publish(output_dir: Path, files: dict[str, bytes], *, kind: str) -> Path:
    """Atomically write a new immutable derived directory with a checksum manifest."""
    if output_dir.exists():
        raise FileExistsError(f"immutable derived output already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent))
    try:
        for name, content in files.items():
            (temporary / name).write_bytes(content)
        manifest = {
            "schema_version": 1,
            "kind": kind,
            "artifacts": {
                name: {"sha256": sha256_file(temporary / name), "bytes": len(content)}
                for name, content in files.items()
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        if output_dir.exists():
            raise FileExistsError(f"immutable derived output already exists: {output_dir}")
        os.rename(temporary, output_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return output_dir


def clean_commit(root: Path) -> str:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True, cwd=root
    ).stdout.strip()
    if dirty:
        raise ValueError("diagnostic requires a clean working tree")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=root
    ).stdout.strip()


def train_rows_and_run_ids(
    declaration: dict[str, Any], canonical_prefix: str
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Return train specs sorted by ID; validation conditions are never mapped."""
    indexed = list(enumerate(declaration["condition_specs"], start=1))
    rows = sorted(
        (row for _, row in indexed if row["split_candidate"] == "train"),
        key=lambda row: row["condition_id"],
    )
    run_ids = {
        row["condition_id"]: f"{canonical_prefix}-c{index:03d}"
        for index, row in indexed
        if row["split_candidate"] == "train"
    }
    if len(rows) != 480 or len({row["semantic_series_id"] for row in rows}) != 40:
        raise ValueError("expected 480 train conditions in 40 semantic series")
    return rows, run_ids


def run(analysis_config_path: Path) -> Path:
    import numpy as np

    analysis = json.loads(analysis_config_path.read_text(encoding="utf-8"))
    root = analysis_config_path.resolve().parents[2]
    spec = analysis["train_cv"]
    runtime_freeze = root / analysis["runtime_freeze"]
    config, declaration, split = load_frozen_plan(
        root / analysis["experiment_config"],
        runtime_freeze_override=Path(analysis["runtime_freeze"]),
        require_matching_head=False,
    )
    output = root / "artifacts/processed" / spec["output_id"]
    if output.exists():
        raise FileExistsError(f"immutable derived output already exists: {output}")
    commit = clean_commit(root)
    design_sha = sha256_file(root / config["references"]["design_freeze"])
    runtime_sha = sha256_file(runtime_freeze)
    rows, run_ids = train_rows_and_run_ids(declaration, analysis["canonical_run_prefix"])
    layers = [f"model.layers.{index}" for index in spec["layers"]]
    features, manifest_hashes = load_canonical_features(
        declaration,
        split,
        root / "artifacts/runs",
        run_ids,
        layers=layers,
        design_freeze_sha256=design_sha,
        runtime_freeze_sha256=runtime_sha,
    )
    order = [row["condition_id"] for row in rows]
    candidates = sorted(declaration["account_value_ids"])
    common = {
        "regularization_c": spec["regularization_c"],
        "max_iter": spec["max_iter"],
        "seed": spec["seed"],
    }
    by_id = {row.condition_id: row for row in features[layers[0]]}
    prompts = [by_id[cid].user_instruction for cid in order]
    report: dict[str, Any] = {"tfidf": {}, "layers": {}}
    for objective in spec["objectives"]:
        scores = loso_scores(rows, prompts, candidates, objective=objective, text=True, **common)
        report["tfidf"][objective] = readout_metrics(rows, scores, candidates)
    for layer in layers:
        by_id = {row.condition_id: row for row in features[layer]}
        matrix = np.stack([by_id[cid].vector for cid in order])
        entry: dict[str, Any] = {"geometry": pair_geometry(rows, matrix)}
        for objective in spec["objectives"]:
            scores = loso_scores(rows, matrix, candidates, objective=objective, **common)
            entry[objective] = readout_metrics(rows, scores, candidates)
            controls = []
            for repeat in range(spec["random_label_repeats"].get(objective, 0)):
                shuffled = loso_scores(
                    rows,
                    matrix,
                    candidates,
                    objective=objective,
                    shuffle_seed=spec["seed"] + repeat,
                    **common,
                )
                controls.append(readout_metrics(rows, shuffled, candidates)["role_swap_auc"])
            entry[objective]["random_label_role_swap_auc"] = controls
            print(layer, objective, round(entry[objective]["role_swap_auc"], 4), flush=True)
        report["layers"][layer] = entry
    payload = {
        "schema_version": 1,
        "research_result": "post_result_train_only_diagnostic",
        "provenance": {
            "git_commit": commit,
            "git_dirty": False,
            "analysis_config": analysis_config_path.resolve().relative_to(root).as_posix(),
            "analysis_config_sha256": sha256_file(analysis_config_path),
            "design_freeze_sha256": design_sha,
            "runtime_freeze_sha256": runtime_sha,
            "canonical_run_prefix": analysis["canonical_run_prefix"],
            "capture_manifest_sha256": manifest_hashes,
            "validation_rows_loaded": 0,
        },
        "settings": {
            **common,
            "objectives": spec["objectives"],
            "layers": layers,
            "random_label_repeats": spec["random_label_repeats"],
            "position_name": "Tend_assistant",
            "folds": "leave_one_semantic_series_out",
        },
        "report": report,
    }
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return publish(output, {"report.json": content.encode("utf-8")}, kind="train_readout_cv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis_config", type=Path)
    print(run(parser.parse_args().analysis_config))


if __name__ == "__main__":
    main()
