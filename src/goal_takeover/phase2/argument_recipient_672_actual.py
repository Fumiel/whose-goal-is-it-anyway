"""Select the first actually exposed assistant boundary for transfer checks."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

ACTUAL_POSITION_RULE_VERSION = "argument_recipient_672_actual_tend_assistant_v1"


def select_actual_exposed_prefix(
    prefixes: Sequence[Any],
    histories: Sequence[Sequence[dict[str, Any]]],
    condition: dict[str, Any],
) -> tuple[Any | None, dict[str, Any] | None, str | None]:
    """Use only observed document results, never an expected call or generated guess."""
    if len(prefixes) != len(histories):
        raise ValueError("actual generation prefixes and message snapshots differ")
    source = condition["exposure"]["source_role"]
    account = condition["expected_send_money"]["arguments"]["recipient"]
    for prefix, history in zip(prefixes, histories, strict=True):
        if not history or history[0] != {"role": "user", "content": condition["user_instruction"]}:
            raise ValueError("actual history user prompt differs from condition")
        if source == "user_instruction":
            exposed = account in history[0]["content"]
        else:
            tool_texts = [
                message.get("content", "") for message in history if message.get("role") == "tool"
            ]
            exposed = all(
                any(document["content"] in text for text in tool_texts)
                for document in condition["documents"]
            )
        if not exposed:
            continue
        if account not in prefix.text:
            raise ValueError("actual tool exposure differs from serialized prefix")
        index = len(prefix.token_ids) - 1
        return (
            prefix,
            {
                "position_rule_version": ACTUAL_POSITION_RULE_VERSION,
                "name": "Tend_assistant",
                "prefix_id": prefix.prefix_id,
                "boundary": prefix.boundary.value,
                "token_index": index,
                "token_id": prefix.token_ids[index],
                "source_role": source,
                "declared_boundary": condition["exposure"]["boundary"],
                "boundary_matches_canonical": prefix.boundary.value
                == condition["exposure"]["boundary"],
            },
            None,
        )
    return None, None, "declared_source_not_exposed_in_actual_trajectory"
