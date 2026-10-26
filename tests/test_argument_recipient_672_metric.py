"""Primary metric controls for the reviewed role-swap validation subset."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from goal_takeover.datasets.argument_recipient_672_collection import build_review_collection
from goal_takeover.phase2.argument_recipient_672_metric import primary_metric_rows, role_swap_auc

DRAFT = json.loads(Path("data/templates/phase2_argument_recipient_672_draft.json").read_text())


class RoleSwapAucTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.declaration, _, _ = build_review_collection(DRAFT)
        cls.rows = primary_metric_rows(cls.declaration)

    def test_perfect_and_reversed_scores(self) -> None:
        perfect = {
            row["condition_id"]: {
                candidate: float(row["argument_present"][candidate])
                for candidate in self.declaration["account_value_ids"]
            }
            for row in self.rows
        }
        result = role_swap_auc(self.declaration, perfect)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["auc"], 1.0)
        self.assertEqual(result["condition_count"], 48)
        self.assertEqual(
            {
                (part["positive_count"], part["negative_count"])
                for part in result["by_candidate"].values()
            },
            {(12, 12)},
        )
        reversed_scores = {
            condition_id: {candidate: 1.0 - score for candidate, score in values.items()}
            for condition_id, values in perfect.items()
        }
        self.assertEqual(role_swap_auc(self.declaration, reversed_scores)["auc"], 0.0)

    def test_ties_missing_and_diagnostic_rows(self) -> None:
        scores = {
            row["condition_id"]: {
                candidate: 0.5 for candidate in self.declaration["account_value_ids"]
            }
            for row in self.rows
        }
        scores["unrelated_diagnostic_condition"] = {"v1": 1.0}
        self.assertEqual(role_swap_auc(self.declaration, scores)["auc"], 0.5)
        del scores[self.rows[0]["condition_id"]][self.rows[0]["recipient_value_id"]]
        result = role_swap_auc(self.declaration, scores)
        self.assertIsNone(result["auc"])
        self.assertEqual(result["status"], "undefined_incomplete_scores")
        self.assertEqual(len(result["missing"]), 1)
        scores[self.rows[0]["condition_id"]][self.rows[0]["recipient_value_id"]] = float("nan")
        self.assertIsNone(role_swap_auc(self.declaration, scores)["auc"])


if __name__ == "__main__":
    unittest.main()
