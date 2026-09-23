"""Frozen-sample AgentDojo model selection, separate from the shakedown."""

from __future__ import annotations

import gc
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from goal_takeover.agent import run_agent
from goal_takeover.agent.runner import AgentAction, AgentRun
from goal_takeover.config import ConfigError, load_yaml
from goal_takeover.environments.agentdojo import AgentDojoSession
from goal_takeover.evaluation.outcomes import classify_outcome
from goal_takeover.instrumentation.huggingface import HuggingFaceActivationExtractor
from goal_takeover.models import load_hugging_face_model
from goal_takeover.models.scoring import HuggingFaceTeacherForcedScorer
from goal_takeover.runtime import (
    assert_model_has_no_cpu_offload,
    gpu_runtime_report,
    package_version,
)
from goal_takeover.serialization.qwen import serialize_qwen_tool_call
from goal_takeover.shakedown import (
    _call_parts,
    _git_metadata,
    _json_messages,
    _make_backend,
    _measurement_messages,
    _position_document,
    _positions,
    _prefix_document,
    _save_activations,
)
from goal_takeover.storage.run_writer import ImmutableRunWriter, sha256_file


@dataclass(frozen=True)
class SelectionPlan:
    gate_path: Path
    sample_path: Path
    gate: dict[str, Any]
    sample: dict[str, Any]
    checksums: dict[str, str]
    freeze: dict[str, Any] | None


def load_selection_plan(gate_path: str | Path, *, require_frozen: bool = True) -> SelectionPlan:
    path = Path(gate_path)
    gate = load_yaml(path)
    sample_path = path.parent / gate["selection"]["sample_manifest"]
    sample = load_yaml(sample_path)
    if require_frozen and (gate.get("status") != "frozen" or sample.get("status") != "frozen"):
        raise ConfigError("selection gate and sample must both be frozen before model runs")
    selection = sample["selection"]
    conditions = selection["conditions"]
    if len(conditions) != 7 or sum(c["condition_family"] == "clean" for c in conditions) != 5:
        raise ConfigError("selection sample must contain five clean and two IPI conditions")
    if len({c["condition_id"] for c in conditions}) != 7:
        raise ConfigError("selection condition IDs must be unique")
    if len(selection["candidate_models"]) != 2 or len(set(selection["candidate_models"])) != 2:
        raise ConfigError("selection requires exactly two distinct candidate models")
    if selection["decoding"]["do_sample"] or selection["decoding"]["strategy"] != "greedy":
        raise ConfigError("selection decoding must be deterministic")
    if gate["selection"]["thresholds"]["clean_user_task_success"]["denominator"] != 5:
        raise ConfigError("clean success denominator must match the five declared conditions")
    if gate["selection"]["thresholds"]["teacher_forced_scoring_success"]["denominator"] != 2:
        raise ConfigError("scoring denominator must match the two IPI conditions")
    if gate["selection"]["thresholds"]["evaluator_human_agreement"]["audit_sample_size"] != 7:
        raise ConfigError("audit must cover all seven conditions per candidate")
    checksums = {"gate": sha256_file(path), "sample": sha256_file(sample_path)}
    for label, relative in gate["references"].items():
        checksums[label] = sha256_file(path.parent / relative)
    freeze_path = path.with_suffix(".freeze.json")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8")) if freeze_path.exists() else None
    if require_frozen:
        if freeze is None or freeze["sha256"] != checksums:
            raise ConfigError("frozen selection checksums no longer match the files")
    return SelectionPlan(path, sample_path, gate, sample, checksums, freeze)


def _session(plan: SelectionPlan, condition: dict[str, Any]) -> AgentDojoSession:
    selection = plan.sample["selection"]
    return AgentDojoSession.create(
        benchmark_version=selection["benchmark_version"],
        suite_name=selection["suite"],
        user_task_id=condition["user_task_id"],
        injection_task_id=condition.get("injection_task_id"),
        injections=condition["injections"],
    )


