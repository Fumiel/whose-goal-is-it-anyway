"""Canonical JSON representation for counterfactual tool calls."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class CharacterSpan:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("character span must be non-empty and ordered")


@dataclass(frozen=True)
class CanonicalToolCall:
    text: str
    tool_name_span: CharacterSpan
    argument_spans: dict[str, CharacterSpan]


def serialize_tool_call(name: str, arguments: Mapping[str, Any]) -> CanonicalToolCall:
    """Serialize one call deterministically while retaining exact value spans."""

    if not name:
        raise ValueError("tool name cannot be empty")
    pieces = ['{"name":']
    name_text = _json(name)
    name_start = sum(map(len, pieces))
    pieces.append(name_text)
    name_span = CharacterSpan(name_start, name_start + len(name_text))
    pieces.append(',"arguments":{')

    argument_spans: dict[str, CharacterSpan] = {}
    for index, key in enumerate(sorted(arguments)):
        if index:
            pieces.append(",")
        pieces.append(_json(key))
        pieces.append(":")
        value_text = _json(arguments[key])
        value_start = sum(map(len, pieces))
        pieces.append(value_text)
        argument_spans[key] = CharacterSpan(value_start, value_start + len(value_text))
    pieces.append("}}")
    return CanonicalToolCall("".join(pieces), name_span, argument_spans)
