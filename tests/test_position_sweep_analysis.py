"""Synthetic signal recovery and globally corrected interpretation (spec 4-8/12)."""

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_position_sweep_positions import ACCOUNTS, CONFIG

from goal_takeover.phase2.argument_recipient_672_selection_pointer import pair_index
from goal_takeover.phase2.position_sweep_analysis import (
    analyze,
    global_null,
    logit_comparison,
    logit_metrics,
    map_hypothesis,
    validate_inputs,
)
from goal_takeover.phase2.position_sweep_positions import POSITIONS

STAGES = CONFIG["analysis"]["stages"]


class MappingTest(unittest.TestCase):
    def test_all_seven_rules_and_G_only(self):
        examples = [
            (["R4", "R3", "R3", "R3", "R3"], 0),
            (["R3"] * 5, 1),
            (["R3", "R1", "R3", "R1", "R1"], 2),
            (["R1", "R3", "R1", "R1", "R3"], 3),
            (["R3", "R3", "R1", "R1", "R3"], 4),
            (["R3", "R3", "R3", "R3", "R1"], 5),
            (["R2", "R3", "R3", "R3", "R3"], 6),
            (["R3", "R3", "R1", "R3", "R3"], 2),
        ]
        for values, rule in examples:
            result = map_hypothesis(dict(zip(POSITIONS[:5], values, strict=True)), STAGES)
            self.assertEqual(result["rule"], rule)
            if rule == 5:
                self.assertTrue(result["r1_only_at_G"])

    def test_logit_range_includes_equality_and_has_correct_direction(self):
        self.assertTrue(logit_comparison(0.8, 0.8)["explained_by_logit_range"])
        self.assertTrue(logit_comparison(0.7, 0.8)["explained_by_logit_range"])
        self.assertFalse(logit_comparison(0.9, 0.8)["explained_by_logit_range"])


