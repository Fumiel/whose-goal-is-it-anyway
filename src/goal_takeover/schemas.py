"""Core, dependency-free records shared across experiment components."""

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


class ProcessingStage(StrEnum):
    """Checkpoints at which model internals are compared."""

    AFTER_USER_INSTRUCTION = "after_user_instruction"
    BEFORE_EXTERNAL_TOOL_CALL = "before_external_tool_call"
    AFTER_TOOL_OUTPUT = "after_tool_output"
    BEFORE_NEXT_ACTION = "before_next_action"
    BEFORE_FINAL_TOOL_CALL = "before_final_tool_call"


@dataclass(frozen=True)
class ConditionRecord:
    """Stable metadata describing an experimental input condition."""

    condition_id: str
    task_template_id: str
    variant_id: str
    user_goal_category: str
    expected_legitimate_tool: str
    has_attack: bool
    attack_template_id: str | None = None
    attack_goal_category: str | None = None
    expected_attack_tool: str | None = None
    paraphrase_family_id: str | None = None
    pair_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.has_attack and not self.attack_template_id:
            raise ValueError("attack_template_id is required when has_attack is true")
        if not self.has_attack and any(
            value is not None
            for value in (
                self.attack_template_id,
                self.attack_goal_category,
                self.expected_attack_tool,
            )
        ):
            raise ValueError("clean conditions cannot contain attack-specific fields")


@dataclass(frozen=True)
class StagePosition:
    """The exact token used to represent one processing stage."""

    stage: ProcessingStage
    token_index: int
    token_id: int
    sequence_length: int
    selection_rule: str = "last_token"

    def __post_init__(self) -> None:
        if self.sequence_length <= 0:
            raise ValueError("sequence_length must be positive")
        if not 0 <= self.token_index < self.sequence_length:
            raise ValueError("token_index is outside the sequence")
