"""Checks for the approved 96-condition recipient collection declaration."""

from __future__ import annotations

import copy
import json
import unittest
from collections import Counter
from pathlib import Path

from goal_takeover.datasets.argument_readout_collection import build_collection
from goal_takeover.phase2.argument_collection import capture_user_boundary, load_plan

ROOT = Path(__file__).resolve().parents[1]


class ArgumentReadoutCollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.draft = json.loads(
            (ROOT / "data/templates/phase2_argument_readout_96_draft.json").read_text()
        )

    def test_stable_ids_and_split_components(self) -> None:
        final, split, graph = build_collection(self.draft)
        again, _, _ = build_collection(self.draft)
        self.assertEqual(final, again)
        self.assertEqual(len({row["condition_id"] for row in final["condition_specs"]}), 96)
        self.assertEqual(
            Counter(row["split"] for row in split["assignments"]),
            {
                "train": 64,
                "validation": 32,
            },
        )
        components = {
            role: {row["component_id"] for row in split["assignments"] if row["split"] == role}
            for role in ("train", "validation")
        }
        self.assertFalse(components["train"] & components["validation"])
        self.assertEqual(len(components["train"]), 1)
        self.assertEqual(len(components["validation"]), 2)
        self.assertEqual(
            graph["component_by_series"]["invoice_payment"], graph["existing_train_component_id"]
        )

    def test_changed_content_or_split_is_rejected(self) -> None:
        changed = copy.deepcopy(self.draft)
        changed["task_specs"][0]["split_candidate"] = "validation"
        with self.assertRaisesRegex(ValueError, "series/split candidate"):
            build_collection(changed)
        changed = copy.deepcopy(self.draft)
        changed["condition_specs"][0]["argument_present"]["v1"] = 0
        with self.assertRaisesRegex(ValueError, "argument_present"):
            build_collection(changed)

    def test_design_loads_without_model_and_selects_user_boundary(self) -> None:
        plan, design = load_plan(ROOT / "configs/experiments/phase2_argument_readout_96_v1.json")
        self.assertEqual(len(plan.conditions), 96)
        self.assertEqual(design["sampling"]["stochastic_repetitions"], 0)
        self.assertTrue(capture_user_boundary([{"role": "user"}]))
        self.assertFalse(capture_user_boundary([{"role": "user"}, {"role": "tool"}]))


if __name__ == "__main__":
    unittest.main()
