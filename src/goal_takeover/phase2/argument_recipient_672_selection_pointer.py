"""Train-only selection-pointer diagnostic for the 672 recipient collection.

Tests whether a candidate-free label, "the recipient is presented before the
reference account", is linearly readable at the saved ``Tend_assistant``
residual. This re-analyzes existing captures. Readable order does not show
selection, and a null does not exclude nonlinear or other pointer codes.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from goal_takeover.phase2.argument_recipient_672_features import load_canonical_features
from goal_takeover.phase2.argument_recipient_672_metric import ROLE_SWAP_VARIANTS
from goal_takeover.phase2.argument_recipient_672_runner import load_frozen_plan
from goal_takeover.phase2.argument_recipient_672_train_readout import (
    clean_commit,
    publish,
    train_rows_and_run_ids,
)
from goal_takeover.storage.run_writer import sha256_file

PROBES = ("logistic", "paired_dom")
FOLD_KEYS = {"family": "family_id", "series": "semantic_series_id"}


def presentation_text(row: dict[str, Any]) -> str:
    """Return the text exposing both accounts: user instruction or documents in read order."""
    if row["source_role"] == "user_instruction":
        return row["user_instruction"]
    if row["source_role"] == "tool_output_document":
        return "\n".join(document["content"] for document in row["documents"])
    raise ValueError(f"unknown source role: {row['source_role']}")


def recipient_first_label(row: dict[str, Any], accounts: dict[str, str]) -> int:
    """Condition-derived label; never uses generated calls or task outcomes."""
    text = presentation_text(row)
    recipient = accounts[row["recipient_value_id"]]
    reference = accounts[row["reference_value_id"]]
    if text.count(recipient) != 1 or text.count(reference) != 1:
        raise ValueError(f"{row['condition_id']}: accounts are not each presented once")
    return int(text.index(recipient) < text.index(reference))


def verify_labels_against_prefixes(
    rows: list[dict[str, Any]], prefix_texts: list[str], accounts: dict[str, str]
) -> None:
    """Require the declared order to hold in the exact serialized text the model received."""
    for index in pointer_indices(rows):
        row = rows[index]
        text = prefix_texts[index]
        recipient = accounts[row["recipient_value_id"]]
        reference = accounts[row["reference_value_id"]]
        if text.count(recipient) != 1 or text.count(reference) != 1:
            raise ValueError(f"{row['condition_id']}: prefix does not expose each account once")
        if int(text.index(recipient) < text.index(reference)) != recipient_first_label(
            row, accounts
        ):
            raise ValueError(f"{row['condition_id']}: prefix order differs from the declaration")


def pointer_indices(rows: list[dict[str, Any]]) -> list[int]:
    return [i for i, row in enumerate(rows) if row["condition_variant"] in ROLE_SWAP_VARIANTS]


def pair_index(rows: list[dict[str, Any]], labels: Any) -> list[tuple[int, int]]:
    """Return one (first, second) row index per task; labels must flip within each pair."""
    by_task: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_task[row["draft_task_id"]].append(index)
    pairs = []
    for task, indices in sorted(by_task.items()):
        if len(indices) != 2:
            raise ValueError(f"{task}: role-swap pair is incomplete")
        if int(labels[indices[0]]) == int(labels[indices[1]]):
            raise ValueError(f"{task}: label does not flip within the pair")
        pairs.append((indices[0], indices[1]))
    return pairs


def _folds(rows: list[dict[str, Any]], level: str) -> list[tuple[Any, Any]]:
    import numpy as np

    key = FOLD_KEYS[level]
    groups = np.asarray([row[key] for row in rows])
    tasks: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        tasks[row["draft_task_id"]].add(row[key])
    if any(len(values) != 1 for values in tasks.values()):
        raise ValueError("a task crosses the fold grouping")
    return [(np.flatnonzero(groups != g), np.flatnonzero(groups == g)) for g in np.unique(groups)]


def _logistic(c: float, max_iter: int, seed: int) -> Any:
    from sklearn.linear_model import LogisticRegression

    return LogisticRegression(C=c, max_iter=max_iter, random_state=seed)


def logistic_scores(
    rows: list[dict[str, Any]], features: Any, labels: Any, level: str, spec: dict[str, Any]
) -> Any:
    """Out-of-fold decision values; the scaler is fitted on the training side only."""
    import numpy as np
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    scores = np.full(len(rows), np.nan)
    for train, heldout in _folds(rows, level):
        model = make_pipeline(
            StandardScaler(),
            _logistic(spec["regularization_c"], spec["max_iter"], spec["seed"]),
        )
        model.fit(features[train], labels[train])
        scores[heldout] = model.decision_function(features[heldout])
    return scores


def paired_dom_scores(
    rows: list[dict[str, Any]], features: Any, labels: Any, level: str, pairs: list[tuple[int, int]]
) -> Any:
    """Project onto the mean within-pair difference learned on the training side only."""
    import numpy as np
    from sklearn.preprocessing import StandardScaler

    scores = np.full(len(rows), np.nan)
    for train, heldout in _folds(rows, level):
        members = set(train.tolist())
        scaler = StandardScaler().fit(features[train])
        standardized = scaler.transform(features)
        differences = []
        for first, second in pairs:
            if first in members:
                positive, negative = (first, second) if labels[first] == 1 else (second, first)
                differences.append(standardized[positive] - standardized[negative])
        scores[heldout] = standardized[heldout] @ np.mean(differences, axis=0)
    return scores


def text_scores(
    rows: list[dict[str, Any]], texts: list[str], labels: Any, level: str, spec: dict[str, Any]
) -> Any:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import make_pipeline

    scores = np.full(len(rows), np.nan)
    for train, heldout in _folds(rows, level):
        model = make_pipeline(
            TfidfVectorizer(analyzer="char", ngram_range=(2, 5)),
            _logistic(spec["regularization_c"], spec["max_iter"], spec["seed"]),
        )
        model.fit([texts[i] for i in train], labels[train])
        scores[heldout] = model.decision_function([texts[i] for i in heldout])
    return scores


def identity_features(rows: list[dict[str, Any]], candidates: list[str]) -> Any:
    import numpy as np

    return np.asarray([[float(row["recipient_value_id"] == c) for c in candidates] for row in rows])


def paired_accuracy(pairs: list[tuple[int, int]], labels: Any, scores: Any) -> float:
    """Share of pairs ranking the label-1 row above the label-0 row; ties count 0.5."""
    return sum(_pair_win(pair, labels, scores) for pair in pairs) / len(pairs)


def _pair_win(pair: tuple[int, int], labels: Any, scores: Any) -> float:
    first, second = pair
    positive, negative = (first, second) if labels[first] == 1 else (second, first)
    if labels[positive] != 1 or labels[negative] != 0:
        raise ValueError("pair labels do not flip")
    return float(scores[positive] > scores[negative]) + 0.5 * float(
        scores[positive] == scores[negative]
    )


def pooled_auc(labels: Any, scores: Any) -> float:
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(labels, scores))


def strata(
    rows: list[dict[str, Any]], pairs: list[tuple[int, int]], labels: Any, scores: Any
) -> dict[str, dict[str, float]]:
    """Paired accuracy by family, source role, recipient rule and exposure boundary."""
    output: dict[str, dict[str, float]] = {}
    keys = {
        "family": lambda row: row["family_id"],
        "source_role": lambda row: row["source_role"],
        "recipient_rule": lambda row: row["recipient_rule"],
        "boundary": lambda row: row["exposure"]["boundary"],
    }
    for name, key in keys.items():
        grouped: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for pair in pairs:
            grouped[key(rows[pair[0]])].append(pair)
        output[name] = {
            value: paired_accuracy(members, labels, scores)
            for value, members in sorted(grouped.items())
        }
    return output


def series_bootstrap(
    rows: list[dict[str, Any]],
    pairs: list[tuple[int, int]],
    labels: Any,
    scores: Any,
    *,
    repeats: int,
    seed: int,
) -> dict[str, list[float]]:
    """Percentile 95% intervals resampling semantic series, the highest usable unit here."""
    import numpy as np

    by_series: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for pair in pairs:
        by_series[rows[pair[0]]["semantic_series_id"]].append(pair)
    names = sorted(by_series)
    wins = {name: [_pair_win(pair, labels, scores) for pair in by_series[name]] for name in names}
    rng = np.random.default_rng(seed)
    accuracy, auc = [], []
    for _ in range(repeats):
        sample = rng.choice(len(names), size=len(names), replace=True)
        chosen = [names[i] for i in sample]
        values = [win for name in chosen for win in wins[name]]
        accuracy.append(sum(values) / len(values))
        indices = [i for name in chosen for pair in by_series[name] for i in pair]
        auc.append(pooled_auc(labels[indices], scores[indices]))
    return {
        "paired_accuracy": [float(v) for v in np.percentile(accuracy, [2.5, 97.5])],
        "pooled_auroc": [float(v) for v in np.percentile(auc, [2.5, 97.5])],
    }


def flip_by_series(rows: list[dict[str, Any]], labels: Any, rng: Any) -> Any:
    """Flip all labels of a randomly chosen half of series, preserving group structure."""
    import numpy as np

    names = sorted({row["semantic_series_id"] for row in rows})
    flips = dict(zip(names, rng.integers(0, 2, size=len(names)).tolist(), strict=True))
    return np.asarray(
        [
            int(label) ^ flips[row["semantic_series_id"]]
            for row, label in zip(rows, labels, strict=True)
        ]
    )


def _cell_scores(
    probe: str,
    rows: list[dict[str, Any]],
    matrix: Any,
    labels: Any,
    level: str,
    pairs: list[tuple[int, int]],
    spec: dict[str, Any],
) -> Any:
    if probe == "logistic":
        return logistic_scores(rows, matrix, labels, level, spec)
    if probe == "paired_dom":
        return paired_dom_scores(rows, matrix, labels, level, pairs)
    raise ValueError(f"unknown probe: {probe}")


def classify(
    positive_control_best: float,
    cells: dict[str, dict[str, Any]],
    baseline_best: float,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    """Apply the fixed R4 -> R1 -> R2 -> R3 rules to judged family-held-out cells."""
    if positive_control_best < thresholds["positive_control_auroc"]:
        return {"class": "R4", "qualifying_cells": []}
    qualifying = []
    for name, cell in cells.items():
        families_above = sum(value > 0.5 for value in cell["strata"]["family"].values())
        if (
            cell["paired_accuracy"] >= thresholds["paired_accuracy"]
            and cell["family_wise_p"] < thresholds["family_wise_alpha"]
            and cell["paired_accuracy"] >= baseline_best + thresholds["baseline_margin"]
            and families_above >= thresholds["families_above_chance"]
            and len(cell["strata"]["source_role"]) == 2
            and all(value > 0.5 for value in cell["strata"]["source_role"].values())
        ):
            qualifying.append(name)
    if qualifying:
        return {"class": "R1", "qualifying_cells": sorted(qualifying)}
    if any(cell["family_wise_p"] < thresholds["family_wise_alpha"] for cell in cells.values()):
        return {"class": "R2", "qualifying_cells": []}
    return {"class": "R3", "qualifying_cells": []}


def analyze(
    rows: list[dict[str, Any]],
    features: dict[int, Any],
    prefix_texts: list[str],
    token_counts: list[int],
    accounts: dict[str, str],
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Run probes, controls, null distribution and classification from aligned arrays."""
    import numpy as np

    indices = pointer_indices(rows)
    subset = [rows[i] for i in indices]
    labels = np.asarray([recipient_first_label(row, accounts) for row in subset])
    pairs = pair_index(subset, labels)
    texts = [prefix_texts[i] for i in indices]
    judged = spec["judged_layers"]
    layers = judged + spec["report_only_layers"]
    report: dict[str, Any] = {
        "pointer_rows": len(subset),
        "pointer_pairs": len(pairs),
        "cells": {},
        "series_held_out": {},
        "baselines": {},
    }
    # Baselines use the same folds and metric as the probes.
    length = np.asarray([[float(token_counts[i])] for i in indices])
    identity = identity_features(subset, sorted(accounts))
    for level in FOLD_KEYS:
        scores = {
            "tfidf": text_scores(subset, texts, labels, level, spec),
            "length": logistic_scores(subset, length, labels, level, spec),
            "identity": logistic_scores(subset, identity, labels, level, spec),
        }
        report["baselines"][level] = {
            name: {
                "paired_accuracy": paired_accuracy(pairs, labels, values),
                "pooled_auroc": pooled_auc(labels, values),
            }
            for name, values in scores.items()
        }
    baseline_best = max(v["paired_accuracy"] for v in report["baselines"]["family"].values())
    # Observed probe cells.
    matrices = {layer: features[layer][indices] for layer in layers}
    observed: dict[str, float] = {}
    for layer in layers:
        for probe in PROBES:
            name = f"layer{layer}/{probe}"
            values = _cell_scores(probe, subset, matrices[layer], labels, "family", pairs, spec)
            cell = {
                "layer": layer,
                "probe": probe,
                "judged": layer in judged,
                "paired_accuracy": paired_accuracy(pairs, labels, values),
                "pooled_auroc": pooled_auc(labels, values),
                "strata": strata(subset, pairs, labels, values),
                "bootstrap_95": series_bootstrap(
                    subset,
                    pairs,
                    labels,
                    values,
                    repeats=spec["bootstrap_repeats"],
                    seed=spec["seed"],
                ),
            }
            report["cells"][name] = cell
            if layer in judged:
                observed[name] = cell["paired_accuracy"]
            series_values = _cell_scores(
                probe, subset, matrices[layer], labels, "series", pairs, spec
            )
            report["series_held_out"][name] = {
                "paired_accuracy": paired_accuracy(pairs, labels, series_values),
                "pooled_auroc": pooled_auc(labels, series_values),
            }
    # Series-level sign flips; the maximum across judged cells controls family-wise error.
    rng = np.random.default_rng(spec["seed"])
    null_maxima = []
    for _ in range(spec["permutation_repeats"]):
        flipped = flip_by_series(subset, labels, rng)
        null_maxima.append(
            max(
                paired_accuracy(
                    pairs,
                    flipped,
                    _cell_scores(probe, subset, matrices[layer], flipped, "family", pairs, spec),
                )
                for layer in judged
                for probe in PROBES
            )
        )
    report["null_maxima"] = null_maxima
    for name, value in observed.items():
        exceed = sum(maximum >= value for maximum in null_maxima)
        report["cells"][name]["family_wise_p"] = (1 + exceed) / (1 + len(null_maxima))
    # Positive control: an obvious structural label, on all train rows.
    source = np.asarray([int(row["source_role"] == "tool_output_document") for row in rows])
    report["positive_control_auroc"] = {
        str(layer): pooled_auc(
            source, logistic_scores(rows, features[layer], source, "family", spec)
        )
        for layer in layers
    }
    # Specificity control: unrelated order information in U tasks, compared by pooled AUROC.
    user = [i for i, row in enumerate(subset) if row["source_role"] == "user_instruction"]
    user_rows = [subset[i] for i in user]
    block = np.asarray([int(row["account_block_position"] == "before_task") for row in user_rows])
    specificity = {}
    for layer in layers:
        control = logistic_scores(user_rows, matrices[layer][user], block, "family", spec)
        main = logistic_scores(user_rows, matrices[layer][user], labels[user], "family", spec)
        control_auc = pooled_auc(block, control)
        main_auc = pooled_auc(labels[user], main)
        specificity[str(layer)] = {
            "control_auroc": control_auc,
            "recipient_first_user_auroc": main_auc,
            "comparable_to_control": control_auc
            >= main_auc - spec["thresholds"]["specificity_margin"],
        }
    report["specificity_control"] = specificity
    judged_cells = {k: v for k, v in report["cells"].items() if v["judged"]}
    report["classification"] = classify(
        max(report["positive_control_auroc"][str(layer)] for layer in judged),
        judged_cells,
        baseline_best,
        spec["thresholds"],
    )
    report["baseline_best_family_paired_accuracy"] = baseline_best
    return report


