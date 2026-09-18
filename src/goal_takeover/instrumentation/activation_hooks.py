"""Architecture-neutral PyTorch forward-hook capture."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any


class ResidualCapture:
    """Capture selected module outputs on CPU.

    Module names must be verified for the selected model. This class deliberately
    does not guess which submodule corresponds to a transformer residual stream.
    """

    def __init__(
        self,
        model: Any,
        module_names: Iterable[str],
        *,
        token_indices: Sequence[int] | None = None,
    ) -> None:
        available = dict(model.named_modules())
        requested = tuple(module_names)
        missing = sorted(set(requested) - available.keys())
        if missing:
            raise ValueError(f"unknown module names: {', '.join(missing)}")
        self._modules = {name: available[name] for name in requested}
        self._handles: list[Any] = []
        self.values: dict[str, list[Any]] = {name: [] for name in requested}
        self._token_indices = None if token_indices is None else tuple(token_indices)
        if self._token_indices is not None and any(index < 0 for index in self._token_indices):
            raise ValueError("token indices must be non-negative")

    def _tensor_from_output(self, output: Any) -> Any:
        value = output[0] if isinstance(output, tuple) else output
        if not hasattr(value, "detach"):
            raise TypeError("hook output is not tensor-like")
        if self._token_indices is not None:
            if getattr(value, "ndim", 0) != 3:
                raise ValueError("selected-position capture expects [batch, sequence, hidden]")
            if self._token_indices and max(self._token_indices) >= value.shape[1]:
                raise IndexError("capture token index is outside the sequence")
            value = value[:, self._token_indices, :]
        return value.detach().to("cpu").clone()

    def __enter__(self) -> ResidualCapture:
        for name, module in self._modules.items():
            handle = module.register_forward_hook(self._make_hook(name))
            self._handles.append(handle)
        return self

    def _make_hook(self, name: str) -> Any:
        def hook(_module: Any, _inputs: Any, output: Any) -> None:
            self.values[name].append(self._tensor_from_output(output))

        return hook

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles.clear()
