"""Release Qwen attention matrices layer by layer after reduction."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


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
