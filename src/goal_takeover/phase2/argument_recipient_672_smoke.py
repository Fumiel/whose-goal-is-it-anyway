"""Engineering preflight and single-condition model smoke for the 672 draft."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from goal_takeover.agent.runner import run_agent
from goal_takeover.config import load_yaml
from goal_takeover.datasets.argument_recipient_672_native import (
    create_session,
    evaluate_condition,
    load_draft,
    native_preflight,
    task_and_condition,
)
from goal_takeover.instrumentation.token_positions import overlapping_token_indices
from goal_takeover.models.generation import DecodingConfig
from goal_takeover.models.qwen import QwenTransformersBackend
from goal_takeover.pilot.evaluation import RecordingSession, state_document
from goal_takeover.selection import _load_model
from goal_takeover.shakedown import _git_metadata
from goal_takeover.storage.run_writer import sha256_file


def _backend(model: Any, tokenizer: Any, session: Any, config: dict[str, Any]) -> Any:
    values = config["model"]
    decoding = config["decoding"]
    if (decoding["do_sample"], decoding["temperature"], decoding["top_p"]) != (False, 0.0, 1.0):
        raise ValueError("672 draft smoke requires deterministic decoding")
    return QwenTransformersBackend(
        model=model,
        tokenizer=tokenizer,
        tools=session.tool_schemas,
        model_revision=values["revision"],
        tokenizer_revision=values["tokenizer_revision"],
        decoding=DecodingConfig(
            do_sample=False,
            temperature=0.0,
            top_p=1.0,
            max_new_tokens=decoding["max_new_tokens"],
        ),
        max_context_tokens=values["max_context_tokens"],
    )


def _prefix_record(prefix: Any, account: str) -> dict[str, Any]:
    occurrences = []
    start = 0
    while (index := prefix.text.find(account, start)) >= 0:
        occurrences.append(index)
        start = index + len(account)
    if len(occurrences) != 1:
        raise ValueError(
            f"recipient account must appear exactly once at selected boundary: {len(occurrences)}"
        )
    indices = overlapping_token_indices(
        prefix.offsets, start=occurrences[0], end=occurrences[0] + len(account)
    )
    if not indices:
        raise ValueError("recipient account has no aligned tokens")
    return {
        "boundary": prefix.boundary.value,
        "prefix_id": prefix.prefix_id,
        "prefix_token_ids": list(prefix.token_ids),
        "recipient_token_indices": list(indices),
        "recipient_token_ids": [prefix.token_ids[i] for i in indices],
        "recipient_last_token_index": indices[-1],
        "recipient_last_token_id": prefix.token_ids[indices[-1]],
        "assistant_boundary_token_index": len(prefix.token_ids) - 1,
        "assistant_boundary_token_id": prefix.token_ids[-1],
        "tool_schema_sha256": prefix.metadata["tool_schema_sha256"],
    }


def tokenizer_preflight(
    draft: dict[str, Any], tokenizer: Any, config: dict[str, Any], ids: list[str]
) -> dict[str, Any]:
    """Replay canonical reads and check the exact exposure boundary and token IDs."""
    records = []
    for cid in ids:
        task, condition = task_and_condition(draft, cid)
        session = create_session(draft, cid, validated=True)
        backend = _backend(None, tokenizer, session, config)
        messages: list[dict[str, Any]] = list(session.initial_messages)
        account = condition["expected_send_money"]["arguments"]["recipient"]
        source = condition["exposure"]["source_role"]
        if source == "user_instruction":
            selected = backend.serialize(messages)
        else:
            if account in backend.serialize(messages).text:
                raise ValueError(f"{cid}: document account leaked before read")
            for index, call in enumerate(task["expected_read_file_calls"]):
                call_id = f"canonical_read_{index}"
                result = session.execute_tool(call["name"], call["arguments"], call_id=call_id)
                if result.error is not None:
                    raise ValueError(f"{cid}: canonical read failed: {result.error}")
                messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {"name": call["name"], "arguments": call["arguments"]},
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "name": call["name"],
                        "tool_call_id": call_id,
                        "content": result.content,
                        "error": result.error,
                        "untrusted": True,
                    }
                )
                if (
                    index < len(task["expected_read_file_calls"]) - 1
                    and account in backend.serialize(messages).text
                ):
                    raise ValueError(f"{cid}: account exposed before all declared reads")
            selected = backend.serialize(messages)
        expected_boundary = condition["exposure"]["boundary"]
        if selected.boundary.value != expected_boundary:
            raise ValueError(f"{cid}: selected boundary differs from declaration")
        records.append(
            {"condition_id": cid, "source_role": source, **_prefix_record(selected, account)}
        )
    return {
        "schema_version": 1,
        "status": "canonical_tokenizer_preflight_passed",
        "research_result": False,
        "condition_count": len(records),
        "conditions": records,
    }


def model_smoke(draft: dict[str, Any], condition_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Run one actual trajectory; retain evidence but make no probe capture claim."""
    import torch

    torch.manual_seed(config["seed"])
    torch.cuda.manual_seed_all(config["seed"])
    task, condition = task_and_condition(draft, condition_id)
    session = create_session(draft, condition_id, validated=True)
    model, tokenizer = _load_model(config["model"])
    backend = _backend(model, tokenizer, session, config)
    recorder = RecordingSession(session)
    initial = state_document(session.environment)
    actual = run_agent(
        backend,
        session.initial_messages,
        recorder.tools,
        max_steps=config["decoding"]["max_steps"],
    )
    final = state_document(session.environment)
    strict = evaluate_condition(
        task, condition, initial, final, recorder.events, require_content=True
    )
    native = session.evaluate(actual.final_answer)
    if len(backend.prefixes) != len(actual.actions):
        raise RuntimeError("generation/prefix count mismatch")
    commit, dirty = _git_metadata()
    return {
        "schema_version": 1,
        "status": "engineering_model_smoke",
        "research_result": False,
        "draft_condition_id": condition_id,
        "git_commit": commit,
        "git_dirty": dirty,
        "seed": config["seed"],
        "model": config["model"],
        "decoding": config["decoding"],
        "chat_template_sha256": backend.template_sha256,
        "tool_schema_sha256": backend.prefixes[0].metadata["tool_schema_sha256"],
        "stop_reason": actual.stop_reason,
        "final_answer": actual.final_answer,
        "messages": actual.messages,
        "generations": [
            {
                "prefix_id": prefix.prefix_id,
                "boundary": prefix.boundary.value,
                "prefix_token_ids": list(prefix.token_ids),
                "boundary_token_index": len(prefix.token_ids) - 1,
                "boundary_token_id": prefix.token_ids[-1],
                "raw_text": action.raw_text,
                "kind": action.kind,
                "tool_calls": [
                    {"name": call.name, "arguments": dict(call.arguments), "call_id": call.call_id}
                    for call in action.ordered_tool_calls()
                ],
            }
            for prefix, action in zip(backend.prefixes, actual.actions, strict=True)
        ],
        "tool_events": recorder.events,
        "native_user_task_success": native.user_task_success,
        "strict_evaluation": strict,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("native-preflight", "tokenizer-preflight", "model-smoke")
    )
    parser.add_argument("draft", type=Path)
    parser.add_argument("--condition", action="append")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    draft = load_draft(args.draft)
    ids = args.condition or [row["draft_condition_id"] for row in draft["condition_specs"]]
    if len(ids) != len(set(ids)):
        parser.error("duplicate condition ID")
    if args.command == "native-preflight":
        report = native_preflight(draft, ids)
    else:
        if args.config is None:
            parser.error("--config is required for tokenizer-preflight and model-smoke")
        config = load_yaml(args.config)
        if args.command == "tokenizer-preflight":
            from transformers import AutoTokenizer

            model = config["model"]
            tokenizer = AutoTokenizer.from_pretrained(
                model["name"], revision=model["tokenizer_revision"], local_files_only=True
            )
            report = tokenizer_preflight(draft, tokenizer, config, ids)
        else:
            if len(ids) != 1:
                parser.error("model-smoke requires exactly one --condition")
            report = model_smoke(draft, ids[0], config)
        report["config_sha256"] = sha256_file(args.config)
    report["draft_sha256"] = sha256_file(args.draft)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
