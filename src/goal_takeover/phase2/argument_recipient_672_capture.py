"""Canonical exposed inputs for the mixed-source recipient probe collection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from goal_takeover.instrumentation.token_positions import overlapping_token_indices

POSITION_RULE_VERSION = "argument_recipient_672_tend_assistant_v1"


@dataclass(frozen=True)
class CanonicalHistory:
    """One user prefix followed by each verified native read result in order."""

    snapshots: tuple[tuple[dict[str, Any], ...], ...]
    read_paths: tuple[str, ...]


def build_canonical_history(
    session: Any, task: dict[str, Any], condition: dict[str, Any]
) -> CanonicalHistory:
    """Execute declared reads only; never generate or infer the recipient call."""
    messages: list[dict[str, Any]] = list(session.initial_messages)
    if len(messages) != 1 or messages[0] != {
        "role": "user",
        "content": condition["user_instruction"],
    }:
        raise ValueError("native session user prompt differs from condition")
    snapshots = [tuple(messages)]
    paths = []
    reads = task["expected_read_file_calls"]
    if len(reads) != len(condition["documents"]):
        raise ValueError("read count and condition documents differ")
    for index, (call, document) in enumerate(zip(reads, condition["documents"], strict=True)):
        path = call["arguments"]["file_path"]
        if call["name"] != "read_file" or path != document["path"]:
            raise ValueError("canonical read path differs from condition document")
        call_id = f"canonical_read_{index}"
        result = session.execute_tool("read_file", call["arguments"], call_id=call_id)
        if result.error is not None or document["content"] not in result.content:
            raise ValueError(f"canonical native read did not expose declared document: {path}")
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {"name": "read_file", "arguments": call["arguments"]},
                    }
                ],
            }
        )
        messages.append(
            {
                "role": "tool",
                "name": "read_file",
                "tool_call_id": call_id,
                "content": result.content,
                "error": None,
                "untrusted": True,
            }
        )
        paths.append(path)
        snapshots.append(tuple(messages))
    return CanonicalHistory(tuple(snapshots), tuple(paths))


def select_canonical_position(
    backend: Any, history: CanonicalHistory, condition: dict[str, Any]
) -> tuple[Any, dict[str, Any]]:
    """Choose the declared exposure boundary and exact last prompt token."""
    exposure = condition["exposure"]
    account = condition["expected_send_money"]["arguments"]["recipient"]
    if (
        history.read_paths != tuple(path for path in exposure["after_tool_results_for"])
        and exposure["source_role"] != "user_instruction"
    ):
        raise ValueError("canonical read history differs from declared exposure")
    selected_index = 0 if exposure["source_role"] == "user_instruction" else len(history.read_paths)
    if selected_index >= len(history.snapshots):
        raise ValueError("selected exposure snapshot is missing")
    for index, messages in enumerate(history.snapshots[:selected_index]):
        if account in backend.serialize(messages).text:
            raise ValueError(f"recipient account leaked before selected boundary: {index}")
    prefix = backend.serialize(history.snapshots[selected_index])
    if prefix.boundary.value != exposure["boundary"]:
        raise ValueError("serialized boundary differs from exposure declaration")
    if prefix.text.count(account) != 1:
        raise ValueError("recipient account must appear exactly once at selected boundary")
    start = prefix.text.index(account)
    indices = overlapping_token_indices(prefix.offsets, start=start, end=start + len(account))
    if not indices:
        raise ValueError("recipient account has no aligned tokens")
    main_index = len(prefix.token_ids) - 1
    position = {
        "position_rule_version": POSITION_RULE_VERSION,
        "name": "Tend_assistant",
        "boundary": prefix.boundary.value,
        "prefix_id": prefix.prefix_id,
        "token_index": main_index,
        "token_id": prefix.token_ids[main_index],
        "recipient_last_token_index": indices[-1],
        "recipient_last_token_id": prefix.token_ids[indices[-1]],
        "recipient_token_indices": list(indices),
        "recipient_token_ids": [prefix.token_ids[i] for i in indices],
        "source_role": exposure["source_role"],
        "read_paths": list(history.read_paths),
    }
    return prefix, position