@unittest.skipUnless(
    importlib.util.find_spec("numpy") and importlib.util.find_spec("sklearn"),
    "research extras unavailable",
)
class NumericalTest(unittest.TestCase):
    @staticmethod
    def data(signals=("T",), positional=False):
        import numpy as np

        rows, texts, counts, positions, probabilities, matrix = [], [], [], [], [], []
        for family in "ABCDEF":
            for series in range(4):
                source = "user_instruction" if series < 2 else "tool_output_document"
                for task in range(2):
                    first, second = ("x", "y") if task == 0 else ("y", "x")
                    for label in (1, 0):
                        recipient, reference = (first, second) if label else (second, first)
                        text = f"{ACCOUNTS[first]} {ACCOUNTS[second]}"
                        row = {
                            "condition_id": f"{family}{series}{task}{label}",
                            "draft_task_id": f"{family}{series}{task}",
                            "semantic_series_id": f"{family}{series}",
                            "family_id": family,
                            "split_candidate": "train",
                            "source_role": source,
                            "user_instruction": text,
                            "documents": [{"content": text}],
                            "condition_variant": "rx_ref_y" if label else "ry_ref_x",
                            "recipient_rule": "synthetic",
                            "exposure": {"boundary": source},
                            "recipient_value_id": recipient,
                            "reference_value_id": reference,
                            "account_block_position": "before_task" if task == 0 else "after_task",
                        }
                        rows.append(row)
                        matrix.append([label * 2 - 1, int(series >= 2) * 2 - 1, task * 2 - 1])
                        texts.append("identical synthetic text")
                        counts.append(100)
                        positions.append(
                            {
                                "positions": {
                                    p: {"token_index": 20 * label if positional else 10}
                                    for p in ("A1", "A2")
                                }
                            }
                        )
                        probabilities.append(
                            {
                                "G": {
                                    "candidate_digits": {
                                        key: -1.0 if key == recipient else -3.0 for key in ACCOUNTS
                                    }
                                },
                                "S": {"gb_log_probability": -0.1},
                            }
                        )
        matrix = np.asarray(matrix, dtype=float)
        features = {p: {24: matrix.copy()} for p in POSITIONS}
        for p in POSITIONS:
            if p not in signals:
                features[p][24][:, 0] = 0
        spec = {
            **CONFIG["analysis"],
            "report_layers": [24],
            "judged_layers": {p: [24] for p in POSITIONS[:5]},
            "permutation_repeats": 26,
            "bootstrap_repeats": 2,
        }
        return rows, features, texts, counts, positions, probabilities, ACCOUNTS, spec

    def test_T_only_signal_and_reproducibility(self):
        data = self.data()
        result = analyze(*data)
        self.assertEqual(result, analyze(*data))
        classes = {p: v["class"] for p, v in result["position_classifications"].items()}
        self.assertEqual(classes, {"A1": "R3", "A2": "R3", "T": "R1", "S": "R3", "G": "R3"})
        self.assertEqual(result["hypothesis_mapping"]["rule"], 2)
        self.assertEqual(result["same_position_logits"]["G"]["paired_accuracy"], 1.0)
        self.assertEqual(result["validation_rows_loaded"], 0)
        data_with_later_signal = self.data(signals=("T", "G"))
        self.assertEqual(analyze(*data_with_later_signal)["hypothesis_mapping"]["rule"], 4)

    def test_position_baseline_raises_R1_requirement(self):
        result = analyze(*self.data(positional=True))
        self.assertEqual(result["baselines"]["family"]["position"]["paired_accuracy"], 1.0)
        self.assertEqual(result["position_classifications"]["T"]["class"], "R2")

    def test_label_blind_logit_orientation_and_ties(self):
        import numpy as np

        rows, _, _, _, _, probabilities, accounts, _ = self.data()
        labels = np.asarray([1, 0] * (len(rows) // 2))
        pairs = pair_index(rows, labels)
        self.assertEqual(
            logit_metrics(rows, probabilities, accounts, labels, pairs)["paired_accuracy"], 1.0
        )
        tied = copy.deepcopy(probabilities)
        for item in tied:
            item["G"]["candidate_digits"] = dict.fromkeys(accounts, -2.0)
        result = logit_metrics(rows, tied, accounts, labels, pairs)
        self.assertEqual(result["paired_accuracy"], 0.5)
        self.assertEqual(result["pooled_auroc"], 0.5)

    def test_null_maximum_covers_all_positions_and_cells(self):
        import numpy as np

        data = self.data()
        rows, features, *_, spec = data
        labels = np.asarray([1, 0] * (len(rows) // 2))
        pairs = pair_index(rows, labels)
        cells = {
            "low": {"position": "A1", "layer": 24, "probe": "logistic", "judged": True},
            "high": {"position": "T", "layer": 24, "probe": "logistic", "judged": True},
            "report": {"position": "D", "layer": 24, "probe": "logistic", "judged": False},
        }

        def scores(probe, rows, matrix, flipped, *args):
            return flipped if matrix is features["T"][24] else -flipped

        with patch(
            "goal_takeover.phase2.position_sweep_analysis._cell_scores", side_effect=scores
        ) as mock:
            values = global_null(
                rows, features, labels, pairs, cells, {**spec, "permutation_repeats": 3}
            )
            self.assertEqual(values, [1.0, 1.0, 1.0])
            self.assertEqual(mock.call_count, 6)

    def test_validation_nonfinite_shape_and_fold_leakage_rejected(self):
        data = self.data()
        rows, features, texts, counts, positions, logprobs, _, spec = data
        for mutation in ("validation", "series", "pair", "shape", "nan"):
            r, f = copy.deepcopy(rows), copy.deepcopy(features)
            if mutation == "validation":
                r[0]["split_candidate"] = "validation"
            elif mutation == "series":
                r[0]["family_id"] = "other"
            elif mutation == "pair":
                r[0]["semantic_series_id"] = "other"
            elif mutation == "shape":
                f["T"][24] = f["T"][24][:-1]
            else:
                f["T"][24][0, 0] = float("nan")
            with self.assertRaises(ValueError):
                validate_inputs(r, f, texts, counts, positions, logprobs, spec)

    def test_derived_output_is_immutable(self):
        from goal_takeover.phase2.argument_recipient_672_train_readout import publish

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "derived"
            publish(output, {"report.json": b"{}"}, kind="position_sweep")
            with self.assertRaises(FileExistsError):
                publish(output, {"report.json": b"{}"}, kind="position_sweep")


@unittest.skipUnless(
    importlib.util.find_spec("torch") and importlib.util.find_spec("safetensors"),
    "research extras unavailable",
)
class BundleLoadingTest(unittest.TestCase):
    def test_synthetic_bundle_alignment_and_prefix_provenance(self):
        import json
        from contextlib import ExitStack

        import torch
        from test_position_sweep_positions import (
            SyntheticTokenizer,
            synthetic_pair,
            synthetic_prefix,
        )

        import goal_takeover.phase2.position_sweep_analysis as module
        from goal_takeover.phase2.position_sweep_capture import capture_files, write_bundle
        from goal_takeover.phase2.position_sweep_positions import resolve_positions
        from goal_takeover.storage.run_writer import canonical_json_bytes, sha256_file

        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            spec = copy.deepcopy(CONFIG)
            (root / "runtime.json").write_text("{}")
            rows = synthetic_pair()
            run_ids = {}
            freeze = {
                "git_commit": "capture-commit",
                "analysis_config_sha256": "cfg",
                "spec_sha256": "spec",
            }
            for number, row in enumerate(rows, 1):
                original_id = f"original-c{number:03d}"
                run_ids[row["condition_id"]] = original_id
                original = root / "artifacts/runs" / original_id
                original.mkdir(parents=True)
                prefix = synthetic_prefix(row)
                (original / "prefix.json").write_bytes(canonical_json_bytes(prefix))
                (original / "manifest.json").write_text("{}")
                resolved = resolve_positions(row, prefix, ACCOUNTS, SyntheticTokenizer(), spec)
                result = {
                    "positions": resolved,
                    "residuals": {
                        f"model.layers.{layer}": torch.full(
                            (1, 6, 4), float(number), dtype=torch.bfloat16
                        )
                        for layer in range(36)
                    },
                    "logprobs": {"synthetic": True},
                }
                run_id = spec["capture"]["run_id_prefix"] + f"-c{number:03d}"
                run = {
                    "status": "completed",
                    "runtime_freeze_sha256": sha256_file(root / "runtime.json"),
                    "run_id": run_id,
                    "condition_id": row["condition_id"],
                    "canonical_run_id": original_id,
                    "split": "train",
                    "git_dirty": False,
                    "git_commit": "capture-commit",
                    "canonical_manifest_sha256": sha256_file(original / "manifest.json"),
                    "analysis_config_sha256": "cfg",
                    "spec_sha256": "spec",
                    "model_dimensions": {"num_hidden_layers": 36, "hidden_size": 4},
                }
                write_bundle(
                    root / "artifacts",
                    run_id,
                    capture_files(row, result, run, {}, sha256_file(original / "prefix.json")),
                )
            stack.enter_context(
                patch.object(
                    module, "context", return_value=(root, spec, {}, rows, run_ids, ACCOUNTS)
                )
            )
            stack.enter_context(patch.object(module, "verify_sweep_freeze", return_value=freeze))
            stack.enter_context(
                patch.object(module, "clean_commit", return_value="analysis-commit")
            )
            stack.enter_context(
                patch.object(
                    module,
                    "canonical_prefix",
                    side_effect=lambda root, rid, row, spec: (synthetic_prefix(row), row, {}),
                )
            )
            loaded = module.load_inputs(Path("config.json"), Path("runtime.json"))
            features, provenance = loaded[3], loaded[-1]
            self.assertEqual(features["A1"][24].shape, (2, 4))
            self.assertEqual(features["A1"][24][:, 0].tolist(), [1.0, 2.0])
            self.assertEqual(provenance["validation_rows_loaded"], 0)
            self.assertEqual(len(provenance["capture_manifest_sha256"]), 2)
            prefix_path = root / "artifacts/runs/original-c001/prefix.json"
            prefix_path.write_text(json.dumps({"synthetic": "changed"}))
            with self.assertRaisesRegex(ValueError, "input/positions"):
                module.load_inputs(Path("config.json"), Path("runtime.json"))
