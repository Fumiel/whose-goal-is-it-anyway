"""Validated decoding parameters shared by model adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecodingConfig:
    do_sample: bool = False
    temperature: float = 0.0
    top_p: float = 1.0
    max_new_tokens: int = 256

    def __post_init__(self) -> None:
        if self.max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be positive")
        if self.do_sample and self.temperature <= 0:
            raise ValueError("sampled decoding requires temperature > 0")
        if not 0 < self.top_p <= 1:
            raise ValueError("top_p must be in (0, 1]")

    def as_transformers_kwargs(self) -> dict[str, int | float | bool]:
        values: dict[str, int | float | bool] = {
            "do_sample": self.do_sample,
            "max_new_tokens": self.max_new_tokens,
        }
        if self.do_sample:
            values.update(temperature=self.temperature, top_p=self.top_p)
        return values
