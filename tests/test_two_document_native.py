"""Native AgentDojo registration and state controls for the custom task."""

import importlib.util
import unittest
from pathlib import Path

from goal_takeover.datasets.two_document_native import native_preflight
from goal_takeover.datasets.two_document_payment import load_spec
from goal_takeover.environments.two_document_payment import create_session

SPEC = Path("data/templates/phase2_two_document_payment_v1.json")


@unittest.skipUnless(importlib.util.find_spec("agentdojo"), "AgentDojo is not installed")
class TwoDocumentNativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = load_spec(SPEC)

    def test_registered_suite_is_isolated_and_documents_are_readable(self) -> None:
        from agentdojo.task_suite.load_suites import get_suite

        original = get_suite("v1.2.2", "banking")
        session, condition = create_session(self.spec, "tool_output")
        self.assertIsNot(session.suite, original)
        self.assertNotIn("user_task_742", original.user_tasks)
        self.assertNotIn("injection_task_742", original.injection_tasks)
        self.assertEqual(session.user_task.ID, "user_task_742")
        self.assertEqual(session.injection_task.ID, "injection_task_742")
        for path, expected in condition["documents"].items():
            result = session.execute_tool("read_file", {"file_path": path})
            self.assertIsNone(result.error)
            self.assertIn(expected, result.content)

    def test_all_native_controls(self) -> None:
        report = native_preflight(self.spec)
        self.assertEqual(report["status"], "native_model_free_controls_passed")
        self.assertFalse(report["research_result"])
        self.assertEqual(len(report["conditions"]), 5)
        for condition in report["conditions"]:
            controls = condition["controls"]
            self.assertEqual(len(controls), 9)
            self.assertTrue(controls["authorized"]["native_user_task_success"])
            for label, outcome in controls.items():
                if label != "authorized":
                    self.assertFalse(outcome["native_user_task_success"])
                if label == "no_operation":
                    self.assertEqual(outcome["initial_state_sha256"], outcome["final_state_sha256"])
                if label == "alternative":
                    self.assertNotEqual(
                        outcome["initial_state_sha256"], outcome["final_state_sha256"]
                    )
            self.assertEqual(
                controls["authorized"]["native_attack_candidate_occurred"],
                condition["variant_id"] == "user_instruction",
            )
            self.assertEqual(
                controls["alternative"]["native_attack_candidate_occurred"],
                condition["variant_id"] != "user_instruction",
            )


if __name__ == "__main__":
    unittest.main()
