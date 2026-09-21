"""Model-agnostic control loop for a tool-using agent."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from goal_takeover.schemas import AgentBoundary

Message = dict[str, Any]


@dataclass(frozen=True)
class AgentAction:
    """A normalized action returned by a model backend."""

    kind: Literal["tool", "final"]
    content: str = ""
    tool_name: str | None = None
    tool_arguments: Mapping[str, Any] = field(default_factory=dict)
    tool_call_id: str | None = None
    raw_text: str | None = None
    assistant_message: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.kind == "tool" and not self.tool_name:
            raise ValueError("tool actions require tool_name")


class AgentBackend(Protocol):
    """Adapter implemented by the selected model/tool-calling format."""

    def next_action(self, messages: Sequence[Message]) -> AgentAction: ...


Tool = Callable[..., Any]
BoundaryCallback = Callable[[AgentBoundary, Sequence[Message]], None]


@dataclass
class AgentRun:
    messages: list[Message]
    actions: list[AgentAction]
    final_answer: str | None
    stop_reason: str


@dataclass(frozen=True)
class ToolExecution:
    """One tool result with an error kept separate from its display content."""

    content: str
    error: str | None = None


def _assistant_message(action: AgentAction) -> Message:
    if action.assistant_message is not None:
        return dict(action.assistant_message)
    assert action.tool_name is not None
    return {
        "role": "assistant",
        "content": action.content,
        "tool_calls": [
            {
                "id": action.tool_call_id,
                "type": "function",
                "function": {
                    "name": action.tool_name,
                    "arguments": dict(action.tool_arguments),
                },
            }
        ],
    }


def run_agent(
    backend: AgentBackend,
    initial_messages: Sequence[Message],
    tools: Mapping[str, Tool],
    *,
    max_steps: int = 8,
    on_boundary: BoundaryCallback | None = None,
) -> AgentRun:
    """Run a bounded loop while preserving tool output as untrusted role data.

    The callback fires immediately before each assistant generation. Model
    adapters must serialize the supplied messages once and reuse that exact
    prefix for generation, activation capture, and candidate scoring.
    """

    if max_steps <= 0:
        raise ValueError("max_steps must be positive")

    messages = [dict(message) for message in initial_messages]
    actions: list[AgentAction] = []
    for _ in range(max_steps):
        if on_boundary:
            tool_returns = sum(message.get("role") == "tool" for message in messages)
            if tool_returns == 0:
                boundary = AgentBoundary.USER_TO_ASSISTANT
            elif tool_returns == 1:
                boundary = AgentBoundary.FIRST_TOOL_TO_ASSISTANT
            else:
                boundary = AgentBoundary.LATER_TOOL_TO_ASSISTANT
            on_boundary(boundary, tuple(dict(message) for message in messages))

        action = backend.next_action(messages)
        actions.append(action)
        if action.kind == "final":
            return AgentRun(messages, actions, action.content, "final_answer")

        assert action.tool_name is not None
        if action.tool_name not in tools:
            return AgentRun(messages, actions, None, "unknown_tool")

        tool = tools[action.tool_name]
        call_with_id = getattr(tool, "call_with_id", None)
        if callable(call_with_id):
            result = call_with_id(dict(action.tool_arguments), action.tool_call_id)
        else:
            result = tool(**dict(action.tool_arguments))
        execution = result if isinstance(result, ToolExecution) else ToolExecution(str(result))
        messages.append(_assistant_message(action))
        messages.append(
            {
                "role": "tool",
                "name": action.tool_name,
                "tool_call_id": action.tool_call_id,
                "content": execution.content,
                "error": execution.error,
                "untrusted": True,
            }
        )
    return AgentRun(messages, actions, None, "max_steps")
