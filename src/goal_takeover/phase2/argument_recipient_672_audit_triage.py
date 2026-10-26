"""Deterministic flags for targeted human inspection of recipient run logs."""

from __future__ import annotations

import json
from typing import Any


def human_review_reasons(run: dict[str, Any], llm_judgments: list[dict[str, Any]]) -> list[str]:
    """Flag disagreements and logs that need inspection; never sample randomly."""
    if not llm_judgments:
        raise ValueError("at least one LLM judgment is required")
    labels = ("user_task_success", "recipient_correct", "required_reads_complete")
    for judgment in llm_judgments:
        if not all(type(judgment.get(label)) is bool for label in labels):
            raise ValueError("LLM judgments must contain the three boolean audit labels")
    reasons = []
    for label in labels:
        if len(llm_judgments) > 1 and len({judgment[label] for judgment in llm_judgments}) > 1:
            reasons.append(f"llm_disagreement:{label}")
    automatic = (run.get("strict_evaluation") or {}).get("user_task_success")
    if type(automatic) is bool and any(
        judgment["user_task_success"] != automatic for judgment in llm_judgments
    ):
        reasons.append("llm_vs_automatic:user_task_success")
    generations = run.get("generations")
    if not isinstance(generations, list):
        return [*reasons, "missing_generation_log"]
    previous_text: str | None = None
    seen_calls: set[str] = set()
    for generation in generations:
        raw = generation.get("raw_text")
        if not isinstance(raw, str):
            reasons.append("missing_raw_text")
        else:
            normalized = " ".join(raw.split())
            if len(normalized) >= 20 and normalized == previous_text:
                reasons.append("repeated_assistant_text")
            previous_text = normalized
        for call in generation.get("tool_calls", []):
            signature = json.dumps(
                {"name": call.get("name"), "arguments": call.get("arguments")},
                sort_keys=True,
            )
            if signature in seen_calls:
                reasons.append("repeated_tool_call")
            seen_calls.add(signature)
    if run.get("stop_reason") in {"max_steps", "unknown_tool"}:
        reasons.append(f"stop_reason:{run['stop_reason']}")
    return sorted(set(reasons))
