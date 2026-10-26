"""Engineering preflight and single-condition model smoke for the 672 draft."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
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
from goal_takeover.instrumentation.huggingface import HuggingFaceActivationExtractor
from goal_takeover.models.generation import DecodingConfig
from goal_takeover.models.qwen import QwenTransformersBackend
from goal_takeover.phase2.argument_recipient_672_capture import (
    build_canonical_history,
    select_canonical_position,
)
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


def tokenizer_preflight(
    draft: dict[str, Any], tokenizer: Any, config: dict[str, Any], ids: list[str]
) -> dict[str, Any]:
    """Replay canonical reads and check the exact exposure boundary and token IDs."""
    records = []
    for cid in ids:
        task, condition = task_and_condition(draft, cid)
        session = create_session(draft, cid, validated=True)
        backend = _backend(None, tokenizer, session, config)
        history = build_canonical_history(session, task, condition)
        prefix, position = select_canonical_position(backend, history, condition)
        records.append(
            {
                "condition_id": cid,
                **position,
                "prefix_token_ids": list(prefix.token_ids),
                "tool_schema_sha256": prefix.metadata["tool_schema_sha256"],
            }
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


def capture_preflight(
    draft: dict[str, Any], condition_id: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Measure one canonical Tend_assistant residual forward without saving features."""
    import torch

    torch.manual_seed(config["seed"])
    torch.cuda.manual_seed_all(config["seed"])
    task, condition = task_and_condition(draft, condition_id)
    session = create_session(draft, condition_id, validated=True)
    model, tokenizer = _load_model(config["model"])
    backend = _backend(model, tokenizer, session, config)
    history = build_canonical_history(session, task, condition)
    prefix, position = select_canonical_position(backend, history, condition)
    extractor = HuggingFaceActivationExtractor(model, block_path="model.layers")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    record = extractor.capture(prefix, positions=(position["token_index"],))
    elapsed = time.perf_counter() - started
    if record.prefix_id != prefix.prefix_id or record.token_ids != prefix.token_ids:
        raise RuntimeError("capture prefix differs from canonical serialization")
    if record.positions != (position["token_index"],):
        raise RuntimeError("capture position differs from selected last token")
    peak = max(torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved())
    commit, dirty = _git_metadata()
    return {
        "schema_version": 1,
        "status": "engineering_canonical_capture_preflight",
        "research_result": False,
        "draft_condition_id": condition_id,
        "git_commit": commit,
        "git_dirty": dirty,
        "seed": config["seed"],
        "model": config["model"],
        "chat_template_sha256": backend.template_sha256,
        "tool_schema_sha256": prefix.metadata["tool_schema_sha256"],
        "prefix_id": prefix.prefix_id,
        "serialized_text_sha256": hashlib.sha256(prefix.text.encode("utf-8")).hexdigest(),
        "prefix_token_ids": list(prefix.token_ids),
        "position": position,
        "layer_shapes": {name: list(value.shape) for name, value in record.values.items()},
        "layer_dtypes": {name: str(value.dtype) for name, value in record.values.items()},
        "layer_count": len(record.values),
        "elapsed_seconds": elapsed,
        "peak_gpu_memory_bytes": int(peak),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("native-preflight", "tokenizer-preflight", "model-smoke", "capture-preflight"),
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
            parser.error("--config is required for tokenizer and model checks")
        config = load_yaml(args.config)
        if args.command == "tokenizer-preflight":
            from transformers import AutoTokenizer

            model = config["model"]
            tokenizer = AutoTokenizer.from_pretrained(
                model["name"], revision=model["tokenizer_revision"], local_files_only=True
            )
            report = tokenizer_preflight(draft, tokenizer, config, ids)
        elif args.command == "model-smoke":
            if len(ids) != 1:
                parser.error("model-smoke requires exactly one --condition")
            report = model_smoke(draft, ids[0], config)
        else:
            if len(ids) != 1:
                parser.error("capture-preflight requires exactly one --condition")
            report = capture_preflight(draft, ids[0], config)
        report["config_sha256"] = sha256_file(args.config)
    report["draft_sha256"] = sha256_file(args.draft)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