def with_block_position(
    rows: list[dict[str, Any]], tasks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach each task's declared account-block position without altering the source rows."""
    positions = {task["draft_task_id"]: task["account_block_position"] for task in tasks}
    return [{**row, "account_block_position": positions[row["draft_task_id"]]} for row in rows]


def run(analysis_config_path: Path) -> Path:
    import numpy as np

    analysis = json.loads(analysis_config_path.read_text(encoding="utf-8"))
    root = analysis_config_path.resolve().parents[2]
    spec = analysis["analysis"]
    runtime_freeze = root / analysis["runtime_freeze"]
    config, declaration, split = load_frozen_plan(
        root / analysis["experiment_config"],
        runtime_freeze_override=Path(analysis["runtime_freeze"]),
        require_matching_head=False,
    )
    output = root / "artifacts/processed" / analysis["output_id"]
    if output.exists():
        raise FileExistsError(f"immutable derived output already exists: {output}")
    commit = clean_commit(root)
    design_sha = sha256_file(root / config["references"]["design_freeze"])
    runtime_sha = sha256_file(runtime_freeze)
    rows, run_ids = train_rows_and_run_ids(declaration, analysis["canonical_run_prefix"])
    rows = with_block_position(rows, declaration["task_specs"])
    layer_ids = spec["judged_layers"] + spec["report_only_layers"]
    names = {layer: f"model.layers.{layer}" for layer in layer_ids}
    captured, manifest_hashes = load_canonical_features(
        declaration,
        split,
        root / "artifacts/runs",
        run_ids,
        layers=list(names.values()),
        design_freeze_sha256=design_sha,
        runtime_freeze_sha256=runtime_sha,
    )
    order = [row["condition_id"] for row in rows]
    features = {}
    for layer, name in names.items():
        by_id = {row.condition_id: row for row in captured[name]}
        features[layer] = np.stack([by_id[cid].vector for cid in order])
    first = {row.condition_id: row for row in captured[names[layer_ids[0]]]}
    prefix_texts = [first[cid].user_instruction for cid in order]
    verify_labels_against_prefixes(rows, prefix_texts, declaration["account_value_ids"])
    report = analyze(
        rows,
        features,
        prefix_texts,
        [first[cid].token_index + 1 for cid in order],
        declaration["account_value_ids"],
        spec,
    )
    payload = {
        "schema_version": 1,
        "research_result": "post_result_train_only_diagnostic",
        "provenance": {
            "rdr": "RDR-2026-11-06-01",
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
        "settings": {**spec, "position_name": "Tend_assistant"},
        "report": report,
    }
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return publish(output, {"report.json": content.encode("utf-8")}, kind="selection_pointer")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis_config", type=Path)
    print(run(parser.parse_args().analysis_config))


if __name__ == "__main__":
    main()
