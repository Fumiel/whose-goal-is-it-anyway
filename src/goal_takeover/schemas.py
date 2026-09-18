"""Dependency-free records shared across experiment components."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class OutcomeGroup(StrEnum):
    """Prompt-injection outcome groups defined in the research proposal."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"


class AgentBoundary(StrEnum):
    """Serialized-prefix boundaries immediately before assistant generation."""

    USER_TO_ASSISTANT = "user_to_assistant"
    FIRST_TOOL_TO_ASSISTANT = "first_tool_to_assistant"
    LATER_TOOL_TO_ASSISTANT = "later_tool_to_assistant"


class TokenPositionName(StrEnum):
    """Within-prefix token positions used by the protocol."""

    TPRE = "Tpre"
    TPOST = "Tpost"
    TEND_TOOL = "Tend_tool"
    TEND_ASSISTANT = "Tend_assistant"


class TaskOpenness(StrEnum):
    FULLY_SPECIFIED = "fully_specified"
    PARAM_OPEN = "param_open"
    ACTION_OPEN = "action_open"


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("tool name cannot be empty")


@dataclass(frozen=True)
class MessageSpan:
    """Half-open character span inside one message's content."""

    message_index: int
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.message_index < 0:
            raise ValueError("message_index must be non-negative")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("message span must be non-empty and ordered")


@dataclass(frozen=True)
class ConditionRecord:
    """Stable metadata describing an experimental input condition."""

    condition_id: str
    task_template_id: str
    variant_id: str
    task_openness: TaskOpenness
    legitimate_call: ToolCall
    has_attack: bool
    attack_goal_id: str | None = None
    attack_style_id: str | None = None
    attack_template_id: str | None = None
    argument_slot_id: str | None = None
    attack_call: ToolCall | None = None
    injection_span: MessageSpan | None = None
    paraphrase_family_id: str | None = None
    pair_id: str | None = None
    stochastic_family_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        attack_values = (
            self.attack_goal_id,
            self.attack_style_id,
            self.attack_template_id,
            self.argument_slot_id,
            self.attack_call,
            self.injection_span,
        )
        if self.has_attack and any(value is None for value in attack_values):
            raise ValueError("attack conditions require all attack-specific fields")
        if not self.has_attack and any(value is not None for value in attack_values):
            raise ValueError("clean conditions cannot contain attack-specific fields")


@dataclass(frozen=True)
class TokenPosition:
    """Exact token selected for one protocol position."""

    name: TokenPositionName
    token_index: int
    token_id: int
    sequence_length: int
    selection_rule: str

    def __post_init__(self) -> None:
        if self.sequence_length <= 0:
            raise ValueError("sequence_length must be positive")
        if not 0 <= self.token_index < self.sequence_length:
            raise ValueError("token_index is outside the sequence")
        if self.token_id < 0:
            raise ValueError("token_id must be non-negative")
        if not self.selection_rule:
            raise ValueError("selection_rule cannot be empty")
