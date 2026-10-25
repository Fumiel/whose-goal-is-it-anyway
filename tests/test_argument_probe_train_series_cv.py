"""Fold boundaries for exploratory training-series cross-validation."""

from __future__ import annotations

import unittest

from goal_takeover.phase2.argument_probe_train_series_cv import fold_indices


class TrainSeriesCvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conditions = []
        for family in ("invoice", "refund", "product", "expense"):
            for task in range(2):
                for variant in range(4):
                    self.conditions.append(
                        {
                            "split": "train",
                            "run_id": f"{family}-{task}-{variant}",
                            "paraphrase_family_id": family,
                            "task_template_id": f"{family}-{task}",
                            "pair_id": f"{family}-{task}-pair",
                        }
                    )
        self.conditions.append(
            {
                "split": "validation",
                "run_id": "external-validation",
                "paraphrase_family_id": "held-out",
                "task_template_id": "held-out-1",
                "pair_id": "held-out-1-pair",
            }
        )
        self.folds = {
            "INV": "invoice",
            "REF": "refund",
            "PRD": "product",
            "EXP": "expense",
        }

    def test_each_series_held_out_whole_and_external_validation_excluded(self) -> None:
        folds = fold_indices(self.conditions, self.folds)
        for fold_id, declaration in folds.items():
            self.assertEqual(len(declaration["train_run_ids"]), 24)
            self.assertEqual(len(declaration["validation_run_ids"]), 8)
            self.assertTrue(
                all(
                    run_id.startswith(self.folds[fold_id])
                    for run_id in declaration["validation_run_ids"]
                )
            )
            self.assertNotIn("external-validation", declaration["train_run_ids"])
            self.assertNotIn("external-validation", declaration["validation_run_ids"])
            self.assertFalse(
                set(declaration["train_task_ids"]) & set(declaration["validation_task_ids"])
            )

    def test_incomplete_or_duplicate_folds_fail(self) -> None:
        with self.assertRaises(ValueError):
            fold_indices(self.conditions, {"INV": "invoice", "REF": "refund"})
        with self.assertRaises(ValueError):
            fold_indices(
                self.conditions,
                {
                    "INV": "invoice",
                    "INV2": "invoice",
                    "REF": "refund",
                    "PRD": "product",
                    "EXP": "expense",
                },
            )

    def test_shared_task_across_series_fails(self) -> None:
        self.conditions[-2]["task_template_id"] = "invoice-0"
        with self.assertRaises(ValueError):
            fold_indices(self.conditions, self.folds)


if __name__ == "__main__":
    unittest.main()
