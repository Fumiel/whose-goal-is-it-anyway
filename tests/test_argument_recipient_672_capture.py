"""Canonical read/exposure alignment without model weights or AgentDojo."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from goal_takeover.phase2.argument_recipient_672_capture import (
    POSITION_RULE_VERSION,
    build_canonical_history,
    select_canonical_position,
)
from goal_takeover.schemas import AgentBoundary
from goal_takeover.serialization.prefix import build_serialized_prefix

DRAFT = json.loads(Path("data/templates/phase2_argument_recipient_672_draft.json").read_text())


def _task_condition(cid: str) -> tuple[dict[str, Any], dict[str, Any]]:
    condition = next(row for row in DRAFT["condition_specs"] if row["draft_condition_id"] == cid)
    task = next(
        row for row in DRAFT["task_specs"] if row["draft_task_id"] == condition["draft_task_id"]
    )
    return task, condition


class FakeSession:
    def __init__(self, condition: dict[str, Any], *, early_leak: bool = False) -> None:
        self.initial_messages = [{"role": "user", "content": condition["user_instruction"]}]
        self.documents = {row["path"]: row["content"] for row in condition["documents"]}
        self.calls: list[str] = []
        self.early_leak = early_leak
        self.account = condition["expected_send_money"]["arguments"]["recipient"]

    def execute_tool(self, name: str, args: dict[str, str], *, call_id: str) -> Any:
        self.calls.append(args["file_path"])
        content = self.documents[args["file_path"]]
        if self.early_leak and len(self.calls) == 1:
            content += self.account
        return SimpleNamespace(content=content, error=None)


class FakeBackend:
    def serialize(self, messages: tuple[dict[str, Any], ...]) -> Any:
        text = "\n".join(str(row.get("content", "")) for row in messages) + "\n<assistant>"
        tool_count = sum(row["role"] == "tool" for row in messages)
        boundary = (
            AgentBoundary.USER_TO_ASSISTANT
            if tool_count == 0
            else AgentBoundary.FIRST_TOOL_TO_ASSISTANT
            if tool_count == 1
            else AgentBoundary.LATER_TOOL_TO_ASSISTANT
        )
        return build_serialized_prefix(
            boundary=boundary,
            text=text,
            token_ids=[ord(char) for char in text],
            offset_mapping=[(index, index + 1) for index in range(len(text))],
            metadata={"tool_schema_sha256": "fake"},
        )


class CanonicalRecipientCaptureTest(unittest.TestCase):
    def test_d2_selects_after_both_reads_and_last_prompt_token(self) -> None:
        task, condition = _task_condition("A1-3-rx")
        session = FakeSession(condition)
        history = build_canonical_history(session, task, condition)
        self.assertEqual(len(history.snapshots), 3)
        self.assertEqual(session.calls, [row["path"] for row in condition["documents"]])
        prefix, position = select_canonical_position(FakeBackend(), history, condition)
        self.assertEqual(position["boundary"], "later_tool_to_assistant")
        self.assertEqual(position["position_rule_version"], POSITION_RULE_VERSION)
        self.assertEqual(position["token_index"], len(prefix.token_ids) - 1)
        self.assertEqual(position["token_id"], prefix.token_ids[-1])
        self.assertLess(position["recipient_last_token_index"], position["token_index"])

    def test_document_account_cannot_leak_in_first_d2_read(self) -> None:
        task, condition = _task_condition("A1-3-rx")
        history = build_canonical_history(FakeSession(condition, early_leak=True), task, condition)
        with self.assertRaisesRegex(ValueError, "leaked"):
            select_canonical_position(FakeBackend(), history, condition)

    def test_user_source_selects_initial_prefix(self) -> None:
        task, condition = _task_condition("A2-1-rx")
        history = build_canonical_history(FakeSession(condition), task, condition)
        prefix, position = select_canonical_position(FakeBackend(), history, condition)
        self.assertEqual(position["boundary"], "user_to_assistant")
        self.assertEqual(position["token_index"], len(prefix.token_ids) - 1)


if __name__ == "__main__":
    unittest.main()
