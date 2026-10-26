"""Evidence-only packet for the declared Codex audit of actual runs."""

from __future__ import annotations

from typing import Any


def build_audit_packet(
    run: dict[str, Any],
    condition: dict[str, Any],
    *,
    messages: list[dict[str, Any]],
    generations: list[dict[str, Any]],
    tool_events: list[dict[str, Any]],
    initial_state: dict[str, Any],
    final_state: dict[str, Any],
) -> dict[str, Any]:
    """Omit automatic judgments so the model checks the raw trace itself."""
    if (
        run.get("status") != "completed"
        or run.get("capture_role") != "actual_behavior_and_transfer"
        or run.get("condition_id") != condition.get("condition_id")
        or not isinstance(generations, list)
        or not isinstance(tool_events, list)
    ):
        raise ValueError("audit packet requires a complete matching actual run")
    return {
        "schema_version": 1,
        "condition_id": condition["condition_id"],
        "run_id": run["run_id"],
        "user_instruction": condition["user_instruction"],
        "declared_documents": condition["documents"],
        "required_reads": [
            call for call in condition["expected_tool_sequence"] if call["name"] == "read_file"
        ],
        "expected_send_money": condition["expected_send_money"],
        "stop_reason": run["stop_reason"],
        "final_answer": run["final_answer"],
        "messages": messages,
        "generations": generations,
        "tool_events": tool_events,
        "initial_state": initial_state,
        "final_state": final_state,
    }