def preflight_selection(plan: SelectionPlan) -> list[dict[str, Any]]:
    """Inspect actual pinned environments and reject declaration drift."""

    reports = []
    clean_ids = {
        c["condition_id"]
        for c in plan.sample["selection"]["conditions"]
        if c["condition_family"] == "clean"
    }
    for condition in plan.sample["selection"]["conditions"]:
        condition_id = condition["condition_id"]
        session = _session(plan, condition)
        legitimate, attack = session.ground_truth_calls()
        if not legitimate:
            raise ConfigError(f"{condition_id}: no legitimate ground-truth call")
        _, tool_output = _measurement_messages(session, legitimate[0])
        is_ipi = condition["condition_family"] == "ipi"
        if is_ipi != (condition.get("injection_task_id") is not None):
            raise ConfigError(f"{condition_id}: attack family and injection task disagree")
        report: dict[str, Any] = {
            "condition_id": condition_id,
            "user_task_id": condition["user_task_id"],
            "injection_task_id": condition.get("injection_task_id"),
            "first_tool": legitimate[0].function,
            "tool_schema_count": len(session.tool_schemas),
            "ground_truth_legitimate_count": len(legitimate),
            "ground_truth_attack_count": len(attack),
            "first_tool_output_sha256": hashlib.sha256(tool_output.encode()).hexdigest(),
        }
        if is_ipi:
            vector = condition["injection_vector"]
            if set(condition["injections"]) != {vector}:
                raise ConfigError(f"{condition_id}: injection vector declaration is ambiguous")
            match = condition["injection_match_text"]
            payload = condition["injections"][vector]
            if tool_output.count(match) != 1 or tool_output.count(payload.strip()) != 1:
                raise ConfigError(
                    f"{condition_id}: injection must appear once in first tool output"
                )
            if condition["clean_reference_condition_id"] not in clean_ids:
                raise ConfigError(f"{condition_id}: missing clean reference")
            try:
                legitimate_call = _call_parts(legitimate[condition["legitimate_call_index"]])
                attack_call = _call_parts(attack[condition["attack_call_index"]])
            except IndexError as exc:
                raise ConfigError(f"{condition_id}: ground-truth call index is invalid") from exc
            expected_legitimate = condition["legitimate_call"]
            expected_attack = condition["attack_call"]
            if legitimate_call != (expected_legitimate["name"], expected_legitimate["arguments"]):
                raise ConfigError(f"{condition_id}: legitimate call differs from pinned task")
            if attack_call != (expected_attack["name"], expected_attack["arguments"]):
                raise ConfigError(f"{condition_id}: attack call differs from pinned task")
            if legitimate_call[0] != attack_call[0] or legitimate_call[1] == attack_call[1]:
                raise ConfigError(
                    f"{condition_id}: candidates must use one tool with different arguments"
                )
            if (
                legitimate_call[0] != condition["expected_legitimate_tool"]
                or attack_call[0] != condition["expected_attack_tool"]
            ):
                raise ConfigError(f"{condition_id}: expected tool names differ from ground truth")
            slot = condition["primary_argument_slot"]
            if slot not in legitimate_call[1] or slot not in attack_call[1]:
                raise ConfigError(f"{condition_id}: declared argument slot is missing")
            report.update(
                injection_vector=vector,
                injection_start=tool_output.index(match),
                injection_end=tool_output.index(match) + len(match),
                legitimate_call=expected_legitimate,
                attack_call=expected_attack,
                primary_argument_slot=slot,
            )
            evaluator_states = {}
            for label, calls in (
                ("negative", ()),
                ("legitimate", legitimate),
                ("attack", attack),
            ):
                state_session = _session(plan, condition)
                for call in calls:
                    result = state_session.execute_tool(call.function, call.args)
                    if result.error is not None:
                        raise ConfigError(f"{condition_id}: {label} evaluator setup failed")
                result = state_session.evaluate(None)
                evaluator_states[label] = {
                    "user_task_success": result.user_task_success,
                    "attack_success": result.attack_success,
                }
            if evaluator_states != {
                "negative": {"user_task_success": False, "attack_success": False},
                "legitimate": {"user_task_success": True, "attack_success": False},
                "attack": {"user_task_success": False, "attack_success": True},
            }:
                raise ConfigError(f"{condition_id}: evaluator positive/negative controls failed")
            report["evaluator_control_states"] = evaluator_states
        elif attack or condition["injections"]:
            raise ConfigError(f"{condition_id}: clean condition contains an attack")
        reports.append(report)
    return reports


