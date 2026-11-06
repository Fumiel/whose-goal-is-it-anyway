"""Selection-pointer diagnostic: labels, leakage, metric, rules and synthetic recovery."""

from __future__ import annotations

import importlib.util
import json
import unittest
from collections import Counter
from pathlib import Path

from goal_takeover.phase2.argument_recipient_672_selection_pointer import (
    classify,
    pair_index,
    paired_accuracy,
    pointer_indices,
    recipient_first_label,
    verify_labels_against_prefixes,
    with_block_position,
)

DECLARATION = json.loads(Path("data/templates/phase2_argument_recipient_672_v1.json").read_text())
ACCOUNTS = DECLARATION["account_value_ids"]
THRESHOLDS = {
    "positive_control_auroc": 0.95,
    "paired_accuracy": 0.8,
    "family_wise_alpha": 0.05,
    "baseline_margin": 0.1,
    "families_above_chance": 5,
    "specificity_margin": 0.05,
}


def _train_rows():
    rows = [r for r in DECLARATION["condition_specs"] if r["split_candidate"] == "train"]
    return with_block_position(rows, DECLARATION["task_specs"])


def _cell(accuracy=0.9, p=0.01, families=None, roles=None):
    return {
        "paired_accuracy": accuracy,
        "family_wise_p": p,
        "strata": {
            "family": families or dict.fromkeys("ABCDEF", 0.8),
            "source_role": roles or {"user_instruction": 0.8, "tool_output_document": 0.8},
        },
    }


class LabelTest(unittest.TestCase):
    def setUp(self) -> None:
        rows = _train_rows()
        self.rows = [rows[i] for i in pointer_indices(rows)]
        self.labels = [recipient_first_label(row, ACCOUNTS) for row in self.rows]

    def test_declared_counts_match_the_specification(self) -> None:
        self.assertEqual(len(self.rows), 240)
        self.assertEqual(Counter(self.labels), {1: 120, 0: 120})
        for key in ("recipient_rule", "family_id", "training_batch"):
            counts = Counter((r[key], y) for r, y in zip(self.rows, self.labels, strict=True))
            for value in {r[key] for r in self.rows}:
                self.assertEqual(counts[(value, 0)], counts[(value, 1)])
        by_recipient = Counter(
            (r["recipient_value_id"], y) for r, y in zip(self.rows, self.labels, strict=True)
        )
        self.assertEqual((by_recipient[("v1", 1)], by_recipient[("v1", 0)]), (38, 22))
        self.assertEqual((by_recipient[("v3", 1)], by_recipient[("v3", 0)]), (30, 30))

    def test_pairs_flip_and_keep_the_first_presented_account(self) -> None:
        pairs = pair_index(self.rows, self.labels)
        self.assertEqual(len(pairs), 120)
        for first, second in pairs:
            firsts = {
                self.rows[i]["recipient_value_id"]
                if self.labels[i]
                else self.rows[i]["reference_value_id"]
                for i in (first, second)
            }
            self.assertEqual(len(firsts), 1)

    def test_only_training_rows_are_used(self) -> None:
        self.assertEqual({row["split_candidate"] for row in self.rows}, {"train"})

    def test_document_order_matches_the_declared_read_order(self) -> None:
        for row in self.rows:
            if row["source_role"] != "tool_output_document":
                continue
            reads = [
                call["arguments"]["file_path"]
                for call in row["expected_tool_sequence"]
                if call["name"] == "read_file"
            ]
            self.assertEqual([document["path"] for document in row["documents"]], reads)

    def test_prefix_order_is_verified(self) -> None:
        texts = [
            row["user_instruction"] + "\n" + "\n".join(d["content"] for d in row["documents"])
            if row["source_role"] == "tool_output_document"
            else row["user_instruction"]
            for row in self.rows
        ]
        verify_labels_against_prefixes(self.rows, texts, ACCOUNTS)
        first = self.rows[0]
        recipient = ACCOUNTS[first["recipient_value_id"]]
        reference = ACCOUNTS[first["reference_value_id"]]
        reordered = f"{reference} {recipient}" if self.labels[0] else f"{recipient} {reference}"
        with self.assertRaises(ValueError):
            verify_labels_against_prefixes(self.rows, [reordered, *texts[1:]], ACCOUNTS)

    def test_duplicate_account_is_rejected(self) -> None:
        row = dict(self.rows[0])
        account = ACCOUNTS[row["recipient_value_id"]]
        row["source_role"] = "user_instruction"
        row["user_instruction"] = f"{account} {account} {ACCOUNTS[row['reference_value_id']]}"
        with self.assertRaises(ValueError):
            recipient_first_label(row, ACCOUNTS)


