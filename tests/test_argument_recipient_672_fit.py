"""Cumulative B1 fit and separate G/H versus I/J evaluation controls."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from goal_takeover.datasets.argument_recipient_672_collection import (
    build_checkpoint_plan,
    build_review_collection,
)
from goal_takeover.phase2.argument_probe import FeatureRow
from goal_takeover.phase2.argument_recipient_672_fit import (
    fit_cumulative_stage,
    write_cumulative_fit,
)

DRAFT = json.loads(Path("data/templates/phase2_argument_recipient_672_draft.json").read_text())


@unittest.skipUnless(
    importlib.util.find_spec("numpy") and importlib.util.find_spec("sklearn"),
    "numerical development dependencies are unavailable",
)
class CumulativeFitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import numpy as np

        cls.declaration, cls.split, graph = build_review_collection(DRAFT)
        cls.checkpoint = build_checkpoint_plan(cls.declaration, graph)
        component_by_id = {
            row["condition_id"]: row["component_id"] for row in cls.split["assignments"]
        }
        cls.rows = [
            FeatureRow(
                condition_id=row["condition_id"],
                run_id=f"synthetic-{index}",
                split=row["split_candidate"],
                component_id=component_by_id[row["condition_id"]],
                task_template_id=row["task_template_id"],
                user_instruction=row["user_instruction"],
                prefix_id=f"synthetic-prefix-{index}",
                boundary=row["exposure"]["boundary"],
                token_index=0,
                token_id=1,
                layer="model.layers.0",
                position_name="Tend_assistant",
                labels=row["argument_present"],
                lexical_presence={
                    candidate: 1 for candidate in cls.declaration["account_value_ids"]
                },
                vector=np.asarray(list(row["argument_present"].values()), dtype=float),
            )
            for index, row in enumerate(cls.declaration["condition_specs"])
        ]

    def fit(self, rows: list[FeatureRow]) -> dict:
        report, _ = fit_cumulative_stage(
            self.declaration,
            self.checkpoint,
            "B1",
            {"model.layers.0": rows},
            layer="model.layers.0",
            regularization_c=1.0,
            max_iter=1000,
            seed=1,
            random_label_repeats=2,
            calibration_bins=5,
        )
        return report

    def test_primary_and_linked_diagnostic_are_separate(self) -> None:
        report = self.fit(self.rows)
        self.assertEqual(report["train_condition_count"], 96)
        self.assertEqual(report["primary"]["condition_count"], 48)
        self.assertEqual(report["primary"]["auc"], 1.0)
        self.assertEqual(report["train_linked_diagnostic"]["auc"], 1.0)
        self.assertEqual(len(report["random_label_controls_primary"]), 2)
        self.assertEqual(report["tfidf_baseline_primary"]["condition_count"], 48)
        self.assertEqual(set(report["primary_role_swap_strata"]["family_id"]), {"G", "H"})
        self.assertEqual(
            set(report["primary_role_swap_strata"]["source_role"]),
            {"user_instruction", "tool_output_document"},
        )
        self.assertEqual(report["primary_validation_calibration"]["v1"]["count"], 96)
        self.assertEqual(report["development_threshold_met"], True)

    def test_validation_missing_is_undefined_and_train_missing_stops(self) -> None:
        primary_id = self.checkpoint["stages"][0]["primary_metric_condition_ids"][0]
        without_primary = [row for row in self.rows if row.condition_id != primary_id]
        report = self.fit(without_primary)
        self.assertIsNone(report["primary"]["auc"])
        self.assertIsNone(report["development_threshold_met"])
        self.assertEqual(report["validation_missing_condition_ids"], [primary_id])
        train_id = self.checkpoint["stages"][0]["train_condition_ids"][0]
        without_train = [row for row in self.rows if row.condition_id != train_id]
        with self.assertRaisesRegex(ValueError, "training features"):
            self.fit(without_train)

    def test_derived_fit_writes_once_with_checksums(self) -> None:
        from goal_takeover.storage.run_writer import sha256_file

        report, fitted = fit_cumulative_stage(
            self.declaration,
            self.checkpoint,
            "B1",
            {"model.layers.0": self.rows},
            layer="model.layers.0",
            regularization_c=1.0,
            max_iter=1000,
            seed=1,
            random_label_repeats=1,
            calibration_bins=5,
        )
        provenance = {
            "git_commit": "synthetic-commit",
            "git_dirty": False,
            "design_freeze_sha256": "synthetic-design",
            "runtime_freeze_sha256": "synthetic-runtime",
            "capture_manifest_sha256": {"synthetic-run": "synthetic-hash"},
            "b1_selection_sha256": "synthetic-selection",
        }
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "fit-b1"
            write_cumulative_fit(target, report, fitted, provenance=provenance)
            manifest = json.loads((target / "manifest.json").read_text())
            for name, item in manifest["artifacts"].items():
                self.assertEqual(sha256_file(target / name), item["sha256"])
            with self.assertRaises(FileExistsError):
                write_cumulative_fit(target, report, fitted, provenance=provenance)


if __name__ == "__main__":
    unittest.main()
