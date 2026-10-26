"""Audit input excludes prior machine labels while preserving raw evidence."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from goal_takeover.phase2.argument_recipient_672_audit_packet import build_audit_packet

DRAFT = json.loads(Path("data/templates/phase2_argument_recipient_672_draft.json").read_text())


class AuditPacketTest(unittest.TestCase):
    def test_omits_automatic_judgments(self) -> None:
        condition = dict(DRAFT["condition_specs"][0], condition_id="synthetic-condition")
        run = {
            "status": "completed",
            "capture_role": "actual_behavior_and_transfer",
            "condition_id": "synthetic-condition",
            "run_id": "synthetic-run",
            "stop_reason": "final_answer",
            "final_answer": "Done",
            "strict_evaluation": {"user_task_success": True},
            "native_evaluation": {"user_task_success": False},
        }
        packet = build_audit_packet(
            run,
            condition,
            messages=[{"role": "user", "content": condition["user_instruction"]}],
            generations=[{"raw_text": "Done", "tool_calls": []}],
            tool_events=[],
            initial_state={},
            final_state={},
        )
        self.assertNotIn("strict_evaluation", packet)
        self.assertNotIn("native_evaluation", packet)
        self.assertEqual(packet["run_id"], "synthetic-run")
        self.assertTrue(packet["required_reads"])


if __name__ == "__main__":
    unittest.main()
