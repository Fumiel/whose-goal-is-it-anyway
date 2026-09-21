"""Runtime compatibility checks for the Windows/WSL execution host."""

from __future__ import annotations

import platform
from importlib.metadata import PackageNotFoundError, version
from typing import Any


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def gpu_runtime_report() -> dict[str, Any]:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - optional research dependency
        raise RuntimeError("PyTorch is not installed") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available to PyTorch")
    properties = torch.cuda.get_device_properties(0)
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "device_name": torch.cuda.get_device_name(0),
        "compute_capability": list(torch.cuda.get_device_capability(0)),
        "total_memory_bytes": int(properties.total_memory),
        "bfloat16_supported": bool(torch.cuda.is_bf16_supported()),
        "packages": {
            name: package_version(name)
            for name in ("agentdojo", "accelerate", "bitsandbytes", "transformers")
        },
    }
    if report["packages"]["agentdojo"] != "0.1.35":
        raise RuntimeError("gpu environment must contain agentdojo==0.1.35")
    if not report["bfloat16_supported"]:
        raise RuntimeError("the selected models require BF16-capable CUDA hardware")
    return report


def assert_model_has_no_cpu_offload(model: Any) -> None:
    device_map = getattr(model, "hf_device_map", None)
    if device_map:
        forbidden = {
            str(device) for device in device_map.values() if str(device).lower() in {"cpu", "disk"}
        }
        if forbidden:
            raise RuntimeError(f"model uses forbidden offload targets: {sorted(forbidden)}")
    parameter_devices = {str(parameter.device) for parameter in model.parameters()}
    if any(device == "cpu" or device == "meta" for device in parameter_devices):
        raise RuntimeError(
            f"model parameters are not fully materialized on CUDA: {parameter_devices}"
        )