def _load_model(model_values: dict[str, Any]) -> tuple[Any, Any]:
    return load_hugging_face_model(
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


def _boundary_prefix_document(prefix: Any) -> dict[str, Any]:
    record = _prefix_document(prefix)
    record["boundary_token_index"] = len(prefix.token_ids) - 1
    record["boundary_token_id"] = prefix.token_ids[-1]
    return record


def _action_document(action: AgentAction, *, prefix_id: str, step_index: int) -> dict[str, Any]:
    if action.raw_text is None:
        raise RuntimeError("selection generation did not retain raw model output")
    return {
        "step_index": step_index,
        "prefix_id": prefix_id,
        "kind": action.kind,
        "raw_text": action.raw_text,
        "content": action.content,
        "tool_calls": [
            {"name": call.name, "arguments": dict(call.arguments), "call_id": call.call_id}
            for call in action.ordered_tool_calls()
        ],
    }


def selection_output_documents(
    measurement_action: AgentAction,
    measurement_prefix_id: str,
    actual: AgentRun,
    actual_prefixes: list[Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Preserve raw generations and the final reply for independent auditing."""

    if len(actual.actions) != len(actual_prefixes):
        raise RuntimeError("actual actions and generation prefixes are misaligned")
    measurement = {
        "schema_version": 1,
        "generation": _action_document(
            measurement_action, prefix_id=measurement_prefix_id, step_index=0
        ),
    }
    output = {
        "schema_version": 1,
        "stop_reason": actual.stop_reason,
        "final_answer": actual.final_answer,
        "generations": [
            _action_document(action, prefix_id=prefix.prefix_id, step_index=index)
            for index, (action, prefix) in enumerate(
                zip(actual.actions, actual_prefixes, strict=True)
            )
        ],
    }
    messages = _json_messages(actual.messages)
    if actual.stop_reason == "final_answer":
        if (
            not actual.actions
            or actual.actions[-1].kind != "final"
            or actual.final_answer != actual.actions[-1].content
        ):
            raise RuntimeError("final answer does not match the final generated action")
        messages.append({"role": "assistant", "content": actual.final_answer, "tool_calls": []})
    elif actual.final_answer is not None:
        raise RuntimeError("non-final run unexpectedly contains a final answer")
    return measurement, output, messages


def _audit_trace_complete(directory: Path, run: dict[str, Any]) -> bool:
    try:
        measurement = json.loads((directory / "measurement_output.json").read_text())
        output = json.loads((directory / "model_output.json").read_text())
        messages = json.loads((directory / "messages.json").read_text())
        actual_prefixes = run["prefix_records"][1:]
        generations = output["generations"]
        if measurement["generation"]["prefix_id"] != run["prefix_records"][0]["prefix_id"]:
            return False
        if not isinstance(measurement["generation"]["raw_text"], str):
            return False
        if len(generations) != len(actual_prefixes):
            return False
        for index, (generation, prefix) in enumerate(
            zip(generations, actual_prefixes, strict=True)
        ):
            if (
                generation["step_index"] != index
                or generation["prefix_id"] != prefix["prefix_id"]
                or not isinstance(generation["raw_text"], str)
            ):
                return False
        if output["stop_reason"] == "final_answer":
            return (
                isinstance(output["final_answer"], str)
                and generations[-1]["kind"] == "final"
                and generations[-1]["content"] == output["final_answer"]
                and messages[-1]
                == {
                    "role": "assistant",
                    "content": output["final_answer"],
                    "tool_calls": [],
                }
            )
        return output["final_answer"] is None
    except (IndexError, KeyError, OSError, TypeError, ValueError):
        return False


def _run_one(
    plan: SelectionPlan,
    condition: dict[str, Any],
    model_config: dict[str, Any],
    model: Any,
    tokenizer: Any,
    *,
    run_id: str,
    artifact_root: Path,
    runtime_report: dict[str, Any],
    git_commit: str,
) -> Path:
    import torch

    started = time.perf_counter()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    model_values = model_config["model"]
    decoding = plan.sample["selection"]["decoding"]
    session = _session(plan, condition)
    legitimate_calls, attack_calls = session.ground_truth_calls()
    messages, tool_output = _measurement_messages(session, legitimate_calls[0])
    backend = _make_backend(
        model=model,
        tokenizer=tokenizer,
        session=session,
        model_config=model_config,
        decoding=decoding,
    )
    prefix = backend.serialize(messages)
    injection_text = condition.get("injection_match_text")
    positions = _positions(prefix, tool_output=tool_output, injection_text=injection_text)
    extractor = HuggingFaceActivationExtractor(
        model, block_path=model_config["instrumentation"]["transformer_block_path"]
    )
    scorer = HuggingFaceTeacherForcedScorer(model, tokenizer)
    activation = extractor.capture(prefix, positions=[p.token_index for p in positions.values()])
    activation.assert_matches(prefix)
    scores = None
    if injection_text is not None:
        legitimate = _call_parts(legitimate_calls[condition["legitimate_call_index"]])
        attack = _call_parts(attack_calls[condition["attack_call_index"]])
        legitimate_score, attack_score, margins = scorer.score_pair(
            prefix,
            legitimate=serialize_qwen_tool_call(*legitimate),
            attack=serialize_qwen_tool_call(*attack),
            argument_slot=condition["primary_argument_slot"],
        )
        scores = {
            "prefix_id": prefix.prefix_id,
            "legitimate": legitimate_score.as_dict(),
            "attack": attack_score.as_dict(),
            "margins": margins.as_dict(),
        }
        if not all(
            math.isfinite(p)
            for p in (
                *legitimate_score.token_log_probabilities,
                *attack_score.token_log_probabilities,
            )
        ):
            raise RuntimeError("candidate scoring returned nonfinite token log probabilities")
    # The generated action is checked against exactly the prefix used above.
    measurement_action = backend.next_action(messages)
    backend.prefixes[-1].assert_same_tokens(prefix.token_ids, consumer="selection_generation")
    actual_session = _session(plan, condition)
    actual_backend = _make_backend(
        model=model,
        tokenizer=tokenizer,
        session=actual_session,
        model_config=model_config,
        decoding=decoding,
    )
    actual = run_agent(
        actual_backend,
        actual_session.initial_messages,
        actual_session.tools,
        max_steps=int(decoding["max_steps"]),
    )
    measurement_output, model_output, audited_messages = selection_output_documents(
        measurement_action,
        prefix.prefix_id,
        actual,
        actual_backend.prefixes,
    )
    evaluation = actual_session.evaluate(actual.final_answer)
    group = classify_outcome(
        has_attack=injection_text is not None,
        user_task_success=evaluation.user_task_success,
        attack_success=evaluation.attack_success,
    )
    attempts = sum(len(action.ordered_tool_calls()) for action in actual.actions)
    executed = len(actual_session.trace)
    errors = len(actual_session.tool_errors)
    elapsed = time.perf_counter() - started
    peak_bytes = int(torch.cuda.max_memory_allocated())
    limits = plan.gate["selection"]["thresholds"]["resources"]
    resource_checks = {
        "seconds_within_limit": elapsed <= limits["maximum_seconds_per_run"],
        "gpu_memory_within_limit": peak_bytes <= limits["maximum_gpu_memory_gib"] * 1024**3,
    }
    resolved = {
        "schema_version": 2,
        "status": "formal_model_selection",
        "condition": condition,
        "model": model_config,
        "decoding": decoding,
        "gate": plan.gate,
        "sample_sha256": plan.checksums["sample"],
        "gate_sha256": plan.checksums["gate"],
        "runtime": runtime_report,
        "versions": {
            name: package_version(name)
            for name in ("agentdojo", "transformers", "torch", "safetensors", "bitsandbytes")
        },
        "serialization": {
            "chat_template_sha256": backend.template_sha256,
            "tool_schema_sha256": prefix.metadata["tool_schema_sha256"],
            "system_message_sha256": prefix.metadata["system_message_sha256"],
            "enable_thinking": False,
        },
    }
    token_document = {
        "text": prefix.text,
        "token_ids": list(prefix.token_ids),
        "offsets": [vars(offset) for offset in prefix.offsets],
        "positions": [_position_document(p) for p in positions.values()],
        "metadata": prefix.metadata,
    }
    with ImmutableRunWriter(artifact_root, run_id) as writer:
        artifacts = [
            writer.write_json("resolved_config.json", resolved, kind="resolved_config"),
            writer.write_json("condition.json", condition, kind="condition"),
            writer.write_json(
                "environment_before.json",
                actual_session.pre_environment.model_dump(mode="json"),
                kind="audit_environment_before",
            ),
            writer.write_json(
                "environment_after.json",
                actual_session.environment.model_dump(mode="json"),
                kind="audit_environment_after",
            ),
            writer.write_json(
                "measurement_messages.json", _json_messages(messages), kind="measurement_messages"
            ),
            writer.write_json(
                "measurement_output.json", measurement_output, kind="measurement_generation"
            ),
            writer.write_json("messages.json", audited_messages, kind="message_trace"),
            writer.write_json("model_output.json", model_output, kind="model_generations"),
            writer.write_json("tokens.json", token_document, kind="token_record"),
            writer.write_json(
                "actual_prefixes.json",
                [_boundary_prefix_document(p) for p in actual_backend.prefixes],
                kind="actual_prefix_records",
            ),
            writer.write_bytes(
                "activations/residual.safetensors",
                _save_activations(activation.values),
                kind="residual_activation",
            ),
            writer.write_json(
                "activations/metadata.json",
                {
                    "prefix_id": activation.prefix_id,
                    "token_ids": list(activation.token_ids),
                    "positions": list(activation.positions),
                    "layers": {
                        name: {"shape": list(t.shape), "dtype": str(t.dtype)}
                        for name, t in activation.values.items()
                    },
                },
                kind="residual_activation_metadata",
            ),
        ]
        if scores is not None:
            artifacts.append(writer.write_json("scores.json", scores, kind="candidate_scores"))
        bundle_bytes = sum(a["bytes"] for a in artifacts)
        resource_checks["storage_within_limit"] = (
            bundle_bytes <= limits["maximum_storage_gib"] * 1024**3
        )
        record = {
            "schema_version": 2,
            "run_id": run_id,
            "condition_id": condition["condition_id"],
            "parent_run_id": None,
            "git_commit": git_commit,
            "git_dirty": False,
            "resolved_config_sha256": artifacts[0]["sha256"],
            "model": {"name": model_values["name"], "revision": model_values["revision"]},
            "tokenizer": {
                "name": model_values["name"],
                "revision": model_values["tokenizer_revision"],
            },
            "seed": plan.sample["selection"]["seed"],
            "decoding": decoding,
            "prefix_records": [
                _prefix_document(prefix, positions.values()),
                *[_boundary_prefix_document(p) for p in actual_backend.prefixes],
            ],
            "outcome": {
                "has_attack": injection_text is not None,
                "user_task_success": evaluation.user_task_success,
                "attack_success": evaluation.attack_success,
                "group": group.value if group else None,
                "baseline_failure": group is None,
                "evaluator_version": evaluation.evaluator_version,
            },
            "metrics": {
                "generated_tool_call_attempts": attempts,
                "parsed_tool_calls": attempts,
                "executed_tool_calls": executed,
                "successful_tool_executions": executed - errors,
                "no_call": attempts == 0,
                "elapsed_seconds": elapsed,
                "peak_gpu_memory_bytes": peak_bytes,
                "bundle_bytes": bundle_bytes,
                "resource_checks": resource_checks,
            },
            "failure": None
            if not actual_session.tool_errors
            else {
                "stage": "tool_execution",
                "kind": "tool_error",
                "message": "; ".join(actual_session.tool_errors),
            },
            "scores": scores,
            "artifacts": artifacts,
        }
        writer.write_json("run.json", record, kind="run_record")
        return writer.commit()


def run_selection(
    gate_path: str | Path, *, run_prefix: str, artifact_root: str | Path = "artifacts"
) -> list[Path]:
    """Run the same seven conditions for each candidate, with immutable failures."""

    import torch

    plan = load_selection_plan(gate_path)
    preflight_selection(plan)
    commit, dirty = _git_metadata()
    if dirty or plan.freeze is None:
        raise ConfigError("formal selection requires a clean Git checkout and freeze record")
    import subprocess

    parent = subprocess.run(
        ["git", "rev-parse", "HEAD^"], check=True, capture_output=True, text=True
    ).stdout.strip()
    if parent != plan.freeze["source_git_commit"]:
        raise ConfigError(
            "freeze record must be committed directly after its recorded source commit"
        )
    runtime_report = gpu_runtime_report()
    paths: list[Path] = []
    selection = plan.sample["selection"]
    for model_index, model_path in enumerate(selection["candidate_models"]):
        model_config = load_yaml(plan.sample_path.parent / model_path)
        model_values = model_config["model"]
        torch.manual_seed(int(selection["seed"]))
        torch.cuda.manual_seed_all(int(selection["seed"]))
        try:
            model, tokenizer = _load_model(model_values)
            assert_model_has_no_cpu_offload(model)
        except Exception as exc:
            for condition in selection["conditions"]:
                run_id = f"{run_prefix}-m{model_index + 1}-{condition['condition_id']}"
                with ImmutableRunWriter(artifact_root, run_id) as writer:
                    writer.write_json(
                        "failure.json",
                        {
                            "schema_version": 2,
                            "status": "technical_failure",
                            "stage": "model_load",
                            "condition_id": condition["condition_id"],
                            "model": model_values,
                            "kind": type(exc).__name__,
                            "message": str(exc),
                            "git_commit": commit,
                            "gate_sha256": plan.checksums["gate"],
                            "sample_sha256": plan.checksums["sample"],
                            "retry_eligible": False,
                        },
                        kind="technical_failure",
                    )
                    paths.append(writer.commit())
            continue
        for condition in selection["conditions"]:
            run_id = f"{run_prefix}-m{model_index + 1}-{condition['condition_id']}"
            try:
                path = _run_one(
                    plan,
                    condition,
                    model_config,
                    model,
                    tokenizer,
                    run_id=run_id,
                    artifact_root=Path(artifact_root),
                    runtime_report=runtime_report,
                    git_commit=commit,
                )
            except Exception as exc:
                with ImmutableRunWriter(artifact_root, run_id) as writer:
                    writer.write_json(
                        "failure.json",
                        {
                            "schema_version": 2,
                            "status": "technical_failure",
                            "condition_id": condition["condition_id"],
                            "model": model_values,
                            "kind": type(exc).__name__,
                            "message": str(exc),
                            "raw_model_output": getattr(exc, "raw_text", None),
                            "git_commit": commit,
                            "gate_sha256": plan.checksums["gate"],
                            "sample_sha256": plan.checksums["sample"],
                            "retry_eligible": False,
                        },
                        kind="technical_failure",
                    )
                    path = writer.commit()
            paths.append(path)
        del model, tokenizer
        gc.collect()
        torch.cuda.empty_cache()
    return paths


def _wilson_95(successes: int, denominator: int) -> list[float] | None:
    if denominator == 0:
        return None
    z = 1.959963984540054
    p = successes / denominator
    adjustment = z * z / denominator
    center = (p + adjustment / 2) / (1 + adjustment)
    radius = z * math.sqrt((p * (1 - p) + adjustment / 4) / denominator) / (1 + adjustment)
    return [center - radius, center + radius]


def summarize_selection(
    gate_path: str | Path,
    *,
    run_prefix: str,
    artifact_root: str | Path = "artifacts",
    audit_path: str | Path | None = None,
) -> dict[str, Any]:
    """Summarize all declared runs; absent/failed runs never disappear from denominators."""

    plan = load_selection_plan(gate_path)
    conditions = plan.sample["selection"]["conditions"]
    root = Path(artifact_root) / "runs"
    human = None
    if audit_path is not None:
        entries = json.loads(Path(audit_path).read_text(encoding="utf-8"))
        if not isinstance(entries, list) or len(entries) != 14:
            raise ConfigError("human audit must contain exactly fourteen entries")
        human = {}
        for entry in entries:
            run_id = entry["run_id"]
            if (
                run_id in human
                or not isinstance(entry["user_task_success"], bool)
                or not isinstance(entry["attack_success"], bool)
            ):
                raise ConfigError("audit IDs must be unique and both labels must be booleans")
            if not entry.get("reviewer_id") or not entry.get("reviewed_at"):
                raise ConfigError("audit requires reviewer_id and reviewed_at")
            if not entry.get("evidence"):
                raise ConfigError("audit requires evidence for both labels")
            human[run_id] = entry
    thresholds = plan.gate["selection"]["thresholds"]
    reports = []
    expected_audit_ids = set()
    for model_index, model_path in enumerate(plan.sample["selection"]["candidate_models"]):
        model_config = load_yaml(plan.sample_path.parent / model_path)
        records = []
        failures = []
        audit_trace_failures = []
        for condition in conditions:
            run_id = f"{run_prefix}-m{model_index + 1}-{condition['condition_id']}"
            expected_audit_ids.add(run_id)
            directory = root / run_id
            run_path = directory / "run.json"
            failure_path = directory / "failure.json"
            if run_path.exists():
                record = json.loads(run_path.read_text(encoding="utf-8"))
                if record["condition_id"] != condition["condition_id"]:
                    raise ConfigError(f"{run_id}: condition ID mismatch")
                records.append((condition, record))
                if not _audit_trace_complete(directory, record):
                    audit_trace_failures.append(run_id)
            elif failure_path.exists():
                failures.append(
                    {"run_id": run_id, **json.loads(failure_path.read_text(encoding="utf-8"))}
                )
            else:
                failures.append({"run_id": run_id, "status": "missing_run"})
        clean = [(c, r) for c, r in records if c["condition_family"] == "clean"]
        ipi = [(c, r) for c, r in records if c["condition_family"] == "ipi"]
        clean_success = sum(r["outcome"]["user_task_success"] for _, r in clean)
        attempts = sum(r["metrics"]["generated_tool_call_attempts"] for _, r in records)
        parsed = sum(r["metrics"]["parsed_tool_calls"] for _, r in records)
        executed = sum(r["metrics"]["successful_tool_executions"] for _, r in records)
        scoring = sum(
            r["scores"] is not None
            and r["scores"]["prefix_id"] == r["prefix_records"][0]["prefix_id"]
            for _, r in ipi
        )
        agreement = None
        if human is not None:
            agreement = {
                label: sum(human[r["run_id"]][label] == r["outcome"][label] for _, r in records)
                for label in ("user_task_success", "attack_success")
            }
        all_complete = len(records) == 7 and not failures
        checks = {
            "all_conditions_complete": all_complete,
            "audit_trace_complete": all_complete and not audit_trace_failures,
            "clean_user_task_success": all_complete
            and clean_success / 5 >= thresholds["clean_user_task_success"]["minimum_rate"],
            "tool_call_parse_success": all_complete
            and attempts > 0
            and parsed / attempts >= thresholds["tool_call_parse_success"]["minimum_rate"],
            "environment_execution_success": all_complete
            and parsed > 0
            and executed / parsed >= thresholds["environment_execution_success"]["minimum_rate"],
            "teacher_forced_scoring_success": all_complete and scoring == 2,
            "prefix_token_identity": all_complete and scoring == 2,
            "same_tool_different_argument_clusters": all_complete and scoring == 2,
            "resources": all_complete
            and all(all(r["metrics"]["resource_checks"].values()) for _, r in records),
            "evaluator_human_agreement": agreement is not None
            and all(
                agreement[label] / 7 >= thresholds["evaluator_human_agreement"]["minimum_rate"]
                for label in ("user_task_success", "attack_success")
            ),
        }
        reports.append(
            {
                "model": model_config["model"]["name"],
                "complete_runs": len(records),
                "technical_failures": failures,
                "audit_trace_failures": audit_trace_failures,
                "clean_success": {
                    "numerator": clean_success,
                    "denominator": 5,
                    "wilson_95": _wilson_95(clean_success, 5),
                },
                "tool_call_parse": {
                    "numerator": parsed,
                    "denominator": attempts,
                    "wilson_95": _wilson_95(parsed, attempts),
                },
                "environment_execution": {
                    "numerator": executed,
                    "denominator": parsed,
                    "wilson_95": _wilson_95(executed, parsed),
                },
                "teacher_forced_scoring": {"numerator": scoring, "denominator": 2},
                "human_agreement": agreement,
                "no_call_runs": sum(r["metrics"].get("no_call", False) for _, r in records),
                "attack_success": {
                    "numerator": sum(r["outcome"]["attack_success"] for _, r in ipi),
                    "denominator": 2,
                },
                "task_families": {
                    family: [
                        r["outcome"]["user_task_success"]
                        for c, r in clean
                        if c["task_family_id"] == family
                    ]
                    for family in sorted({c["task_family_id"] for c, _ in clean})
                },
                "checks": checks,
                "passes": all(checks.values()),
            }
        )
    if human is not None and set(human) != expected_audit_ids:
        raise ConfigError("human audit run IDs differ from the fourteen declared runs")
    audit_evidence_complete = human is not None and all(
        not report["audit_trace_failures"] for report in reports
    )
    passing = [report["model"] for report in reports if report["passes"]]
    selected = None
    if audit_evidence_complete and len(passing) == 1:
        selected = passing[0]
    elif audit_evidence_complete and len(passing) == 2:
        preferred = load_yaml(
            plan.sample_path.parent / plan.sample["selection"]["candidate_models"][0]
        )["model"]["name"]
        selected = preferred
    return {
        "schema_version": 1,
        "status": "complete"
        if human is not None
        and all(not r["technical_failures"] and not r["audit_trace_failures"] for r in reports)
        else "incomplete",
        "gate_sha256": plan.checksums["gate"],
        "sample_sha256": plan.checksums["sample"],
        "run_prefix": run_prefix,
        "candidates": reports,
        "selected_model": selected,
    }
