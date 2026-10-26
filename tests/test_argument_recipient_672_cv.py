"""B1-only hyperparameter selection controls."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from goal_takeover.datasets.argument_recipient_672_collection import build_review_collection
from goal_takeover.phase2.argument_probe import FeatureRow
from goal_takeover.phase2.argument_recipient_672_cv import select_b1_layer_and_c

DRAFT = json.loads(Path("data/templates/phase2_argument_recipient_672_draft.json").read_text())
LAYER_GRID = [0, 8, 16, 24, 32, 35]
C_GRID = [0.01, 0.1, 1.0]


@unittest.skipUnless(
    importlib.util.find_spec("numpy") and importlib.util.find_spec("sklearn"),
    "numerical development dependencies are unavailable",
)
class B1SelectionTest(unittest.TestCase):
    def select(self, features: dict[str, list[FeatureRow]]) -> dict:
        return select_b1_layer_and_c(
            self.declaration,
            features,
            seed=20261027,
            layer_grid=LAYER_GRID,
            regularization_c_grid=C_GRID,
            max_iter=1000,
        )

    @classmethod
    def setUpClass(cls) -> None:
        import numpy as np

        cls.declaration, cls.split, _ = build_review_collection(DRAFT)
        component_by_id = {
            row["condition_id"]: row["component_id"] for row in cls.split["assignments"]
        }
        rows = [
            row
            for row in cls.declaration["condition_specs"]
            if row["split_candidate"] == "train" and row["training_batch"] == "B1"
        ]
        cls.features = {}
        for layer_index in LAYER_GRID:
            layer = f"model.layers.{layer_index}"
            cls.features[layer] = [
                FeatureRow(
                    condition_id=row["condition_id"],
                    run_id=f"synthetic-{index}",
                    split="train",
                    component_id=component_by_id[row["condition_id"]],
                    task_template_id=row["task_template_id"],
                    user_instruction=row["user_instruction"],
                    prefix_id=f"synthetic-prefix-{index}",
                    boundary=row["exposure"]["boundary"],
                    token_index=0,
                    token_id=1,
                    layer=layer,
                    position_name="Tend_assistant",
                    labels=row["argument_present"],
                    lexical_presence=row["lexical_presence"],
                    vector=np.asarray(list(row["argument_present"].values()), dtype=float),
                )
                for index, row in enumerate(rows)
            ]

    def test_selects_once_from_complete_b1_grid(self) -> None:
        result = self.select(self.features)
        self.assertEqual(len(result["settings"]), 18)
        self.assertEqual(len(result["series"]), 8)
        self.assertEqual(result["chosen"]["layer"], "model.layers.0")
        self.assertEqual(result["chosen"]["regularization_c"], 0.01)
        self.assertEqual(result["chosen"]["role_swap_auc"], 1.0)

    def test_rejects_missing_b1_capture(self) -> None:
        shortened = {key: list(value) for key, value in self.features.items()}
        shortened["model.layers.0"].pop()
        with self.assertRaisesRegex(ValueError, "missing or duplicate"):
            self.select(shortened)


if __name__ == "__main__":
    unittest.main()
