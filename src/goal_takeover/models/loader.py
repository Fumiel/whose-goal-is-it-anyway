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
) -> tuple[Any, Any]:
    """Load a causal LM and tokenizer after the exact revision is selected."""

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
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
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        revision=revision,
        trust_remote_code=trust_remote_code,
        torch_dtype=dtype,
        device_map=device_map,
    )
    model.eval()
    return model, tokenizer
