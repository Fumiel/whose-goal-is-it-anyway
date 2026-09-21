"""Qwen3-native tool-call continuation serialization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from goal_takeover.serialization.canonical import CanonicalToolCall, CharacterSpan


def serialize_qwen_tool_call(name: str, arguments: Mapping[str, Any]) -> CanonicalToolCall:
    """Build the exact assistant continuation expected by the Qwen3 chat template."""

    if not name:
        raise ValueError("tool name cannot be empty")
    arguments_text = json.dumps(
        dict(arguments), ensure_ascii=False, sort_keys=True, separators=(", ", ": ")
    )
    payload = f'{{"name": {json.dumps(name)}, "arguments": {arguments_text}}}'
    text = f"<tool_call>\n{payload}\n</tool_call><|im_end|>"

    name_text = json.dumps(name)
    name_start = text.index(name_text)
    argument_spans: dict[str, CharacterSpan] = {}
    search_start = text.index(arguments_text)
    for key in sorted(arguments):
        key_text = json.dumps(str(key), ensure_ascii=False)
        key_start = text.index(key_text, search_start)
        colon = text.index(":", key_start + len(key_text))
        value_text = json.dumps(
            arguments[key], ensure_ascii=False, sort_keys=True, separators=(", ", ": ")
        )
        value_start = text.index(value_text, colon + 1)
        argument_spans[key] = CharacterSpan(value_start, value_start + len(value_text))
        search_start = value_start + len(value_text)
    return CanonicalToolCall(
        text=text,
        tool_name_span=CharacterSpan(name_start, name_start + len(name_text)),
        argument_spans=argument_spans,
    )
