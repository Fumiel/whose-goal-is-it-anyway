"""Exact serialized-prefix records shared by runner instrumentation and scoring."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from goal_takeover.schemas import AgentBoundary


@dataclass(frozen=True)
class TokenOffset:
    token_index: int
    token_id: int
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.token_index < 0 or self.token_id < 0:
            raise ValueError("token index and ID must be non-negative")
        if self.start < 0 or self.end < self.start:
            raise ValueError("token offsets must be ordered")


@dataclass(frozen=True)
class SerializedPrefix:
    boundary: AgentBoundary
    text: str
    token_ids: tuple[int, ...]
    offsets: tuple[TokenOffset, ...]
    prefix_id: str
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.token_ids:
            raise ValueError("serialized prefix must contain at least one token")
        if len(self.token_ids) != len(self.offsets):
            raise ValueError("token IDs and offsets must have equal length")
        for expected, offset in enumerate(self.offsets):
            if offset.token_index != expected or offset.token_id != self.token_ids[expected]:
                raise ValueError("offset records must align exactly with token IDs")

    def assert_same_tokens(self, other_token_ids: Sequence[int], *, consumer: str) -> None:
        if tuple(int(value) for value in other_token_ids) != self.token_ids:
            raise ValueError(f"{consumer} prefix tokens do not match serialized prefix")


def stable_prefix_id(token_ids: Sequence[int], metadata: Mapping[str, Any]) -> str:
    """Hash exact tokens plus serialization metadata into a stable prefix ID."""

    payload = {
        "token_ids": [int(value) for value in token_ids],
        "metadata": dict(metadata),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "prefix_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def build_serialized_prefix(
    *,
    boundary: AgentBoundary,
    text: str,
    token_ids: Sequence[int],
    offset_mapping: Sequence[tuple[int, int]],
    metadata: Mapping[str, Any],
) -> SerializedPrefix:
    """Construct and validate the one prefix record every consumer must reuse."""

    ids = tuple(int(value) for value in token_ids)
    if len(ids) != len(offset_mapping):
        raise ValueError("token IDs and offset mapping must have equal length")
    offsets = tuple(
        TokenOffset(index, token_id, int(span[0]), int(span[1]))
        for index, (token_id, span) in enumerate(zip(ids, offset_mapping, strict=True))
    )
    metadata_dict = dict(metadata)
    return SerializedPrefix(
        boundary=boundary,
        text=text,
        token_ids=ids,
        offsets=offsets,
        prefix_id=stable_prefix_id(ids, metadata_dict),
        metadata=metadata_dict,
    )


def serialize_huggingface_prefix(
    tokenizer: Any,
    messages: Sequence[Mapping[str, Any]],
    *,
    boundary: AgentBoundary,
    tokenizer_revision: str,
    chat_template_sha256: str,
) -> SerializedPrefix:
    """Serialize with a verified Hugging Face chat template and fast offsets."""

    text = tokenizer.apply_chat_template(list(messages), tokenize=False, add_generation_prompt=True)
    encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    if "offset_mapping" not in encoded:
        raise ValueError("selected tokenizer must provide verified offset mapping")
    metadata = {
        "serializer": "huggingface_chat_template",
        "tokenizer_revision": tokenizer_revision,
        "chat_template_sha256": chat_template_sha256,
        "add_generation_prompt": True,
    }
    return build_serialized_prefix(
        boundary=boundary,
        text=text,
        token_ids=encoded["input_ids"],
        offset_mapping=encoded["offset_mapping"],
        metadata=metadata,
    )
