"""Collect Qwen attention at the decision query without a full attention matrix."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


class QwenQueryAttentionCapture:
    """Recompute only the last-query weights while the model keeps SDPA outputs.

    This is limited to an evaluation forward over one unpadded, complete prefix.
    It fails closed if the Qwen attention contract changes or a cache/sliding
    window is introduced. The pre-hook does not alter the model's output.
    """

    def __init__(
        self, model: Any, block_names: Sequence[str], consume: Callable[[str, Any], None]
    ) -> None:
        modules = dict(model.named_modules())
        self.modules = {}
        for block in block_names:
            name = f"{block}.self_attn"
            if name not in modules:
                raise ValueError(f"unverified Qwen attention module: {name}")
            self.modules[name] = modules[name]
        self.consume = consume
        self.seen: set[str] = set()
        self.handles: list[Any] = []

    def __enter__(self):
        try:
            for name, module in self.modules.items():
                self.handles.append(
                    module.register_forward_pre_hook(self._hook(name), with_kwargs=True)
                )
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def _hook(self, name: str):
        def hook(module: Any, args: Any, kwargs: Any) -> None:
            import torch

            if name in self.seen:
                raise ValueError("duplicate attention layer execution")
            if args or kwargs.get("past_key_values") is not None:
                raise ValueError("query attention requires an uncached Qwen prefix forward")
            if module.training or module.sliding_window is not None:
                raise ValueError("query attention requires evaluation and full causal attention")
            hidden = kwargs.get("hidden_states")
            embeddings = kwargs.get("position_embeddings")
            if (
                hidden is None
                or hidden.ndim != 3
                or hidden.shape[0] != 1
                or not isinstance(embeddings, tuple)
                or len(embeddings) != 2
            ):
                raise ValueError("unverified Qwen query/position-embedding inputs")
            length = hidden.shape[1]
            cos, sin = embeddings
            if cos.shape[:2] != (1, length) or sin.shape != cos.shape:
                raise ValueError("unverified Qwen rotary embedding shape")
            heads = module.config.num_attention_heads
            kv_heads = module.config.num_key_value_heads
            if heads % kv_heads or module.num_key_value_groups != heads // kv_heads:
                raise ValueError("unverified Qwen grouped-query layout")
            shape = (1, length, -1, module.head_dim)
            query = module.q_norm(module.q_proj(hidden).view(shape)).transpose(1, 2)
            query = query[:, :, -1:, :]
            key = module.k_norm(module.k_proj(hidden).view(shape)).transpose(1, 2)

            def rotate_half(value: Any) -> Any:
                left, right = value.chunk(2, dim=-1)
                return torch.cat((-right, left), dim=-1)

            query = query * cos[:, -1:, :].unsqueeze(1) + rotate_half(query) * sin[
                :, -1:, :
            ].unsqueeze(1)
            key = key * cos.unsqueeze(1) + rotate_half(key) * sin.unsqueeze(1)
            key = key.repeat_interleave(module.num_key_value_groups, dim=1)
            scores = torch.matmul(query, key.transpose(-2, -1)) * module.scaling
            mask = kwargs.get("attention_mask")
            if mask is not None:
                if mask.ndim != 4 or mask.shape[-1] != length:
                    raise ValueError("unverified Qwen attention mask shape")
                scores = scores + mask[:, :, -1:, :]
            weights = torch.softmax(scores, dim=-1, dtype=torch.float32).to(query.dtype)
            weights = weights[0, :, 0, :]
            if weights.shape != (heads, length) or not bool(weights.isfinite().all()):
                raise ValueError("invalid last-query attention weights")
            self.consume(name, weights)
            self.seen.add(name)

        return hook

    def assert_complete(self) -> None:
        if self.seen != set(self.modules):
            raise ValueError("attention capture has missing layers")

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        for handle in self.handles:
            handle.remove()
        self.handles.clear()


class QwenAttentionCapture:
    """Verified Qwen3 self-attention tuple contract; unsupported backends fail.

    Qwen3 returns (attention_output, attention_weights). Reducing weights in
    the module hook and returning None in the second slot prevents the model
    output from retaining every layer's quadratic attention matrix. The
    computed attention_output is passed through unchanged.
    """

    def __init__(
        self, model: Any, block_names: Sequence[str], consume: Callable[[str, Any], None]
    ) -> None:
        modules = dict(model.named_modules())
        self.modules = {}
        for block in block_names:
            name = f"{block}.self_attn"
            if name not in modules:
                raise ValueError(f"unverified Qwen attention module: {name}")
            self.modules[name] = modules[name]
        self.consume = consume
        self.seen: set[str] = set()
        self.handles: list[Any] = []

    def __enter__(self):
        try:
            for name, module in self.modules.items():
                self.handles.append(module.register_forward_hook(self._hook(name)))
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def _hook(self, name: str):
        def hook(_module: Any, _inputs: Any, output: Any):
            if not isinstance(output, tuple) or len(output) != 2 or output[1] is None:
                raise ValueError("unverified Qwen attention output; expected output and weights")
            if name in self.seen:
                raise ValueError("duplicate attention layer execution")
            self.consume(name, output[1])
            self.seen.add(name)
            return output[0], None

        return hook

    def assert_complete(self) -> None:
        if self.seen != set(self.modules):
            raise ValueError("attention capture has missing layers")

    def __exit__(self, _exc_type, _exc, _traceback):
        for handle in self.handles:
            handle.remove()
        self.handles.clear()
