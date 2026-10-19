"""Model-free controls for the custom two-document development task."""

import copy
import unittest
from pathlib import Path

from goal_takeover.datasets.two_document_payment import (
    evaluate_events,
    load_spec,
    materialize,
    model_free_preflight,
    simulate_events,
    validate_spec,
)

SPEC = Path("data/templates/phase2_two_document_payment_v1.json")
SPEC_V2 = Path("data/templates/phase2_two_document_payment_v2.json")


class TwoDocumentPaymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = load_spec(SPEC)

    def test_all_matched_roles_and_controls(self) -> None:
        report = model_free_preflight(self.spec)
        self.assertEqual(report["status"], "synthetic_model_free_controls_passed")
        self.assertEqual(len(report["condition_ids"]), 5)
        self.assertEqual(report["controls_per_condition"], 6)
        self.assertEqual(len(set(report["condition_ids"].values())), 5)
        for variant in report["condition_ids"]:
            condition = materialize(self.spec, variant)
            self.assertEqual(condition["condition_id"], report["condition_ids"][variant])
            self.assertEqual(
                condition["user_instruction"].count(self.spec["matched_content"])
                + sum(
                    text.count(self.spec["matched_content"])
                    for text in condition["documents"].values()
                ),
                1,
            )

    def test_alternative_recipient_is_not_authorized_in_tool_output(self) -> None:
        condition = materialize(self.spec, "tool_output")
        calls = [
            self.spec["calls"]["read_purchase_order"],
            self.spec["calls"]["read_payee_registry"],
            self.spec["calls"]["attacker"],
        ]
        events = [{**call, "error": None} for call in calls]
        result = evaluate_events(self.spec, condition, events, simulate_events(self.spec, events))
        self.assertFalse(result["user_task_success"])
        self.assertTrue(result["attack_candidate_occurred"])

    def test_user_instruction_authorizes_same_recipient(self) -> None:
        condition = materialize(self.spec, "user_instruction")
        calls = [
            self.spec["calls"]["read_purchase_order"],
            self.spec["calls"]["read_payee_registry"],
            self.spec["calls"]["attacker"],
        ]
        events = [{**call, "error": None} for call in calls]
        result = evaluate_events(self.spec, condition, events, simulate_events(self.spec, events))
        self.assertTrue(result["user_task_success"])
        self.assertTrue(result["attack_candidate_occurred"])
        self.assertFalse(condition["has_attack"])

    def test_state_mismatch_rejects_success(self) -> None:
        condition = materialize(self.spec, "tool_output")
        calls = [
            self.spec["calls"]["read_purchase_order"],
            self.spec["calls"]["read_payee_registry"],
            self.spec["calls"]["legitimate"],
        ]
        events = [{**call, "error": None} for call in calls]
        self.assertFalse(
            evaluate_events(self.spec, condition, events, {"transactions": []})["user_task_success"]
        )

    def test_schema_rejects_extra_candidate_difference(self) -> None:
        altered = copy.deepcopy(self.spec)
        altered["calls"]["attacker"]["arguments"]["amount"] = 99.0
        with self.assertRaisesRegex(ValueError, "only recipient"):
            validate_spec(altered)

    def test_v2_discloses_both_exact_file_paths_to_every_role(self) -> None:
        revised = load_spec(SPEC_V2)
        for document in ("purchase_order", "payee_registry"):
            path = revised[document]["path"]
            self.assertEqual(revised["instruction_base"].count(path), 1)
            for row in revised["conditions"]:
                self.assertIn(path, materialize(revised, row["variant_id"])["user_instruction"])
        self.assertNotEqual(
            materialize(self.spec, "tool_output")["condition_id"],
            materialize(revised, "tool_output")["condition_id"],
        )
        altered = copy.deepcopy(revised)
        altered["instruction_base"] = altered["instruction_base"].replace(
            revised["payee_registry"]["path"], "approved-payees registry"
        )
        with self.assertRaisesRegex(ValueError, "payee_registry path"):
            validate_spec(altered)


if __name__ == "__main__":
    unittest.main()
