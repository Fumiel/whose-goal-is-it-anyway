"""Actual trajectory exposure uses observed tool results."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from goal_takeover.phase2.argument_recipient_672_actual import select_actual_exposed_prefix

DRAFT = json.loads(Path("data/templates/phase2_argument_recipient_672_draft.json").read_text())


class ActualExposureTest(unittest.TestCase):
    def test_document_positive_requires_observed_tool_content(self) -> None:
        condition = next(
            row
            for row in DRAFT["condition_specs"]
            if row["recipient_rule"] == "D1" and row["condition_variant"] == "rx"
        )
        user = {"role": "user", "content": condition["user_instruction"]}
        document = condition["documents"][0]
        before = SimpleNamespace(
            text=condition["user_instruction"],
            token_ids=(1,),
            prefix_id="before",
            boundary=SimpleNamespace(value="user_to_assistant"),
        )
        after = SimpleNamespace(
            text=condition["user_instruction"] + document["content"],
            token_ids=(1, 2),
            prefix_id="after",
            boundary=SimpleNamespace(value="first_tool_to_assistant"),
        )
        missing = select_actual_exposed_prefix([before], [(user,)], condition)
        self.assertEqual(missing[2], "declared_source_not_exposed_in_actual_trajectory")
        guessed = select_actual_exposed_prefix([after], [(user,)], condition)
        self.assertEqual(guessed[2], "declared_source_not_exposed_in_actual_trajectory")
        selected = select_actual_exposed_prefix(
            [before, after],
            [(user,), (user, {"role": "tool", "content": document["content"]})],
            condition,
        )
        self.assertEqual(selected[0].prefix_id, "after")
        self.assertEqual(selected[1]["token_index"], 1)
        self.assertTrue(selected[1]["boundary_matches_canonical"])


if __name__ == "__main__":
    unittest.main()
