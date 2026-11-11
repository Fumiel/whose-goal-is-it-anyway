"""Train-only, globally corrected position sweep. Observation does not imply choice."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Set before importing any numerical libraries, including transitive imports.
for _variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_variable, "1")

from goal_takeover.phase2.argument_recipient_672_selection_pointer import (  # noqa: E402
    FOLD_KEYS,
    PROBES,
    _cell_scores,
    _folds,
    classify,
    flip_by_series,
    identity_features,
    logistic_scores,
    pair_index,
    paired_accuracy,
    pooled_auc,
    recipient_first_label,
    series_bootstrap,
    strata,
    text_scores,
)
from goal_takeover.phase2.argument_recipient_672_train_readout import (  # noqa: E402
    clean_commit,
    publish,
)
from goal_takeover.phase2.position_sweep_capture import verify_sweep_freeze  # noqa: E402
from goal_takeover.phase2.position_sweep_positions import (  # noqa: E402
    POSITIONS,
    canonical_prefix,
    context,
    presentation_order,
    safe_path,
    span_last_token,
    verified_json,
    verify_manifest,
)
from goal_takeover.storage.run_writer import (  # noqa: E402
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)

STAGE_ORDER = ["span", "pre_generation", "call_prefix"]


def stage_class(position_classes: dict, members: list[str]) -> str:
    values = [position_classes[p] for p in members]
    return "R1" if "R1" in values else "R2" if "R2" in values else "R3"


def map_hypothesis(position_classes: dict, stages: dict, r1_cells: dict | None = None) -> dict:
    if any(value == "R4" for value in position_classes.values()):
        return {"rule": 0, "mapping": "deferred_procedure_problem"}
    if all(value == "R3" for value in position_classes.values()):
        return {"rule": 1, "mapping": "none_detected"}
    classes = {s: stage_class(position_classes, stages[s]) for s in STAGE_ORDER}
    first = next((s for s in STAGE_ORDER if classes[s] == "R1"), None)
    if first is None:
        return {"rule": 6, "mapping": "unmapped_pattern", "stage_classes": classes}
    if any(classes[s] == "R3" for s in STAGE_ORDER[STAGE_ORDER.index(first) + 1 :]):
        return {"rule": 2, "mapping": "signal_disappears", "stage_classes": classes}
    number = {"span": 3, "pre_generation": 4, "call_prefix": 5}[first]
    result = {"rule": number, "mapping": f"H{number - 2}_consistent", "stage_classes": classes}
    if first == "call_prefix":
        result["r1_only_at_G"] = position_classes["S"] != "R1" and position_classes["G"] == "R1"
    return result


def global_null(
    rows: list[dict], features: dict, labels, pairs: list, cells: dict, spec: dict
) -> list[float]:
    import numpy as np

    rng = np.random.default_rng(spec["seed"])
    null = []
    judged = [v for v in cells.values() if v["judged"]]
    for repeat in range(spec["permutation_repeats"]):
        flipped = flip_by_series(rows, labels, rng)
        null.append(
            max(
                paired_accuracy(
                    pairs,
                    flipped,
                    _cell_scores(
                        cell["probe"],
                        rows,
                        features[cell["position"]][cell["layer"]],
                        flipped,
                        "family",
                        pairs,
                        spec,
                    ),
                )
                for cell in judged
            )
        )
        print(
            f"position sweep permutation {repeat + 1}/{spec['permutation_repeats']}",
            file=sys.stderr,
            flush=True,
        )
    return null


def logit_comparison(probe_accuracy: float, logit_accuracy: float) -> dict:
    return {
        "explained_by_logit_range": probe_accuracy <= logit_accuracy,
        "description": "同位置ロジットの精度以下"
        if probe_accuracy <= logit_accuracy
        else "同位置ロジットの精度を上回る",
        "interpretation": "accuracy_comparison_only",
    }


def logit_metrics(rows: list[dict], logprobs: list[dict], accounts: dict, labels, pairs) -> dict:
    import numpy as np

    inverse = {value: key for key, value in accounts.items()}
    scores = []
    for row, probabilities in zip(rows, logprobs, strict=True):
        first, second = presentation_order(row, accounts)
        values = probabilities["G"]["candidate_digits"]
        scores.append(values[inverse[first]] - values[inverse[second]])
    values = np.asarray(scores)
    if not np.isfinite(values).all():
        raise ValueError("nonfinite logit score")
    return {
        "score_orientation": "first_presented_minus_second_presented",
        "paired_accuracy": paired_accuracy(pairs, labels, values),
        "pooled_auroc": pooled_auc(labels, values),
        "strata": strata(rows, pairs, labels, values),
    }


def validate_inputs(
    rows: list[dict],
    features: dict,
    texts: list[str],
    counts: list[int],
    positions: list[dict],
    logprobs: list[dict],
    spec: dict,
) -> None:
    import numpy as np

    count = len(rows)
    if not count or any(row.get("split_candidate") != "train" for row in rows):
        raise ValueError("only train rows are allowed")
    if len({r["condition_id"] for r in rows}) != count or any(
        len(values) != count for values in (texts, counts, positions, logprobs)
    ):
        raise ValueError("duplicate or unaligned input rows")
    for level in FOLD_KEYS:
        _folds(rows, level)
    # Series must remain wholly inside a family as well as pairs inside a fold.
    for series in {r["semantic_series_id"] for r in rows}:
        if len({r["family_id"] for r in rows if r["semantic_series_id"] == series}) != 1:
            raise ValueError("a semantic series crosses family folds")
    shape = None
    for p in POSITIONS:
        for layer in spec["report_layers"]:
            matrix = features[p][layer]
            if matrix.ndim != 2 or matrix.shape[0] != count or not np.isfinite(matrix).all():
                raise ValueError("missing, nonfinite or unaligned residual features")
            shape = shape or matrix.shape
            if matrix.shape != shape:
                raise ValueError("residual hidden sizes differ")


def analyze(
    rows: list[dict],
    features: dict,
    prefix_texts: list[str],
    token_counts: list[int],
    positions: list[dict],
    logprobs: list[dict],
    accounts: dict,
    spec: dict,
) -> dict:
    import numpy as np

    validate_inputs(rows, features, prefix_texts, token_counts, positions, logprobs, spec)
    labels = np.asarray([recipient_first_label(row, accounts) for row in rows])
    pairs = pair_index(rows, labels)
    report = {
        "pointer_rows": len(rows),
        "pointer_pairs": len(pairs),
        "cells": {},
        "baselines": {},
        "series_held_out": {},
        "validation_rows_loaded": 0,
    }
    length = np.asarray(token_counts, dtype=float)[:, None]
    positional = np.asarray(
        [
            [p["positions"][name]["token_index"] for name in ("A1", "A2")] + [n]
            for p, n in zip(positions, token_counts, strict=True)
        ]
    )
    identity = identity_features(rows, sorted(accounts))
    for level in FOLD_KEYS:
        scores = {
            "tfidf": text_scores(rows, prefix_texts, labels, level, spec),
            **{
                name: logistic_scores(rows, matrix, labels, level, spec)
                for name, matrix in (
                    ("length", length),
                    ("identity", identity),
                    ("position", positional),
                )
            },
        }
        report["baselines"][level] = {
            name: {
                "paired_accuracy": paired_accuracy(pairs, labels, values),
                "pooled_auroc": pooled_auc(labels, values),
            }
            for name, values in scores.items()
        }
    best = max(v["paired_accuracy"] for v in report["baselines"]["family"].values())
    report["baseline_best_family_paired_accuracy"] = best
    for p in POSITIONS:
        for layer in spec["report_layers"]:
            for probe in PROBES:
                name = f"{p}/layer{layer}/{probe}"
                matrix = features[p][layer]
                values = _cell_scores(probe, rows, matrix, labels, "family", pairs, spec)
                cell = {
                    "position": p,
                    "layer": layer,
                    "probe": probe,
                    "judged": p not in spec["report_only_positions"]
                    and layer in spec["judged_layers"].get(p, []),
                    "paired_accuracy": paired_accuracy(pairs, labels, values),
                    "pooled_auroc": pooled_auc(labels, values),
                    "strata": strata(rows, pairs, labels, values),
                    "bootstrap_95": series_bootstrap(
                        rows,
                        pairs,
                        labels,
                        values,
                        repeats=spec["bootstrap_repeats"],
                        seed=spec["seed"],
                    ),
                }
                report["cells"][name] = cell
                series = _cell_scores(probe, rows, matrix, labels, "series", pairs, spec)
                report["series_held_out"][name] = {
                    "paired_accuracy": paired_accuracy(pairs, labels, series),
                    "pooled_auroc": pooled_auc(labels, series),
                }
        print(f"position sweep observed {p}", file=sys.stderr, flush=True)
    judged_count = sum(c["judged"] for c in report["cells"].values())
    expected = 2 * sum(
        len(v) for k, v in spec["judged_layers"].items() if k not in spec["report_only_positions"]
    )
    if judged_count != expected or expected <= 0:
        raise ValueError("judged cell grid differs")
    # Production config is checked against the 42-cell grid by the input loader.
    report["judged_cell_count"] = judged_count
    null = global_null(rows, features, labels, pairs, report["cells"], spec)
    report["null_maxima"] = null
    for cell in report["cells"].values():
        if cell["judged"]:
            cell["family_wise_p"] = (1 + sum(v >= cell["paired_accuracy"] for v in null)) / (
                1 + len(null)
            )
    source = np.asarray([int(row["source_role"] == "tool_output_document") for row in rows])
    user = [i for i, row in enumerate(rows) if row["source_role"] == "user_instruction"]
    user_rows = [rows[i] for i in user]
    block = np.asarray([int(r["account_block_position"] == "before_task") for r in user_rows])
    positives, specificity, classes = {}, {}, {}
    for p in POSITIONS:
        positives[p], specificity[p] = {}, {}
        for layer in spec["report_layers"]:
            matrix = features[p][layer]
            positives[p][str(layer)] = pooled_auc(
                source, logistic_scores(rows, matrix, source, "family", spec)
            )
            control = logistic_scores(user_rows, matrix[user], block, "family", spec)
            main = logistic_scores(user_rows, matrix[user], labels[user], "family", spec)
            control_auc, main_auc = pooled_auc(block, control), pooled_auc(labels[user], main)
            specificity[p][str(layer)] = {
                "control_auroc": control_auc,
                "recipient_first_user_auroc": main_auc,
                "comparable_to_control": control_auc
                >= main_auc - spec["thresholds"]["specificity_margin"],
            }
        if p not in spec["report_only_positions"]:
            classes[p] = classify(
                max(positives[p][str(layer)] for layer in spec["judged_layers"][p]),
                {n: c for n, c in report["cells"].items() if c["position"] == p and c["judged"]},
                best,
                spec["thresholds"],
            )
    logits = logit_metrics(rows, logprobs, accounts, labels, pairs)
    for cell in report["cells"].values():
        if cell["position"] == "G" and cell["judged"]:
            cell.update(logit_comparison(cell["paired_accuracy"], logits["paired_accuracy"]))
    gb = np.asarray([v["S"]["gb_log_probability"] for v in logprobs])
    if not np.isfinite(gb).all():
        raise ValueError("nonfinite GB log probabilities")
    report.update(
        positive_control_auroc=positives,
        specificity_control=specificity,
        same_position_logits={
            "G": logits,
            "S": {
                "gb_log_probability_min": float(gb.min()),
                "gb_log_probability_median": float(np.median(gb)),
            },
        },
        position_classifications=classes,
        hypothesis_mapping=map_hypothesis(
            {p: v["class"] for p, v in classes.items()}, spec["stages"]
        ),
    )
    return report


def load_inputs(config_path: Path, runtime_freeze: Path) -> tuple:
    import numpy as np
    import torch
    from safetensors.torch import load_file

    root, spec, config, rows, run_ids, accounts = context(config_path, runtime_freeze)
    freeze = verify_sweep_freeze(root, config_path, spec, config, runtime_freeze)
    if clean_commit(root) == freeze["git_commit"]:
        raise ValueError("analysis requires a different commit from capture")
    if sum(map(len, spec["analysis"]["judged_layers"].values())) * len(PROBES) != 42:
        raise ValueError("production analysis requires 42 judged cells")
    features = {p: {layer: [] for layer in spec["analysis"]["report_layers"]} for p in POSITIONS}
    texts, counts, positions, probabilities = [], [], [], []
    manifests, canonical_manifests = {}, {}
    runtime_sha = sha256_file(root / runtime_freeze)
    dimensions = None
    for row in rows:
        canonical_id = run_ids[row["condition_id"]]
        prefix, condition, _ = canonical_prefix(root, canonical_id, row, spec)
        run_id = spec["capture"]["run_id_prefix"] + "-" + canonical_id.rsplit("-", 1)[1]
        bundle = root / "artifacts/runs" / run_id
        manifest = verify_manifest(bundle)
        run = verified_json(bundle, manifest, "run.json")
        original_manifest = sha256_file(root / "artifacts/runs" / canonical_id / "manifest.json")
        if (
            run["status"] != "completed"
            or run["runtime_freeze_sha256"] != runtime_sha
            or run["run_id"] != run_id
            or run["condition_id"] != row["condition_id"]
            or run["canonical_run_id"] != canonical_id
            or run["split"] != "train"
            or run["git_dirty"] is not False
            or run["git_commit"] != freeze["git_commit"]
            or run["canonical_manifest_sha256"] != original_manifest
            or run["analysis_config_sha256"] != freeze["analysis_config_sha256"]
            or run["spec_sha256"] != freeze["spec_sha256"]
            or verified_json(bundle, manifest, "condition.json") != condition
        ):
            raise ValueError("sweep bundle condition/provenance differs")
        inputs = verified_json(bundle, manifest, "input.json")
        p = verified_json(bundle, manifest, "positions.json")
        ids = inputs["token_ids"]
        if (
            inputs["canonical_prefix_sha256"]
            != sha256_file(root / "artifacts/runs" / canonical_id / "prefix.json")
            or inputs["token_ids_sha256"] != sha256_bytes(canonical_json_bytes(ids))
            or ids[: len(prefix["token_ids"])] != prefix["token_ids"]
            or p["position_order"] != list(POSITIONS)
            or p["input_token_count"] != len(ids)
            or any(
                ids[p["positions"][name]["token_index"]] != p["positions"][name]["token_id"]
                for name in POSITIONS
            )
        ):
            raise ValueError("sweep input/positions differ")
        first, second = presentation_order(row, accounts)
        for name, account in (("A1", first), ("A2", second)):
            if p["positions"][name]["account"] != account or p["positions"][name][
                "token_index"
            ] != span_last_token(prefix, account):
                raise ValueError("span position differs from canonical presentation")
        if [p["positions"][name]["token_index"] for name in ("T", "S", "G", "D")] != [
            len(prefix["token_ids"]) - 1,
            len(ids) - 3,
            len(ids) - 2,
            len(ids) - 1,
        ]:
            raise ValueError("T/S/G/D indices differ")
        tensors = load_file(str(bundle / "residual.safetensors"))
        current_dimensions = run["model_dimensions"]
        if dimensions is not None and current_dimensions != dimensions:
            raise ValueError("capture model dimensions differ across bundles")
        dimensions = current_dimensions
        if dimensions["num_hidden_layers"] != max(spec["analysis"]["report_layers"]) + 1:
            raise ValueError("capture layer count differs from frozen report grid")
        if set(tensors) != {f"model.layers.{i}" for i in range(dimensions["num_hidden_layers"])}:
            raise ValueError("expected all 36 residual layers")
        for tensor in tensors.values():
            if (
                tensor.shape != (1, len(POSITIONS), dimensions["hidden_size"])
                or tensor.dtype != torch.bfloat16
                or not torch.isfinite(tensor).all()
            ):
                raise ValueError("sweep residual shape/dtype/finite check failed")
        for index, name in enumerate(POSITIONS):
            for layer in features[name]:
                features[name][layer].append(
                    tensors[f"model.layers.{layer}"][0, index].float().numpy()
                )
        texts.append(prefix["text"])
        counts.append(len(prefix["token_ids"]))
        positions.append(p)
        probabilities.append(verified_json(bundle, manifest, "logprobs.json"))
        manifests[run_id] = sha256_file(bundle / "manifest.json")
        canonical_manifests[canonical_id] = original_manifest
    features = {
        p: {layer: np.stack(v).astype(np.float32) for layer, v in layers.items()}
        for p, layers in features.items()
    }
    provenance = {
        "git_commit": clean_commit(root),
        "git_dirty": False,
        "analysis_config_sha256": freeze["analysis_config_sha256"],
        "spec_sha256": freeze["spec_sha256"],
        "runtime_freeze_sha256": runtime_sha,
        "capture_manifest_sha256": manifests,
        "canonical_manifest_sha256": canonical_manifests,
        "validation_rows_loaded": 0,
        "research_result": "post_result_train_only_diagnostic",
        "rdr": "RDR-2026-11-06-01",
    }
    return root, spec, rows, features, texts, counts, positions, probabilities, accounts, provenance


def run(config_path: Path, runtime_freeze: Path) -> Path:
    # Fail before expensive fitting if the immutable output has already been published.
    from goal_takeover.phase2.position_sweep_positions import read_config

    root, spec = read_config(config_path)
    output = safe_path(root, "artifacts/processed/" + spec["analysis"]["output_id"])
    if output.exists():
        raise FileExistsError(f"immutable derived output already exists: {output}")
    root, spec, rows, features, texts, counts, positions, probabilities, accounts, provenance = (
        load_inputs(config_path, runtime_freeze)
    )
    report = analyze(
        rows, features, texts, counts, positions, probabilities, accounts, spec["analysis"]
    )
    return publish(
        output,
        {
            "report.json": canonical_json_bytes(
                {
                    "schema_version": 1,
                    "provenance": provenance,
                    "settings": spec["analysis"],
                    "report": report,
                }
            )
        },
        kind="position_sweep",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--runtime-freeze", type=Path, required=True)
    args = parser.parse_args()
    print(run(args.config, args.runtime_freeze))


if __name__ == "__main__":
    main()
