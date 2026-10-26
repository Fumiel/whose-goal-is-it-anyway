"""Native execution contract for the condition-specific 672 draft documents."""

from __future__ import annotations

import json
import unittest
from importlib.util import find_spec
from pathlib import Path

from goal_takeover.datasets.argument_recipient_672_native import (
    create_session,
    evaluate_condition,
    native_preflight,
    task_and_condition,
    validate_declarations,
)
from goal_takeover.pilot.evaluation import RecordingSession, state_document

DRAFT = json.loads(Path("data/templates/phase2_argument_recipient_672_draft.json").read_text())


class ArgumentRecipient672NativeTest(unittest.TestCase):
    @unittest.skipUnless(find_spec("agentdojo"), "AgentDojo research dependency unavailable")
    def test_role_swap_installs_condition_specific_documents(self) -> None:
        for cid in ("A1-1-rx", "A1-1-ry_ref_x"):
            _, condition = task_and_condition(DRAFT, cid)
            session = create_session(DRAFT, cid)
            self.assertEqual(session.initial_messages[0]["content"], condition["user_instruction"])
            for document in condition["documents"]:
                self.assertEqual(
                    session.environment.filesystem.files[document["path"]], document["content"]
                )
            self.assertIsNone(session.injection_task)

    @unittest.skipUnless(find_spec("agentdojo"), "AgentDojo research dependency unavailable")
    def test_d1_d1m_d2_native_controls(self) -> None:
        result = native_preflight(DRAFT, ["A1-1-rx", "A1-2-rx_ref_y", "A1-3-ry_ref_x"])
        self.assertEqual(result["condition_count"], 3)
        self.assertEqual(result["control_count"], 12)

    @unittest.skipUnless(find_spec("agentdojo"), "AgentDojo research dependency unavailable")
    def test_d2_requires_second_read_before_transfer(self) -> None:
        cid = "A1-3-rx"
        task, condition = task_and_condition(DRAFT, cid)
        session = create_session(DRAFT, cid)
        recorder = RecordingSession(session)
        initial = state_document(session.environment)
        for call in (task["expected_read_file_calls"][0], condition["expected_send_money"]):
            self.assertIsNone(recorder.execute(call["name"], call["arguments"]).error)
        result = evaluate_condition(
            task,
            condition,
            initial,
            state_document(session.environment),
            recorder.events,
            require_content=True,
        )
        self.assertFalse(result["user_task_success"])
        self.assertFalse(result["reads_before_transfer"])

    def test_rejects_document_path_mismatch(self) -> None:
        changed = json.loads(json.dumps(DRAFT))
        changed["condition_specs"][0]["expected_tool_sequence"][0]["arguments"]["file_path"] = "bad"
        with self.assertRaises(ValueError):
            validate_declarations(changed)

    def test_accepts_frozen_declaration_and_rejects_unknown_status(self) -> None:
        frozen = json.loads(
            Path("data/templates/phase2_argument_recipient_672_v1.json").read_text()
        )
        validate_declarations(frozen)
        frozen["status"] = "unknown"
        with self.assertRaisesRegex(ValueError, "status"):
            validate_declarations(frozen)


if __name__ == "__main__":
    unittest.main()
