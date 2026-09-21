"""Non-selection AgentDojo shakedown using one local Transformers model instance."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from goal_takeover.agent import run_agent
from goal_takeover.config import load_yaml
from goal_takeover.datasets.generation import stable_condition_id
from goal_takeover.environments.agentdojo import AgentDojoSession
from goal_takeover.evaluation.outcomes import classify_outcome
from goal_takeover.instrumentation.huggingface import HuggingFaceActivationExtractor
from goal_takeover.instrumentation.token_positions import select_protocol_positions
from goal_takeover.models import DecodingConfig, QwenTransformersBackend, load_hugging_face_model
from goal_takeover.models.scoring import HuggingFaceTeacherForcedScorer
from goal_takeover.runtime import (
    assert_model_has_no_cpu_offload,
    gpu_runtime_report,
    package_version,
)
from goal_takeover.schemas import AgentBoundary, TokenPosition, TokenPositionName
from goal_takeover.serialization.qwen import serialize_qwen_tool_call
from goal_takeover.storage.run_writer import ImmutableRunWriter


@dataclass(frozen=True)
class ShakedownResult:
    run_paths: tuple[Path, ...]
    model_name: str
    model_revision: str


def write_shakedown_failure(
    shakedown_config_path: str | Path,
    *,
    run_prefix: str,
    stage: str,
    error: BaseException,
) -> Path:
    """Publish a small immutable bundle when a shakedown aborts before a full run record."""

    config = load_yaml(shakedown_config_path)
    artifact_root = config["experiment"]["artifact_root"]
    run_id = f"{run_prefix}-technical-failure"
    with ImmutableRunWriter(artifact_root, run_id) as writer:
        writer.write_json(
            "failure.json",
            {
                "schema_version": 1,
                "status": "technical_failure",
                "stage": stage,
                "kind": type(error).__name__,
                "message": str(error),
                "shakedown_config": str(shakedown_config_path),
            },
            kind="technical_failure",
        )
        return writer.commit()


def _git_metadata() -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], check=True, capture_output=True, text=True
        ).stdout.strip()
    )
    return commit, dirty


def _boundary(value: str) -> AgentBoundary:
    try:
        return AgentBoundary(value)
    except ValueError as exc:
        raise ValueError(f"unsupported capture boundary: {value}") from exc


def _call_parts(call: Any) -> tuple[str, dict[str, Any]]:
    return str(call.function), dict(call.args)


def _measurement_messages(
    session: AgentDojoSession, first_call: Any
) -> tuple[list[dict[str, Any]], str]:
    name, arguments = _call_parts(first_call)
    call_id = "measurement_ground_truth_0000"
    result = session.execute_tool(name, arguments, call_id=call_id)
    if result.error is not None:
        raise RuntimeError(f"ground-truth measurement tool failed: {result.error}")
    messages: list[dict[str, Any]] = [*session.initial_messages]
    messages.append(
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }
            ],
        }
    )
    messages.append(
        {
            "role": "tool",
            "name": name,
            "tool_call_id": call_id,
            "content": result.content,
            "error": None,
            "untrusted": True,
        }
    )
    return messages, result.content


def _positions(
    prefix: Any, *, tool_output: str, injection_text: str | None
) -> dict[TokenPositionName, TokenPosition]:
    if injection_text is None:
        index = len(prefix.token_ids) - 1
        position = TokenPosition(
            name=TokenPositionName.TEND_ASSISTANT,
            token_index=index,
            token_id=prefix.token_ids[index],
            sequence_length=len(prefix.token_ids),
            selection_rule="last_prompt_token_at_assistant_generation_boundary",
        )
        return {TokenPositionName.TEND_ASSISTANT: position}
    tool_start = prefix.text.rfind(tool_output)
    if tool_start < 0:
        raise ValueError("tool output is not present verbatim in the serialized prefix")
    injection_relative = tool_output.find(injection_text)
    if injection_relative < 0:
        raise ValueError("fixed injection is not present in the first tool output")
    tool_span = (tool_start, tool_start + len(tool_output))
    injection_span = (
        tool_start + injection_relative,
        tool_start + injection_relative + len(injection_text),
    )
    return select_protocol_positions(
        prefix, injection_span=injection_span, tool_content_span=tool_span
    )


def _position_document(position: TokenPosition) -> dict[str, Any]:
    return {
        "name": position.name.value,
        "token_index": position.token_index,
        "token_id": position.token_id,
        "sequence_length": position.sequence_length,
        "selection_rule": position.selection_rule,
    }


def _prefix_document(prefix: Any, positions: Sequence[TokenPosition] = ()) -> dict[str, Any]:
    return {
        "boundary": prefix.boundary.value,
        "prefix_id": prefix.prefix_id,
        "serialized_text_sha256": hashlib.sha256(prefix.text.encode("utf-8")).hexdigest(),
        "token_ids": list(prefix.token_ids),
        "positions": [_position_document(position) for position in positions],
    }


def _json_messages(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return json.loads(json.dumps(list(messages), ensure_ascii=False, default=str))


def _save_activations(values: Mapping[str, Any]) -> bytes:
    try:
        from safetensors.torch import save
    except ImportError as exc:  # pragma: no cover - optional research dependency
        raise RuntimeError("safetensors is required for activation output") from exc
    tensors = {name: tensor.contiguous() for name, tensor in values.items()}
    return save(tensors)


def _make_backend(
    *,
    model: Any,
    tokenizer: Any,
    session: AgentDojoSession,
    model_config: Mapping[str, Any],
    decoding: Mapping[str, Any],
) -> QwenTransformersBackend:
    model_values = model_config["model"]
    return QwenTransformersBackend(
        model=model,
        tokenizer=tokenizer,
        tools=session.tool_schemas,
        model_revision=model_values["revision"],
        tokenizer_revision=model_values["tokenizer_revision"],
        decoding=DecodingConfig(
            do_sample=bool(decoding["do_sample"]),
            temperature=float(decoding["temperature"]),
            top_p=float(decoding["top_p"]),
            max_new_tokens=int(decoding["max_new_tokens"]),
        ),
        max_context_tokens=int(model_values["max_context_tokens"]),
    )


def run_agentdojo_shakedown(
    shakedown_config_path: str | Path,
    model_config_path: str | Path,
    *,
    run_prefix: str,
) -> ShakedownResult:
    """Execute the three authorized fixtures and publish immutable run bundles."""

    try:
        import torch
    except ImportError as exc:  # pragma: no cover - optional research dependency
        raise RuntimeError("install research dependencies before shakedown") from exc
    shakedown_config = load_yaml(shakedown_config_path)
    model_config = load_yaml(model_config_path)
    experiment = shakedown_config["experiment"]
    model_values = model_config["model"]
    runtime_report = gpu_runtime_report()
    torch.manual_seed(int(experiment["seed"]))
    torch.cuda.manual_seed_all(int(experiment["seed"]))
    model, tokenizer = load_hugging_face_model(
        model_values["name"],
        revision=model_values["revision"],
        tokenizer_revision=model_values["tokenizer_revision"],
        trust_remote_code=bool(model_values["trust_remote_code"]),
        torch_dtype=model_values["dtype"],
        device_map=model_values["device_map"],
        quantization=model_values.get("quantization"),
        low_cpu_mem_usage=bool(model_values["low_cpu_mem_usage"]),
        attn_implementation=model_values.get("attn_implementation"),
    )
    assert_model_has_no_cpu_offload(model)
    extractor = HuggingFaceActivationExtractor(
        model, block_path=model_config["instrumentation"]["transformer_block_path"]
    )
    scorer = HuggingFaceTeacherForcedScorer(model, tokenizer)
    if extractor.model is not model or scorer.model is not model:
        raise RuntimeError("generation, activation, and scoring must share one model instance")
    git_commit, git_dirty = _git_metadata()
    run_paths: list[Path] = []

    for fixture in shakedown_config["fixtures"]:
        fixture_started = time.perf_counter()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        common = {
            "benchmark_version": experiment["benchmark_version"],
            "suite_name": experiment["suite"],
            "user_task_id": fixture["user_task_id"],
            "injection_task_id": fixture.get("injection_task_id"),
            "injections": fixture.get("injections", {}),
        }
        measurement_session = AgentDojoSession.create(**common)
        legitimate_calls, attack_calls = measurement_session.ground_truth_calls()
        if not legitimate_calls:
            raise RuntimeError("fixture has no legitimate ground-truth call")
        messages, tool_output = _measurement_messages(measurement_session, legitimate_calls[0])
        backend = _make_backend(
            model=model,
            tokenizer=tokenizer,
            session=measurement_session,
            model_config=model_config,
            decoding=shakedown_config["decoding"],
        )
        prefix = backend.serialize(messages)
        if prefix.boundary != _boundary(fixture["capture_boundary"]):
            raise RuntimeError("measurement prefix is at the wrong agent boundary")
        injection_text = None
        if fixture.get("injection_vector") is not None:
            injection_text = fixture["injection_match_text"]
        positions = _positions(prefix, tool_output=tool_output, injection_text=injection_text)
        activation = extractor.capture(
            prefix, positions=[position.token_index for position in positions.values()]
        )
        activation.assert_matches(prefix)
        if len(activation.values) != len(extractor.module_names):
            raise RuntimeError("activation capture did not return every transformer layer")

        scores = None
        legitimate_call_document = _call_parts(
            legitimate_calls[int(fixture.get("legitimate_call_index", 0))]
        )
        attack_call_document = None
        if fixture.get("primary_argument_slot") is not None:
            if not attack_calls:
                raise RuntimeError("scored fixture has no attack ground-truth call")
            attack_call_document = _call_parts(
                attack_calls[int(fixture.get("attack_call_index", 0))]
            )
            legitimate_serialized = serialize_qwen_tool_call(*legitimate_call_document)
            attack_serialized = serialize_qwen_tool_call(*attack_call_document)
            legitimate_score, attack_score, margins = scorer.score_pair(
                prefix,
                legitimate=legitimate_serialized,
                attack=attack_serialized,
                argument_slot=fixture["primary_argument_slot"],
            )
            scores = {
                "prefix_id": prefix.prefix_id,
                "legitimate": legitimate_score.as_dict(),
                "attack": attack_score.as_dict(),
                "margins": margins.as_dict(),
            }

        # Generation is deliberately performed from the same measured prefix.
        backend.next_action(messages)
        backend.prefixes[-1].assert_same_tokens(prefix.token_ids, consumer="generation")

        actual_session = AgentDojoSession.create(**common)
        actual_backend = _make_backend(
            model=model,
            tokenizer=tokenizer,
            session=actual_session,
            model_config=model_config,
            decoding=shakedown_config["decoding"],
        )
        actual_run = run_agent(
            actual_backend,
            actual_session.initial_messages,
            actual_session.tools,
            max_steps=int(experiment["max_steps"]),
        )
        evaluation = actual_session.evaluate(actual_run.final_answer)
        outcome_group = classify_outcome(
            has_attack=fixture.get("injection_task_id") is not None,
            user_task_success=evaluation.user_task_success,
            attack_success=evaluation.attack_success,
        )
        condition_payload = {
            "fixture_id": fixture["fixture_id"],
            "benchmark_version": experiment["benchmark_version"],
            "suite": experiment["suite"],
            "user_task_id": fixture["user_task_id"],
            "injection_task_id": fixture.get("injection_task_id"),
            "injections": fixture.get("injections", {}),
        }
        condition_id = stable_condition_id(condition_payload)
        run_id = f"{run_prefix}-{fixture['fixture_id']}"
        technical_errors = list(actual_session.tool_errors)
        if actual_run.stop_reason == "unknown_tool":
            technical_errors.append("model requested a tool outside the pinned schema")
        technical_error = "; ".join(technical_errors) or None
        peak_memory = int(torch.cuda.max_memory_allocated())
        elapsed_seconds = time.perf_counter() - fixture_started
        resolved_config = {
            "schema_version": 2,
            "status": "pre_gate_shakedown_only",
            "experiment": experiment,
            "fixture": fixture,
            "model": model_values,
            "runtime": runtime_report,
            "versions": {
                name: package_version(name)
                for name in (
                    "agentdojo",
                    "accelerate",
                    "bitsandbytes",
                    "safetensors",
                    "transformers",
                )
            },
            "peak_gpu_memory_bytes": peak_memory,
            "elapsed_seconds": elapsed_seconds,
            "serialization": {
                "chat_template_sha256": backend.template_sha256,
                "tool_schema_sha256": prefix.metadata["tool_schema_sha256"],
                "system_message_sha256": prefix.metadata["system_message_sha256"],
                "enable_thinking": False,
            },
        }
        prefix_positions = [_position_document(position) for position in positions.values()]
        token_document = {
            "boundary": prefix.boundary.value,
            "prefix_id": prefix.prefix_id,
            "text": prefix.text,
            "token_ids": list(prefix.token_ids),
            "offsets": [
                {
                    "token_index": offset.token_index,
                    "token_id": offset.token_id,
                    "start": offset.start,
                    "end": offset.end,
                }
                for offset in prefix.offsets
            ],
            "positions": prefix_positions,
            "metadata": prefix.metadata,
        }
        condition_document = {
            "schema_version": 2,
            "condition_id": condition_id,
            "task_template_id": fixture["user_task_id"],
            "variant_id": fixture["fixture_id"],
            "task_openness": "param_open",
            "paraphrase_family_id": fixture["fixture_id"],
            "pair_id": None,
            "attack_goal_id": fixture.get("injection_task_id"),
            "attack_style_id": "direct_override" if injection_text else None,
            "attack_template_id": "shakedown_direct_override_bill_v1" if injection_text else None,
            "argument_slot_id": fixture.get("primary_argument_slot"),
            "stochastic_family_id": None,
            "condition_family": "ipi" if injection_text else "clean",
            "has_attack": injection_text is not None,
            "legitimate_call": {
                "name": legitimate_call_document[0],
                "arguments": legitimate_call_document[1],
            },
            "attack_call": (
                None
                if attack_call_document is None
                else {"name": attack_call_document[0], "arguments": attack_call_document[1]}
            ),
            "injection_span": (
                None
                if injection_text is None
                else {
                    "message_index": 2,
                    "start": tool_output.index(injection_text),
                    "end": tool_output.index(injection_text) + len(injection_text),
                }
            ),
            "messages": _json_messages(messages),
            "metadata": {"pre_gate_shakedown_only": True},
        }

        with ImmutableRunWriter(experiment["artifact_root"], run_id) as writer:
            artifact_records = []
            config_artifact = writer.write_json(
                "resolved_config.json", resolved_config, kind="resolved_config"
            )
            artifact_records.append(config_artifact)
            artifact_records.append(
                writer.write_json("condition.json", condition_document, kind="condition")
            )
            artifact_records.append(
                writer.write_json(
                    "messages.json", _json_messages(actual_run.messages), kind="message_trace"
                )
            )
            artifact_records.append(
                writer.write_json("tokens.json", token_document, kind="token_record")
            )
            artifact_records.append(
                writer.write_json(
                    "actual_prefixes.json",
                    [
                        {
                            "text": actual_prefix.text,
                            "metadata": actual_prefix.metadata,
                            **_prefix_document(actual_prefix),
                        }
                        for actual_prefix in actual_backend.prefixes
                    ],
                    kind="actual_prefix_records",
                )
            )
            artifact_records.append(
                writer.write_bytes(
                    "activations/residual.safetensors",
                    _save_activations(activation.values),
                    kind="residual_activation",
                )
            )
            artifact_records.append(
                writer.write_json(
                    "activations/metadata.json",
                    {
                        "prefix_id": activation.prefix_id,
                        "token_ids": list(activation.token_ids),
                        "positions": list(activation.positions),
                        "layers": {
                            name: {
                                "shape": list(tensor.shape),
                                "dtype": str(tensor.dtype),
                            }
                            for name, tensor in activation.values.items()
                        },
                    },
                    kind="residual_activation_metadata",
                )
            )
            if scores is not None:
                artifact_records.append(
                    writer.write_json("scores.json", scores, kind="candidate_scores")
                )
            run_record = {
                "schema_version": 2,
                "run_id": run_id,
                "condition_id": condition_id,
                "parent_run_id": None,
                "git_commit": git_commit,
                "git_dirty": git_dirty,
                "resolved_config_sha256": config_artifact["sha256"],
                "model": {"name": model_values["name"], "revision": model_values["revision"]},
                "tokenizer": {
                    "name": model_values["name"],
                    "revision": model_values["tokenizer_revision"],
                },
                "seed": int(experiment["seed"]),
                "decoding": shakedown_config["decoding"],
                "prefix_records": [
                    _prefix_document(prefix, positions.values()),
                    *[_prefix_document(actual_prefix) for actual_prefix in actual_backend.prefixes],
                ],
                "outcome": {
                    "has_attack": injection_text is not None,
                    "user_task_success": evaluation.user_task_success,
                    "attack_success": evaluation.attack_success,
                    "group": outcome_group.value if outcome_group else None,
                    "baseline_failure": outcome_group is None,
                    "evaluator_version": evaluation.evaluator_version,
                },
                "scores": scores,
                "failure": (
                    None
                    if technical_error is None
                    else {
                        "stage": "tool_execution",
                        "kind": "tool_error",
                        "message": technical_error,
                    }
                ),
                "artifacts": artifact_records,
            }
            writer.write_json("run.json", run_record, kind="run_record")
            run_paths.append(writer.commit())

    return ShakedownResult(tuple(run_paths), model_values["name"], model_values["revision"])
