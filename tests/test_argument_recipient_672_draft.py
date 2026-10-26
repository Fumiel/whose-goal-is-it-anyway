"""Consistency checks for the 672-condition recipient-collection review draft."""

import copy
import json
import unittest
from pathlib import Path

from goal_takeover.datasets.argument_recipient_672_draft import (
    ACCOUNTS,
    TRAIN_BATCHES,
    build_draft,
    validate_draft,
)

DRAFT = Path("data/templates/phase2_argument_recipient_672_draft.json")


class ArgumentRecipient672DraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.draft = build_draft()

    def test_generated_draft_validates_and_counts(self) -> None:
        validate_draft(self.draft)
        self.assertEqual(self.draft["task_count"], 168)
        self.assertEqual(self.draft["condition_count"], 672)
        self.assertEqual(self.draft["split_candidate_counts"], {"train": 480, "validation": 192})
        self.assertEqual(
            self.draft["training_batch_counts"],
            {"B1": 96, "B2": 96, "B3": 96, "B4": 96, "B5": 96, "none": 192},
        )

    def test_committed_draft_matches_generator(self) -> None:
        committed = json.loads(DRAFT.read_text(encoding="utf-8"))
        self.assertEqual(committed, self.draft)

    def test_families_do_not_cross_splits(self) -> None:
        splits = {}
        for t in self.draft["task_specs"]:
            splits.setdefault(t["family_id"], set()).add(t["split_candidate"])
        self.assertEqual({f for f, s in splits.items() if s == {"train"}}, set("ABCDEF"))
        self.assertEqual({f for f, s in splits.items() if s == {"validation"}}, set("GHIJ"))

    def test_batches_have_all_train_families_and_five_u_three_d(self) -> None:
        tasks = self.draft["task_specs"]
        for batch in TRAIN_BATCHES:
            rows = [t for t in tasks if t["training_batch"] == batch]
            self.assertEqual({t["family_id"] for t in rows}, set("ABCDEF"))
            kinds = [t["series_source_kind"] for t in rows if t["draft_task_id"].endswith("-1")]
            self.assertEqual((kinds.count("U"), kinds.count("D")), (5, 3))

    def test_candidate_balance_per_batch_and_validation(self) -> None:
        groups = {b: 24 for b in TRAIN_BATCHES} | {None: 48}
        for batch, positives in groups.items():
            rows = [c for c in self.draft["condition_specs"] if c["training_batch"] == batch]
            for key in ACCOUNTS:
                self.assertEqual(sum(c["argument_present"][key] for c in rows), positives)
                self.assertEqual(
                    sum(
                        1
                        for c in rows
                        if c["lexical_presence"][key] and not c["argument_present"][key]
                    ),
                    positives // 2,
                )

    def test_role_and_order_are_balanced_per_split(self) -> None:
        for split in ("train", "validation"):
            rows = [
                c
                for c in self.draft["condition_specs"]
                if c["reference_value_id"] and c["split_candidate"] == split
            ]
            recipient_first = 0
            for c in rows:
                text = (
                    c["user_instruction"] + "\n" + "\n".join(d["content"] for d in c["documents"])
                )
                recipient_first += text.index(ACCOUNTS[c["recipient_value_id"]]) < text.index(
                    ACCOUNTS[c["reference_value_id"]]
                )
            self.assertEqual(recipient_first, len(rows) // 2)

    def test_exposure_follows_rule(self) -> None:
        for c in self.draft["condition_specs"]:
            rule = c["recipient_rule"]
            boundary = c["exposure"]["boundary"]
            if rule in ("U0", "UN", "UI"):
                self.assertEqual(boundary, "user_to_assistant")
            elif rule == "D2":
                self.assertEqual(boundary, "later_tool_to_assistant")
                self.assertEqual(len(c["exposure"]["after_tool_results_for"]), 2)
            else:
                self.assertEqual(boundary, "first_tool_to_assistant")

    def test_validation_phrasing_strata(self) -> None:
        for context in ("user_instruction", "document"):
            rows = [
                t["phrasing"]
                for t in self.draft["task_specs"]
                if t["split_candidate"] == "validation"
                and t["phrasing"]["phrase_context"] == context
            ]
            self.assertEqual(
                {p["phrasing_novelty"] for p in rows},
                {"train_seen", "recipient_novel", "reference_novel", "both_novel"},
            )
            self.assertEqual(
                {p["reference_sense"] for p in rows},
                {
                    "payer_account",
                    "reconciliation_ledger",
                    "transaction_history",
                    "receipt_archive",
                },
            )

    def test_target_position_varies_and_ids_must_be_matched(self) -> None:
        for rule, expected in (("UN", 2), ("UI", 3), ("D1M", 3), ("D2", 2)):
            tasks = [t for t in self.draft["task_specs"] if t["recipient_rule"] == rule]
            self.assertEqual({t["target_position"] for t in tasks}, set(range(expected)))
        for c in self.draft["condition_specs"]:
            if c["recipient_rule"] == "D1M":
                body = c["documents"][0]["content"]
                self.assertEqual(body.count("| open"), 3)
                self.assertNotIn("| settled", body)
            if c["recipient_rule"] == "D2":
                self.assertNotIn("no account on file", c["documents"][1]["content"])

    def test_validation_rejects_document_account_leak(self) -> None:
        broken = copy.deepcopy(self.draft)
        row = next(c for c in broken["condition_specs"] if c["recipient_rule"] == "D1")
        row["user_instruction"] += " " + row["expected_send_money"]["arguments"]["recipient"]
        with self.assertRaises(ValueError):
            validate_draft(broken)

    def test_validation_rejects_family_crossing_splits(self) -> None:
        broken = copy.deepcopy(self.draft)
        broken["task_specs"][0]["split_candidate"] = "validation"
        with self.assertRaises(ValueError):
            validate_draft(broken)

    def test_validation_rejects_broken_labels(self) -> None:
        broken = copy.deepcopy(self.draft)
        broken["condition_specs"][2]["argument_present"] = {k: 0 for k in ACCOUNTS}
        with self.assertRaises(ValueError):
            validate_draft(broken)

    def test_validation_rejects_role_swap_beyond_account(self) -> None:
        broken = copy.deepcopy(self.draft)
        row = next(c for c in broken["condition_specs"] if c["condition_variant"] == "ry")
        row["documents"][0]["content"] += "\nNote: urgent"
        with self.assertRaises(ValueError):
            validate_draft(broken)

    def test_generation_is_deterministic(self) -> None:
        self.assertEqual(build_draft(), self.draft)


if __name__ == "__main__":
    unittest.main()
