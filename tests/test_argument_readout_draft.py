"""Consistency checks for the 96-condition argument_readout review draft."""

import copy
import json
import unittest
from pathlib import Path

from goal_takeover.datasets.argument_readout_draft import (
    ACCOUNTS,
    build_draft,
    iban_mod97_valid,
    validate_draft,
)

DRAFT = Path("data/templates/phase2_argument_readout_96_draft.json")


class ArgumentReadoutDraftTests(unittest.TestCase):
    def setUp(self) -> None:
        self.draft = build_draft()

    def test_generated_draft_validates_and_counts(self) -> None:
        validate_draft(self.draft)
        self.assertEqual(self.draft["task_count"], 24)
        self.assertEqual(self.draft["condition_count"], 96)
        self.assertEqual(self.draft["split_candidate_counts"], {"train": 64, "validation": 32})

    def test_committed_draft_matches_generator(self) -> None:
        committed = json.loads(DRAFT.read_text(encoding="utf-8"))
        self.assertEqual(committed, self.draft)

    def test_account_checksums_and_distance(self) -> None:
        values = list(ACCOUNTS.values())
        self.assertTrue(all(iban_mod97_valid(v) for v in values))
        for i, a in enumerate(values):
            for b in values[i + 1 :]:
                self.assertGreaterEqual(sum(x != y for x, y in zip(a, b, strict=True)), 10)
            self.assertNotIn("0000000", a)

    def test_candidate_balance_per_split(self) -> None:
        for split, positives, hard_negatives in (("train", 16, 8), ("validation", 8, 4)):
            for key in ACCOUNTS:
                rows = [c for c in self.draft["condition_specs"] if c["split_candidate"] == split]
                self.assertEqual(sum(c["argument_present"][key] for c in rows), positives)
                self.assertEqual(
                    sum(
                        1
                        for c in rows
                        if c["lexical_presence"][key] and not c["argument_present"][key]
                    ),
                    hard_negatives,
                )

    def test_role_and_order_are_balanced(self) -> None:
        rows = [c for c in self.draft["condition_specs"] if c["reference_value_id"]]
        recipient_first = 0
        for c in rows:
            text = c["user_instruction"]
            recipient_first += text.index(ACCOUNTS[c["recipient_value_id"]]) < text.index(
                ACCOUNTS[c["reference_value_id"]]
            )
        self.assertEqual(recipient_first, len(rows) // 2)

    def test_phrasing_design(self) -> None:
        train = [t["phrasing"] for t in self.draft["task_specs"] if t["split_candidate"] == "train"]
        val = [
            t["phrasing"] for t in self.draft["task_specs"] if t["split_candidate"] == "validation"
        ]
        pairs = {(p["recipient_phrase_id"], p["reference_phrase_id"]) for p in train}
        self.assertEqual(len(pairs), 16)
        self.assertEqual(sum(p["account_block_position"] == "before_task" for p in train), 4)
        self.assertTrue(all(p["phrasing_novelty"] == "train_seen" for p in train))
        counts = {}
        for p in val:
            counts[p["phrasing_novelty"]] = counts.get(p["phrasing_novelty"], 0) + 1
        self.assertEqual(
            counts,
            {"train_seen": 2, "recipient_novel": 2, "reference_novel": 2, "both_novel": 2},
        )

    def test_validation_rejects_reused_train_phrase_pair(self) -> None:
        broken = copy.deepcopy(self.draft)
        first, second = [t for t in broken["task_specs"] if t["split_candidate"] == "train"][:2]
        second["phrasing"] = dict(first["phrasing"])
        with self.assertRaises(ValueError):
            validate_draft(broken)

    def test_validation_rejects_broken_labels(self) -> None:
        broken = copy.deepcopy(self.draft)
        broken["condition_specs"][2]["argument_present"] = {k: 0 for k in ACCOUNTS}
        with self.assertRaises(ValueError):
            validate_draft(broken)

    def test_validation_rejects_negation_wording(self) -> None:
        broken = copy.deepcopy(self.draft)
        broken["condition_specs"][2]["user_instruction"] += " It is not the recipient."
        with self.assertRaises(ValueError):
            validate_draft(broken)

    def test_generation_is_deterministic(self) -> None:
        self.assertEqual(build_draft(), build_draft())


if __name__ == "__main__":
    unittest.main()
