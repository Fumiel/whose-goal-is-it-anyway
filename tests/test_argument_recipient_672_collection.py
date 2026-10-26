"""Split and stable-ID controls for the 672-condition review materialization."""

from __future__ import annotations

import copy
import json
import unittest
from collections import Counter
from pathlib import Path

from goal_takeover.datasets.argument_recipient_672_collection import (
    build_actual_sample_plan,
    build_checkpoint_plan,
    build_frozen_materialization,
    build_review_collection,
)

DRAFT = json.loads(Path("data/templates/phase2_argument_recipient_672_draft.json").read_text())


class ArgumentRecipient672CollectionTest(unittest.TestCase):
    def test_stable_ids_and_grouped_current_allocation(self) -> None:
        first, split, graph = build_review_collection(DRAFT)
        second, _, _ = build_review_collection(DRAFT)
        self.assertEqual(first, second)
        self.assertEqual(len({row["condition_id"] for row in first["condition_specs"]}), 672)
        self.assertEqual(
            Counter(row["split"] for row in split["assignments"]),
            {"train": 480, "validation": 192},
        )
        self.assertEqual(graph["batch_counts"], {f"B{i}": 96 for i in range(1, 6)})
        self.assertFalse(graph["independent_validation_certified"])
        self.assertTrue(graph["primary_validation_independence_certified"])
        self.assertEqual(len(graph["reviewed_non_edges"]), 3)
        self.assertEqual(
            {row["validation_series"] for row in graph["confirmed_cross_split_edges"]},
            {"I4", "J3"},
        )
        self.assertTrue(graph["required_cross_split_reviews"])
        split_by_id = {row["condition_id"]: row["split"] for row in split["assignments"]}
        component_by_id = {row["condition_id"]: row["component_id"] for row in split["assignments"]}
        for row in first["condition_specs"]:
            self.assertEqual(split_by_id[row["condition_id"]], row["split_candidate"])
        by_pair: dict[str, set[str]] = {}
        for row in first["condition_specs"]:
            by_pair.setdefault(row["pair_id"], set()).add(split_by_id[row["condition_id"]])
        self.assertTrue(all(len(values) == 1 for values in by_pair.values()))
        train_components = {
            row["component_id"] for row in split["assignments"] if row["split"] == "train"
        }
        primary_ids = {
            row["condition_id"] for row in first["condition_specs"] if row["family_id"] in "GH"
        }
        linked_ids = {
            row["condition_id"] for row in first["condition_specs"] if row["family_id"] in "IJ"
        }
        self.assertTrue({component_by_id[cid] for cid in primary_ids}.isdisjoint(train_components))
        self.assertTrue({component_by_id[cid] for cid in linked_ids} <= train_components)
        checkpoints = build_checkpoint_plan(first, graph)
        self.assertEqual(checkpoints["primary_metric"], "role_swap_auc")
        self.assertEqual(checkpoints["primary_metric_threshold"], 0.8)
        self.assertEqual(
            [stage["train_count"] for stage in checkpoints["stages"]],
            [96, 192, 288, 384, 480],
        )
        self.assertTrue(all(stage["validation_count"] == 192 for stage in checkpoints["stages"]))
        self.assertTrue(
            all(
                stage["primary_validation_candidate_count"] == 96
                and stage["primary_metric_condition_count"] == 48
                and stage["train_linked_diagnostic_count"] == 96
                for stage in checkpoints["stages"]
            )
        )
        self.assertTrue(
            all(
                checkpoints["stages"][i]["train_condition_ids"]
                == checkpoints["stages"][i + 1]["train_condition_ids"][: 96 * (i + 1)]
                for i in range(4)
            )
        )
        self.assertEqual(
            len({tuple(stage["validation_condition_ids"]) for stage in checkpoints["stages"]}),
            1,
        )
        metric_ids = {
            row["condition_id"]
            for row in first["condition_specs"]
            if row["family_id"] in "GH" and row["condition_variant"] in {"rx_ref_y", "ry_ref_x"}
        }
        self.assertEqual(set(checkpoints["stages"][0]["primary_metric_condition_ids"]), metric_ids)

    def test_text_change_changes_condition_id_without_changing_other_ids(self) -> None:
        original, _, _ = build_review_collection(DRAFT)
        changed = copy.deepcopy(DRAFT)
        task_id = changed["condition_specs"][0]["draft_task_id"]
        for row in changed["condition_specs"]:
            if row["draft_task_id"] == task_id:
                row["documents"][0]["content"] += "\nReview note."
        revised, _, _ = build_review_collection(changed)
        self.assertNotEqual(
            original["condition_specs"][0]["condition_id"],
            revised["condition_specs"][0]["condition_id"],
        )
        self.assertEqual(
            original["condition_specs"][4]["condition_id"],
            revised["condition_specs"][4]["condition_id"],
        )

    def test_rejects_family_crossing_split(self) -> None:
        changed = copy.deepcopy(DRAFT)
        changed["condition_specs"][0]["split_candidate"] = "validation"
        with self.assertRaises(ValueError):
            build_review_collection(changed)

    def test_actual_sample_is_unique_paired_and_uses_all_task_positions(self) -> None:
        declaration, _, _ = build_review_collection(DRAFT)
        sample = build_actual_sample_plan(declaration)
        self.assertEqual(sample["series_count"], 56)
        self.assertEqual(sample["condition_count"], 112)
        self.assertEqual(len(sample["selections"]), 56)
        self.assertEqual(
            Counter(item["split"] for item in sample["selections"]),
            {"train": 40, "validation": 16},
        )
        self.assertEqual(set(item["task_position"] for item in sample["selections"]), {1, 2, 3})
        lookup = {row["condition_id"]: row for row in declaration["condition_specs"]}
        for item in sample["selections"]:
            self.assertEqual(len(item["condition_ids"]), 2)
            self.assertEqual(
                {lookup[cid]["condition_variant"] for cid in item["condition_ids"]},
                {"rx_ref_y", "ry_ref_x"},
            )
            self.assertEqual(
                {lookup[cid]["draft_task_id"] for cid in item["condition_ids"]},
                {item["task_id"]},
            )

    def test_execution_materialization_has_separate_status_and_same_ids(self) -> None:
        reviewed, _, _ = build_review_collection(DRAFT)
        declaration, split, graph, checkpoints, sample = build_frozen_materialization(DRAFT)
        self.assertEqual(declaration["status"], "design_frozen_runtime_pending")
        self.assertEqual(split["split_version"], "phase2_argument_recipient_672_v1")
        self.assertEqual(graph["status"], "design_frozen_runtime_pending")
        self.assertEqual(checkpoints["status"], "design_frozen_runtime_pending")
        self.assertEqual(sample["status"], "design_frozen_runtime_pending")
        self.assertEqual(
            [row["condition_id"] for row in declaration["condition_specs"]],
            [row["condition_id"] for row in reviewed["condition_specs"]],
        )


if __name__ == "__main__":
    unittest.main()
