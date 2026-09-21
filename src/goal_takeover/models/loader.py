"""Lazy Hugging Face loader kept separate from experiment logic."""

from __future__ import annotations

from typing import Any


def load_hugging_face_model(
    model_name: str,
    *,
    revision: str | None = None,
    tokenizer_revision: str | None = None,
    trust_remote_code: bool = False,
    torch_dtype: str = "bfloat16",
    device_map: str = "auto",
    quantization: str | None = None,
    low_cpu_mem_usage: bool = True,
    attn_implementation: str | None = None,
) -> tuple[Any, Any]:
    """Load a causal LM and tokenizer after the exact revision is selected."""

    if not revision or not tokenizer_revision:
        raise ValueError("immutable model and tokenizer revisions are required")
    if quantization not in (None, "int8"):
        raise ValueError("quantization must be null or 'int8'")
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as exc:  # pragma: no cover - requires research extras
        raise RuntimeError("install the 'research' dependencies to load a model") from exc

    dtype = getattr(torch, torch_dtype, None)
    if dtype is None:
        raise ValueError(f"unknown torch dtype: {torch_dtype}")

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        revision=tokenizer_revision or revision,
        trust_remote_code=trust_remote_code,
    )
    model_kwargs: dict[str, Any] = {
        "revision": revision,
        "trust_remote_code": trust_remote_code,
        "torch_dtype": dtype,
        "device_map": device_map,
        "low_cpu_mem_usage": low_cpu_mem_usage,
    }
    if attn_implementation is not None:
        model_kwargs["attn_implementation"] = attn_implementation
    if quantization == "int8":
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_enable_fp32_cpu_offload=False,
        )
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        **model_kwargs,
    )
    model.eval()
    return model, tokenizer
