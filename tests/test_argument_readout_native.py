"""Native Banking registration and strict task evaluation for the 96-condition draft."""

import copy
import importlib.util
import unittest
from pathlib import Path

from goal_takeover.datasets.argument_readout_evaluation import (
    evaluate_calls,
    load_draft,
    task_and_condition,
    validate_execution_declarations,
)

DRAFT = Path("data/templates/phase2_argument_readout_96_draft.json")


class ArgumentReadoutEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.draft = load_draft(DRAFT)

    def test_all_declarations_match_the_execution_contract(self) -> None:
        validate_execution_declarations(self.draft)
        for row in self.draft["condition_specs"]:
            task, condition = task_and_condition(self.draft, row["draft_condition_id"])
            self.assertEqual(condition["expected_tool_sequence"][-1]["name"], "send_money")
            self.assertEqual(len(task["documents"]) + 1, len(condition["expected_tool_sequence"]))

    def test_rejects_conflicting_document_path_and_call_sequence(self) -> None:
        broken = copy.deepcopy(self.draft)
        broken["task_specs"][1]["documents"][0]["path"] = broken["task_specs"][0]["documents"][0][
            "path"
        ]
        with self.assertRaises(ValueError):
            validate_execution_declarations(broken)
        broken = copy.deepcopy(self.draft)
        broken["condition_specs"][0]["expected_tool_sequence"] = []
        with self.assertRaises(ValueError):
            validate_execution_declarations(broken)

    def test_ordered_reads_and_exact_state_are_required(self) -> None:
        task, condition = task_and_condition(self.draft, "INV-4-rx")
        initial = {
            "bank_account": {"iban": "sender", "transactions": []},
            "user_account": {"name": "original"},
        }
        expected = condition["expected_send_money"]["arguments"]
        row = {**expected, "id": 1, "sender": "sender", "recurring": False}
        final = copy.deepcopy(initial)
        final["bank_account"]["transactions"].append(row)
        reads = [
            {
                "name": "read_file",
                "arguments": {"file_path": d["path"]},
                "content": d["content"],
                "error": None,
            }
            for d in task["documents"]
        ]
        send = {"name": "send_money", "arguments": expected, "error": None}
        self.assertTrue(
            evaluate_calls(task, condition, initial, final, [*reads, send], require_content=True)[
                "user_task_success"
            ]
        )
        for calls, state in (
            ([*reversed(reads), send], final),
            ([reads[0], send, reads[1]], final),
            ([{**reads[0], "content": ""}, reads[1], send], final),
            ([*reads, send, send], final),
            ([*reads, send], {**final, "user_account": {"name": "changed"}}),
        ):
            self.assertFalse(
                evaluate_calls(task, condition, initial, state, calls, require_content=True)[
                    "user_task_success"
                ]
            )


@unittest.skipUnless(importlib.util.find_spec("agentdojo"), "AgentDojo is not installed")
class ArgumentReadoutNativeTests(unittest.TestCase):
    def test_registered_task_and_real_transfer(self) -> None:
        from agentdojo.task_suite.load_suites import get_suite

        from goal_takeover.environments.argument_readout import create_session
        from goal_takeover.pilot.evaluation import RecordingSession, state_document

        draft = load_draft(DRAFT)
        original = get_suite("v1.2.2", "banking")
        for cid in ("INV-1-rx", "INV-1-ry_ref_x"):
            task, condition = task_and_condition(draft, cid)
            session = create_session(draft, cid)
            self.assertIsNot(session.suite, original)
            self.assertNotIn(session.user_task.ID, original.user_tasks)
            self.assertIsNone(session.injection_task)
            self.assertEqual(session.initial_messages[0]["content"], condition["user_instruction"])
            recorder = RecordingSession(session)
            initial = state_document(session.environment)
            for call in condition["expected_tool_sequence"]:
                self.assertIsNone(recorder.execute(call["name"], call["arguments"]).error)
            final = state_document(session.environment)
            self.assertTrue(
                session.user_task.utility("", session.pre_environment, session.environment)
            )
            self.assertTrue(session.evaluate(None).user_task_success)
            self.assertTrue(
                evaluate_calls(
                    task, condition, initial, final, recorder.events, require_content=True
                )["user_task_success"]
            )


if __name__ == "__main__":
    unittest.main()
