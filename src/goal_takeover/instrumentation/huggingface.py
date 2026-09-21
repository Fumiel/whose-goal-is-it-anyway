"""Hugging Face activation extraction tied to an exact serialized prefix."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from goal_takeover.instrumentation.activation_hooks import ResidualCapture
from goal_takeover.instrumentation.capture import ActivationRecord
from goal_takeover.serialization.prefix import SerializedPrefix


def transformer_block_names(model: Any, *, block_path: str) -> tuple[str, ...]:
    modules = dict(model.named_modules())
    if block_path not in modules:
        raise ValueError(f"transformer block path is unavailable: {block_path}")
    container = modules[block_path]
    try:
        count = len(container)
    except TypeError as exc:
        raise ValueError(
            f"transformer block path is not an indexed container: {block_path}"
        ) from exc
    if count <= 0:
        raise ValueError("transformer block container is empty")
    names = tuple(f"{block_path}.{index}" for index in range(count))
    missing = [name for name in names if name not in modules]
    if missing:
        raise ValueError(f"transformer blocks are unavailable: {', '.join(missing)}")
    return names


class HuggingFaceActivationExtractor:
    """Capture selected residual block outputs using the generation model object."""

    def __init__(self, model: Any, *, block_path: str = "model.layers") -> None:
        self.model = model
        self.module_names = transformer_block_names(model, block_path=block_path)

    def capture(self, prefix: SerializedPrefix, *, positions: Sequence[int]) -> ActivationRecord:
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - optional research dependency
            raise RuntimeError("install research dependencies for activation capture") from exc
        selected = tuple(int(position) for position in positions)
        if not selected:
            raise ValueError("at least one activation position is required")
        prefix.assert_same_tokens(prefix.token_ids, consumer="activation extractor")
        device = next(self.model.parameters()).device
        input_ids = torch.tensor([prefix.token_ids], dtype=torch.long, device=device)
        attention_mask = torch.ones_like(input_ids)
        with (
            torch.no_grad(),
            ResidualCapture(self.model, self.module_names, token_indices=selected) as capture,
        ):
            self.model(input_ids=input_ids, attention_mask=attention_mask, use_cache=False)
        values = {name: tensors[-1] for name, tensors in capture.values.items()}
        return ActivationRecord(
            prefix_id=prefix.prefix_id,
            token_ids=prefix.token_ids,
            positions=selected,
            values=values,
        )
