"""Model-agnostic control loop for a tool-using agent."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from goal_takeover.schemas import ProcessingStage

Message = dict[str, Any]


@dataclass(frozen=True)
class AgentAction:
    """A normalized action returned by a model backend."""

    kind: Literal["tool", "final"]
    content: str = ""
    tool_name: str | None = None
    tool_arguments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind == "tool" and not self.tool_name:
            raise ValueError("tool actions require tool_name")


class AgentBackend(Protocol):
    """Adapter implemented by the selected model/tool-calling format."""

    def next_action(self, messages: Sequence[Message]) -> AgentAction: ...


Tool = Callable[..., Any]
StageCallback = Callable[[ProcessingStage, Sequence[Message]], None]


@dataclass
class AgentRun:
    messages: list[Message]
    actions: list[AgentAction]
    final_answer: str | None
    stop_reason: str


def run_agent(
    backend: AgentBackend,
    initial_messages: Sequence[Message],
    tools: Mapping[str, Tool],
    *,
    max_steps: int = 8,
    on_stage: StageCallback | None = None,
) -> AgentRun:
    """Run a bounded loop while preserving tool output as untrusted role data.

    The callback marks semantic stages. Model-specific adapters are responsible
    for capturing activations at the exact forward pass and token position.
    """

    if max_steps <= 0:
        raise ValueError("max_steps must be positive")

    messages = [dict(message) for message in initial_messages]
    actions: list[AgentAction] = []
    if on_stage:
        on_stage(ProcessingStage.AFTER_USER_INSTRUCTION, messages)

    for _ in range(max_steps):
        if on_stage:
            stage = (
                ProcessingStage.BEFORE_EXTERNAL_TOOL_CALL
                if not actions
                else ProcessingStage.BEFORE_NEXT_ACTION
            )
            on_stage(stage, messages)

        action = backend.next_action(messages)
        actions.append(action)
        if action.kind == "final":
            return AgentRun(messages, actions, action.content, "final_answer")

        assert action.tool_name is not None
        if action.tool_name not in tools:
            return AgentRun(messages, actions, None, "unknown_tool")

        if on_stage and len(actions) > 1:
            on_stage(ProcessingStage.BEFORE_FINAL_TOOL_CALL, messages)

        result = tools[action.tool_name](**dict(action.tool_arguments))
        messages.append(
            {
                "role": "assistant",
                "tool_call": {
                    "name": action.tool_name,
                    "arguments": dict(action.tool_arguments),
                },
            }
        )
        messages.append(
            {
                "role": "tool",
                "name": action.tool_name,
                "content": str(result),
                "untrusted": True,
            }
        )
        if on_stage:
            on_stage(ProcessingStage.AFTER_TOOL_OUTPUT, messages)

    return AgentRun(messages, actions, None, "max_steps")