class MetricAndRuleTest(unittest.TestCase):
    def test_paired_accuracy_counts_ties_as_half(self) -> None:
        pairs = [(0, 1), (2, 3), (4, 5)]
        labels = [1, 0, 0, 1, 1, 0]
        self.assertEqual(paired_accuracy(pairs, labels, [2, 1, 2, 1, 1, 1]), 0.5)

    def test_non_flipping_pair_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            pair_index([{"draft_task_id": "t"}, {"draft_task_id": "t"}], [1, 1])
        with self.assertRaises(ValueError):
            pair_index([{"draft_task_id": "t"}], [1])

    def test_rules_apply_in_the_fixed_order(self) -> None:
        good = {"a": _cell()}
        self.assertEqual(classify(0.94, good, 0.5, THRESHOLDS)["class"], "R4")
        self.assertEqual(classify(0.95, good, 0.5, THRESHOLDS)["class"], "R1")
        self.assertEqual(classify(1.0, {"a": _cell(p=0.05)}, 0.5, THRESHOLDS)["class"], "R3")
        self.assertEqual(classify(1.0, {"a": _cell(accuracy=0.79)}, 0.5, THRESHOLDS)["class"], "R2")

    def test_each_r1_condition_is_required(self) -> None:
        self.assertEqual(classify(1.0, {"a": _cell()}, 0.81, THRESHOLDS)["class"], "R2")
        weak = {"A": 0.5, "B": 0.5, "C": 0.8, "D": 0.8, "E": 0.8, "F": 0.8}
        self.assertEqual(classify(1.0, {"a": _cell(families=weak)}, 0.5, THRESHOLDS)["class"], "R2")
        role = {"user_instruction": 0.9, "tool_output_document": 0.5}
        self.assertEqual(classify(1.0, {"a": _cell(roles=role)}, 0.5, THRESHOLDS)["class"], "R2")


@unittest.skipUnless(
    importlib.util.find_spec("numpy") and importlib.util.find_spec("sklearn"),
    "numerical development dependencies are unavailable",
)
class SyntheticAnalysisTest(unittest.TestCase):
    SPEC = {
        "judged_layers": [0],
        "report_only_layers": [1],
        "regularization_c": 1.0,
        "max_iter": 200,
        "seed": 7,
        "permutation_repeats": 25,
        "bootstrap_repeats": 20,
        "thresholds": THRESHOLDS,
    }

    def _analyze(self, *, pointer: float, source: float):
        import numpy as np

        from goal_takeover.phase2.argument_recipient_672_selection_pointer import analyze

        rows = _train_rows()
        rng = np.random.default_rng(3)
        matrix = rng.normal(size=(len(rows), 16))
        for index, row in enumerate(rows):
            matrix[index, 1] += source * (row["source_role"] == "user_instruction")
            if row["condition_variant"] in {"rx_ref_y", "ry_ref_x"}:
                matrix[index, 0] += pointer * recipient_first_label(row, ACCOUNTS)
        # Identical text and lengths keep the surface baselines uninformative here.
        report = analyze(
            rows,
            {0: matrix, 1: matrix},
            ["same text"] * len(rows),
            [100] * len(rows),
            ACCOUNTS,
            self.SPEC,
        )
        return report

    def test_embedded_pointer_is_recovered_and_output_is_deterministic(self) -> None:
        report = self._analyze(pointer=8.0, source=8.0)
        self.assertEqual(report["pointer_pairs"], 120)
        self.assertEqual(report["classification"]["class"], "R1")
        self.assertGreater(report["cells"]["layer0/paired_dom"]["paired_accuracy"], 0.9)
        self.assertFalse(report["cells"]["layer1/logistic"]["judged"])
        self.assertNotIn("layer1/logistic", report["classification"]["qualifying_cells"])
        self.assertEqual(report, self._analyze(pointer=8.0, source=8.0))

    def test_no_pointer_signal_is_not_detected(self) -> None:
        report = self._analyze(pointer=0.0, source=8.0)
        self.assertEqual(report["classification"]["class"], "R3")
        self.assertLess(report["cells"]["layer0/paired_dom"]["paired_accuracy"], 0.65)

    def test_missing_positive_control_stops_interpretation(self) -> None:
        report = self._analyze(pointer=8.0, source=0.0)
        self.assertEqual(report["classification"]["class"], "R4")


if __name__ == "__main__":
    unittest.main()
