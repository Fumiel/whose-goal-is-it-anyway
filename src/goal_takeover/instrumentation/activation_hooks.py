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


class ResidualPatch:
    """Replace one block-output vector once, without modifying its input tensor.

    Register this context before ResidualCapture when both observe the same block.
    The index is local to this forward's uncached input, not the full history.
    """

    def __init__(self, model: Any, module_name: str, sequence_index: int, vector: Any) -> None:
        modules = dict(model.named_modules())
        if module_name not in modules:
            raise ValueError(f"unknown patch module: {module_name}")
        if sequence_index < 0:
            raise ValueError("patch index must be non-negative")
        self.module = modules[module_name]
        self.index = sequence_index
        self.vector = vector
        self.calls = 0
        self.handle: Any = None

    def _hook(self, _module: Any, _inputs: Any, output: Any) -> Any:
        self.calls += 1
        value = output[0] if isinstance(output, tuple) else output
        if value.ndim != 3 or value.shape[0] != 1:
            raise ValueError("patch expects [1, sequence, hidden]")
        if self.index >= value.shape[1]:
            raise IndexError("patch index outside uncached input")
        if (
            self.vector.shape != value.shape[2:]
            or self.vector.dtype != value.dtype
            or self.vector.device != value.device
        ):
            raise ValueError("patch vector shape/dtype/device differs")
        patched = value.clone()
        patched[0, self.index, :] = self.vector
        if isinstance(output, tuple):
            values = (patched, *output[1:])
            return values if type(output) is tuple else type(output)(*values)
        return patched

    def __enter__(self) -> ResidualPatch:
        if self.handle is not None:
            raise RuntimeError("patch context already registered")
        self.calls = 0
        self.handle = self.module.register_forward_hook(self._hook)
        return self

    def __exit__(self, exc_type: Any, _exc: Any, _traceback: Any) -> None:
        if self.handle is not None:
            self.handle.remove()
            self.handle = None
        if exc_type is None and self.calls != 1:
            raise RuntimeError(f"patch hook called {self.calls} times, expected once")
