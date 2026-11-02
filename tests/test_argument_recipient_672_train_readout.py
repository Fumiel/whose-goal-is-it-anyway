"""Train-only readout diagnostic: metrics, fold separation and log-prob alignment."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from goal_takeover.datasets.argument_recipient_672_collection import build_review_collection
from goal_takeover.phase2.argument_recipient_672_recipient_logprob import (
    candidate_accounts,
    continuation_ids,
    summarize,
)
from goal_takeover.phase2.argument_recipient_672_train_readout import (
    loso_scores,
    publish,
    readout_metrics,
    train_rows_and_run_ids,
)

DRAFT = json.loads(Path("data/templates/phase2_argument_recipient_672_draft.json").read_text())


def _b1_rows(declaration):
    return sorted(
        (
            row
            for row in declaration["condition_specs"]
            if row["split_candidate"] == "train" and row["training_batch"] == "B1"
        ),
        key=lambda row: row["condition_id"],
    )


class ReadoutMetricTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.declaration, _, _ = build_review_collection(DRAFT)
        cls.rows = _b1_rows(cls.declaration)
        cls.candidates = sorted(cls.declaration["account_value_ids"])

    def _scores(self, value):
        return {
            row["condition_id"]: {c: float(value(row, c)) for c in self.candidates}
            for row in self.rows
        }

    def test_role_scores_are_perfect_everywhere(self) -> None:
        result = readout_metrics(
            self.rows, self._scores(lambda row, c: row["argument_present"][c]), self.candidates
        )
        self.assertEqual(result["role_swap_auc"], 1.0)
        self.assertEqual(result["within_condition_choice_accuracy"], 1.0)
        self.assertEqual(result["paired_within_task_accuracy"], 1.0)
        self.assertEqual(result["recipient_vs_absent_auc"], 1.0)
        self.assertEqual(result["role_swap_row_count"], 48)

    def test_presence_only_scores_give_chance_role(self) -> None:
        exposed = lambda row, c: c in (row["recipient_value_id"], row["reference_value_id"])  # noqa: E731
        result = readout_metrics(self.rows, self._scores(exposed), self.candidates)
        self.assertEqual(result["presence_auc"], 1.0)
        self.assertEqual(result["role_swap_auc"], 0.5)
        self.assertEqual(result["paired_within_task_accuracy"], 0.0)  # ties are not wins

    def test_train_mapping_excludes_validation(self) -> None:
        rows, run_ids = train_rows_and_run_ids(self.declaration, "prefix")
        self.assertEqual(len(rows), 480)
        self.assertEqual(set(run_ids), {row["condition_id"] for row in rows})
        validation = {
            row["condition_id"]
            for row in self.declaration["condition_specs"]
            if row["split_candidate"] == "validation"
        }
        self.assertFalse(validation & set(run_ids))
        index = {
            row["condition_id"]: i for i, row in enumerate(self.declaration["condition_specs"], 1)
        }
        for cid, run_id in run_ids.items():
            self.assertEqual(run_id, f"prefix-c{index[cid]:03d}")

    def test_publish_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "out"
            publish(target, {"report.json": b"{}\n"}, kind="test")
            manifest = json.loads((target / "manifest.json").read_text())
            self.assertEqual(manifest["artifacts"]["report.json"]["bytes"], 3)
            with self.assertRaises(FileExistsError):
                publish(target, {"report.json": b"{}\n"}, kind="test")


@unittest.skipUnless(
    importlib.util.find_spec("numpy") and importlib.util.find_spec("sklearn"),
    "numerical development dependencies are unavailable",
)
class LosoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.declaration, _, _ = build_review_collection(DRAFT)
        cls.rows = _b1_rows(cls.declaration)
        cls.candidates = sorted(cls.declaration["account_value_ids"])

    def test_role_signal_generalizes_across_series(self) -> None:
        import numpy as np

        rng = np.random.default_rng(0)
        signal = np.array(
            [[row["argument_present"][c] for c in self.candidates] for row in self.rows], float
        )
        features = np.hstack([signal * 3.0, rng.normal(size=(len(self.rows), 20))])
        scores = loso_scores(
            self.rows,
            features,
            self.candidates,
            objective="exposed_only",
            regularization_c=1.0,
            max_iter=1000,
            seed=0,
        )
        self.assertGreater(
            readout_metrics(self.rows, scores, self.candidates)["role_swap_auc"], 0.95
        )

    def test_held_out_series_is_not_memorized(self) -> None:
        import numpy as np

        # Pure noise with more dimensions than rows: a fold that leaked held-out
        # rows into training would memorize them and score near 1.0.
        features = np.random.default_rng(1).normal(size=(len(self.rows), 400))
        scores = loso_scores(
            self.rows,
            features,
            self.candidates,
            objective="all_rows",
            regularization_c=100.0,
            max_iter=2000,
            seed=0,
        )
        self.assertLess(readout_metrics(self.rows, scores, self.candidates)["role_swap_auc"], 0.8)
        self.assertEqual({len(values) for values in scores.values()}, {4})


class FakeTokenizer:
    """Character tokens, except a merged token for '9"' to exercise boundary merges."""

    def __call__(self, text, add_special_tokens=False):
        ids, i = [], 0
        while i < len(text):
            if text.startswith('9"', i):
                ids.append(1000)
                i += 2
            else:
                ids.append(ord(text[i]))
                i += 1
        return {"input_ids": ids}


class LogprobAlignmentTest(unittest.TestCase):
    def test_continuation_follows_saved_prefix(self) -> None:
        tokenizer = FakeTokenizer()
        prefix = "ab\n"
        ids = continuation_ids(tokenizer, prefix, tokenizer(prefix)["input_ids"], 'x9"')
        self.assertEqual(ids, [ord("x"), 1000])

    def test_prefix_drift_is_rejected(self) -> None:
        tokenizer = FakeTokenizer()
        with self.assertRaises(ValueError):
            continuation_ids(tokenizer, "ab9", tokenizer("ab9")["input_ids"], '"')

    def test_summary_choice_and_margin(self) -> None:
        declaration, _, _ = build_review_collection(DRAFT)
        rows = _b1_rows(declaration)
        accounts = candidate_accounts(declaration)
        totals, exposed = {}, {}
        for row in rows:
            present = [row["recipient_value_id"]] + (
                [row["reference_value_id"]] if row["reference_value_id"] else []
            )
            exposed[row["condition_id"]] = present
            totals[row["condition_id"]] = {
                key: (-1.0 if key == row["recipient_value_id"] else -5.0) for key in accounts
            }
        result = summarize(rows, totals, exposed, sorted(declaration["account_value_ids"]))
        self.assertEqual(
            result["recipient_argmax_among_exposed"]["all"], {"correct": 96, "count": 96}
        )
        self.assertEqual(result["margin_nats"]["median"], 4.0)
        self.assertEqual(result["role_swap_auc_by_batch"], {"B1": 1.0})


if __name__ == "__main__":
    unittest.main()
