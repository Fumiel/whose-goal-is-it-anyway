"""Formal, post-result local-wording baseline; no GPU, model, or validation bundles."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

for _variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_variable, "1")

from goal_takeover.phase2.activation_patching import (  # noqa: E402
    identity,
    load_plan,
    read_config,
    require_train,
)
from goal_takeover.phase2.argument_recipient_672_selection_pointer import (  # noqa: E402
    _folds,
    paired_accuracy,
    presentation_text,
    text_scores,
)
from goal_takeover.phase2.argument_recipient_672_train_readout import publish  # noqa: E402
from goal_takeover.phase2.position_sweep_positions import presentation_order  # noqa: E402
from goal_takeover.storage.run_writer import canonical_json_bytes  # noqa: E402


def local_windows(rows: list[dict], accounts: dict, position: str, characters: int) -> tuple:
    require_train(rows)
    if position not in ("A1", "A2") or characters <= 0:
        raise ValueError("invalid local window position/length")
    texts, ranges = [], []
    for row in rows:
        text = presentation_text(row)
        account = presentation_order(row, accounts)[("A1", "A2").index(position)]
        end = text.index(account)
        start = max(0, end - characters)
        texts.append(text[start:end])
        ranges.append(
            {
                "condition_id": row["condition_id"],
                "character_start": start,
                "character_end": end,
                "account_character_start": end,
            }
        )
    return texts, ranges


def evaluate_local(rows: list[dict], accounts: dict, labels: list, pairs: list, spec: dict) -> dict:
    import numpy as np

    require_train(rows)
    output = {}
    for position in spec["positions"]:
        for characters in spec["window_characters"]:
            texts, ranges = local_windows(rows, accounts, position, characters)
            levels = {}
            for level in ("family", "series"):
                scores = text_scores(rows, texts, np.asarray(labels), level, spec)
                if not np.isfinite(scores).all():
                    raise ValueError("missing local-wording predictions")
                folds = []
                for _, heldout in _folds(rows, level):
                    members = set(heldout.tolist())
                    selected = [pair for pair in pairs if pair[0] in members]
                    folds.append(
                        {
                            "held_out_group": rows[int(heldout[0])][
                                "family_id" if level == "family" else "semantic_series_id"
                            ],
                            "pair_count": len(selected),
                            "paired_accuracy": paired_accuracy(selected, labels, scores),
                        }
                    )
                levels[level] = {
                    "paired_accuracy": paired_accuracy(pairs, labels, scores),
                    "folds": folds,
                    "condition_scores": {
                        row["condition_id"]: float(score)
                        for row, score in zip(rows, scores, strict=True)
                    },
                }
            output[f"{position}/N{characters}"] = {"window_ranges": ranges, "evaluations": levels}
    return output


def run(config_path: Path) -> Path:
    root, settings = read_config(config_path)
    target = root / "artifacts/processed" / settings["local_wording"]["output_id"]
    if target.exists():
        raise FileExistsError(target)
    plan = load_plan(config_path)
    spec = settings["local_wording"]
    if spec["ngram_range"] != [2, 5]:
        raise ValueError("existing text_scores requires the frozen char 2-5 grams")
    cells = evaluate_local(plan["rows"], plan["accounts"], plan["labels"], plan["pairs"], spec)
    report = {
        "provenance": {
            **identity(plan),
            "research_result": "formal_record_of_post_result_informal_check",
        },
        "cells": cells,
        "changes_prior_classifications": False,
    }
    return publish(
        target, {"report.json": canonical_json_bytes(report)}, kind="local_wording_baseline"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run",))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    print(run(args.config))


if __name__ == "__main__":
    main()
