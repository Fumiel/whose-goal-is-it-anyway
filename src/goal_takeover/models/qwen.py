"""Qwen3 Transformers backend for the experiment-owned agent loop."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from goal_takeover.agent.runner import AgentAction, AgentToolCall, Message
from goal_takeover.models.generation import DecodingConfig
from goal_takeover.schemas import AgentBoundary
from goal_takeover.serialization.prefix import SerializedPrefix, serialize_huggingface_prefix

_TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_THINK_PATTERN = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


class QwenToolCallParseError(ValueError):
    """Raised when a Qwen completion declares a malformed or ambiguous tool call."""

    def __init__(self, message: str, *, raw_text: str) -> None:
        super().__init__(message)
        self.raw_text = raw_text


def parse_qwen_action(text: str, *, call_id: str) -> AgentAction:
    """Parse every declared Qwen tool call in the order emitted by the model."""

    matches = list(_TOOL_CALL_PATTERN.finditer(text))
    if text.count("<tool_call>") != len(matches) or text.count("</tool_call>") != len(matches):
        raise QwenToolCallParseError("tool call tags are malformed or incomplete", raw_text=text)
    visible_text = _THINK_PATTERN.sub("", text).strip()
    if not matches:
        return AgentAction(kind="final", content=visible_text, raw_text=text)
    calls: list[AgentToolCall] = []
    for index, match in enumerate(matches):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise QwenToolCallParseError("tool call is not valid JSON", raw_text=text) from exc
        if not isinstance(payload, dict):
            raise QwenToolCallParseError("tool call payload must be an object", raw_text=text)
        name = payload.get("name")
        arguments = payload.get("arguments")
        if not isinstance(name, str) or not name:
            raise QwenToolCallParseError(
                "tool call name must be a non-empty string", raw_text=text
            )
        if not isinstance(arguments, dict):
            raise QwenToolCallParseError("tool call arguments must be an object", raw_text=text)
        current_id = call_id if index == 0 else f"{call_id}_{index}"
        calls.append(AgentToolCall(name=name, arguments=arguments, call_id=current_id))
    outside = text
    for match in reversed(matches):
        outside = outside[: match.start()] + outside[match.end() :]
    outside = outside.strip()
    outside = _THINK_PATTERN.sub("", outside).strip()
    assistant_message = {
        "role": "assistant",
        "content": outside,
        "tool_calls": [
            {
                "id": call.call_id,
                "type": "function",
                "function": {"name": call.name, "arguments": dict(call.arguments)},
            }
            for call in calls
        ],
    }
    first = calls[0]
    return AgentAction(
        kind="tool",
        content=outside,
        tool_name=first.name,
        tool_arguments=first.arguments,
        tool_call_id=first.call_id,
        tool_calls=tuple(calls),
        raw_text=text,
        assistant_message=assistant_message,
    )


def chat_template_sha256(tokenizer: Any) -> str:
    template = getattr(tokenizer, "chat_template", None)
    if not isinstance(template, str) or not template:
        raise ValueError("tokenizer must expose a non-empty chat template")
    return hashlib.sha256(template.encode("utf-8")).hexdigest()


class QwenTransformersBackend:
    """Generate actions and retain each exact prefix from one model instance."""

    def __init__(
        self,
        *,
        model: Any,
        tokenizer: Any,
        tools: Sequence[Mapping[str, Any]],
        model_revision: str,
        tokenizer_revision: str,
        decoding: DecodingConfig,
        max_context_tokens: int = 4096,
    ) -> None:
        if max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be positive")
        self.model = model
        self.tokenizer = tokenizer
        self.tools = tuple(dict(tool) for tool in tools)
        self.model_revision = model_revision
        self.tokenizer_revision = tokenizer_revision
        self.decoding = decoding
        self.max_context_tokens = max_context_tokens
        self.template_sha256 = chat_template_sha256(tokenizer)
        self.prefixes: list[SerializedPrefix] = []
        self._call_index = 0

    @staticmethod
    def _boundary(messages: Sequence[Message]) -> AgentBoundary:
        tool_returns = sum(message.get("role") == "tool" for message in messages)
        if tool_returns == 0:
            return AgentBoundary.USER_TO_ASSISTANT
        if tool_returns == 1:
            return AgentBoundary.FIRST_TOOL_TO_ASSISTANT
        return AgentBoundary.LATER_TOOL_TO_ASSISTANT

    def serialize(self, messages: Sequence[Message]) -> SerializedPrefix:
        prefix = serialize_huggingface_prefix(
            self.tokenizer,
            messages,
            boundary=self._boundary(messages),
            tokenizer_revision=self.tokenizer_revision,
            chat_template_sha256=self.template_sha256,
            tools=self.tools,
            enable_thinking=False,
            add_generation_prompt=True,
        )
        if len(prefix.token_ids) > self.max_context_tokens:
            raise ValueError(
                f"serialized prefix has {len(prefix.token_ids)} tokens, limit is "
                f"{self.max_context_tokens}"
            )
        return prefix

    def next_action(self, messages: Sequence[Message]) -> AgentAction:
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - optional research dependency
            raise RuntimeError("install research dependencies for model generation") from exc
        prefix = self.serialize(messages)
        self.prefixes.append(prefix)
        device = next(self.model.parameters()).device
        input_ids = torch.tensor([prefix.token_ids], dtype=torch.long, device=device)
        attention_mask = torch.ones_like(input_ids)
        with torch.no_grad():
            output = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                **self.decoding.as_transformers_kwargs(),
            )
        generated = output[0, input_ids.shape[1] :].tolist()
        text = self.tokenizer.decode(generated, skip_special_tokens=False)
        if self.tokenizer.eos_token and text.endswith(self.tokenizer.eos_token):
            text = text[: -len(self.tokenizer.eos_token)]
        call_id = f"call_{self._call_index:04d}"
        self._call_index += 1
        return parse_qwen_action(text, call_id=call_id)
