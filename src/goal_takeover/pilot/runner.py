"""Immutable, staged execution of the frozen exploratory Banking pilot."""

from __future__ import annotations

import json
import signal
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from goal_takeover.agent import run_agent
from goal_takeover.config import ConfigError
from goal_takeover.models.qwen import QwenToolCallParseError
from goal_takeover.pilot.evaluation import (
    RecordingSession,
    outcome_document,
    state_checksum,
    state_document,
    strict_evaluation,
)
from goal_takeover.pilot.measurement import measurement_positions
from goal_takeover.pilot.plan import PilotPlan, load_pilot_plan, load_runtime_freeze
from goal_takeover.pilot.preflight import preflight_pilot
from goal_takeover.pilot.report import condition_run_id, load_records, summarize_pilot
from goal_takeover.shakedown import _git_metadata, _json_messages
from goal_takeover.storage.run_writer import (
    ImmutableRunWriter,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)


class ExternalInfrastructureInterruption(RuntimeError):
    """Explicit host/transport interruption, never inferred from model errors."""


@contextmanager
def condition_deadline(seconds: float):
    """Use a POSIX deadline on the supported WSL execution host."""
    if not hasattr(signal, "setitimer"):
        raise RuntimeError("pilot deadlines require POSIX; run on the documented WSL host")

    def timeout(_signum: int, _frame: Any) -> None:
        raise TimeoutError("oom_or_resource_limit: condition wall-time ceiling exceeded")

    previous = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _prefix_document(prefix: Any) -> dict[str, Any]:
    return {
        "prefix_id": prefix.prefix_id,
        "boundary": prefix.boundary.value,
        "text": prefix.text,
        "serialized_text_sha256": sha256_bytes(prefix.text.encode("utf-8")),
        "token_ids": list(prefix.token_ids),
        "attention_mask": [1] * len(prefix.token_ids),
        "offsets": [
            {"token_index": o.token_index, "token_id": o.token_id, "start": o.start, "end": o.end}
            for o in prefix.offsets
        ],
        "metadata": prefix.metadata,
        "boundary_token_index": len(prefix.token_ids) - 1,
        "boundary_token_id": prefix.token_ids[-1],
    }


def execute_condition(
    plan: PilotPlan,
    runtime: dict[str, Any],
    services: Any,
    *,
    condition: dict[str, Any],
    artifact_root: str | Path,
    run_id: str,
    runtime_sha256: str,
    parent_run_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Persist partial traces on failure; model errors are never regenerated."""
    started = time.perf_counter()
    started_at = datetime.now(UTC).isoformat()
    git_commit, git_dirty = _git_metadata()
    capture = runtime["capture"]
    session = recorder = backend = None
    prefixes, generations, messages, measurements = [], [], [], []
    initial = final = None
    outcome = diagnostic = failure = None
    stage, last_stage = "condition_setup", None
    model_output_count, actual_exposed_scored = 0, False
    peak_memory = 0
    written_bytes = 0
    records = []
    with ImmutableRunWriter(artifact_root, run_id) as writer:

        def write_json(name: str, value: Any, kind: str) -> None:
            nonlocal written_bytes
            record = writer.write_json(name, value, kind=kind)
            records.append(record)
            written_bytes += record["bytes"]

        def write_bytes(name: str, value: bytes, kind: str) -> None:
            nonlocal written_bytes
            if (
                written_bytes + len(value)
                > plan.config["resources"]["maximum_storage_gib_per_condition"] * 2**30
            ):
                raise RuntimeError("oom_or_resource_limit: tensor artifact exceeds storage ceiling")
            record = writer.write_bytes(name, value, kind=kind)
            records.append(record)
            written_bytes += record["bytes"]

        def check_resources() -> None:
            nonlocal peak_memory
            peak_memory = max(peak_memory, services.check_memory())
            resources = plan.config["resources"]
            if (
                time.perf_counter() - started > resources["maximum_seconds_per_condition"]
                or written_bytes > resources["maximum_storage_gib_per_condition"] * 2**30
            ):
                raise RuntimeError("oom_or_resource_limit: condition resource ceiling exceeded")

        def measure(
            current_backend: Any,
            current_messages: list[dict[str, Any]],
            *,
            scope: str,
            resolve_exposure: bool,
            capture_activations: bool = True,
        ) -> tuple[Any, dict[str, Any]]:
            nonlocal stage, last_stage
            stage = f"{scope}_serialization"
            prefix = current_backend.serialize(current_messages)
            if prefix.metadata["tool_schema_sha256"] != runtime["tool_schema_sha256"]:
                raise ValueError("runtime tool schema checksum mismatch")
            positions_doc, indices, ranges = measurement_positions(
                prefix,
                current_messages,
                condition,
                capture if capture_activations else {**capture, "full_sequence_condition_ids": []},
                resolve_exposure=resolve_exposure,
            )
            for position in positions_doc["positions"]:
                offset = prefix.offsets[position["token_index"]]
                position["offset_start"] = offset.start
                position["offset_end"] = offset.end
                position["decoded_token"] = (
                    current_backend.tokenizer.decode([position["token_id"]])
                    if hasattr(current_backend, "tokenizer")
                    else prefix.text[offset.start : offset.end]
                )
            index = len(measurements)
            prefix_doc = {
                **_prefix_document(prefix),
                "scope": scope,
                "measurement": positions_doc,
                "step_index": index,
            }
            prefixes.append(prefix_doc)
            if capture_activations:
                stage = f"{scope}_capture"
                activation, attention, full = services.capture(
                    prefix,
                    indices,
                    ranges,
                    full_attention=condition["condition_id"]
                    in capture["full_sequence_attention_condition_ids"],
                )
                # Keep the consumer input independently reconstructable from raw artifacts.
                activation.assert_matches(prefix)
                if activation.positions != indices:
                    raise ValueError("activation position mismatch")
                write_bytes(
                    f"measurements/{index}/residual.safetensors",
                    services.activation_bytes(activation),
                    "residual_activation",
                )
                metadata = {
                    "prefix_id": activation.prefix_id,
                    "token_ids": list(activation.token_ids),
                    "positions": list(activation.positions),
                    "layers": {
                        name: {"shape": list(t.shape), "dtype": str(t.dtype)}
                        for name, t in activation.values.items()
                    },
                }
                write_json(f"measurements/{index}/activation.json", metadata, "activation_metadata")
                if attention.get("prefix_id") != prefix.prefix_id or attention.get(
                    "prefix_token_ids"
                ) != list(prefix.token_ids):
                    raise ValueError("attention prefix token mismatch")
                write_json(
                    f"measurements/{index}/attention.json", attention, "attention_aggregates"
                )
                if full is not None:
                    write_bytes(
                        f"measurements/{index}/attention.safetensors", full, "full_attention"
                    )
            else:
                metadata = {
                    "prefix_id": prefix.prefix_id,
                    "status": "not_captured_fixed_prefix_scoring_diagnostic",
                }
            scores = None
            if positions_doc["exposed"] and condition["intervention_span_in_vector"] is not None:
                stage = f"{scope}_scoring"
                scores = services.score(prefix, condition)
                if scores.get("prefix_id") != prefix.prefix_id or scores.get(
                    "prefix_token_ids"
                ) != list(prefix.token_ids):
                    raise ValueError("scorer prefix token mismatch")
                # Also rejects NaN/Infinity in test adapters and future scoring implementations.
                json.dumps(scores, allow_nan=False)
                write_json(f"measurements/{index}/scores.json", scores, "candidate_scores")
            measurement = {
                "scope": scope,
                "prefix_id": prefix.prefix_id,
                "index": index,
                "positions": positions_doc,
                "scores": scores,
                "activation": metadata,
                "prefix_token_identity": True,
            }
            measurements.append(measurement)
            last_stage = stage
            check_resources()
            return prefix, measurement

        try:
            with condition_deadline(plan.config["resources"]["maximum_seconds_per_condition"]):
                services.start_condition()
                session = services.session(condition)
                recorder = RecordingSession(session)
                initial = state_document(session.environment)
                backend = services.backend(session)
                messages = _json_messages(session.initial_messages)
                exposure_captured = False

                class MeasuredBackend:
                    def next_action(self, current_messages: Any) -> Any:
                        nonlocal messages, exposure_captured, actual_exposed_scored
                        nonlocal stage, last_stage, model_output_count
                        messages = _json_messages(current_messages)
                        prefix, measured = measure(
                            backend,
                            messages,
                            scope="actual",
                            resolve_exposure=not exposure_captured,
                        )
                        if measured["positions"]["exposed"]:
                            exposure_captured = True
                            actual_exposed_scored = (
                                condition["has_attack"] and measured["scores"] is not None
                            )
                        stage = "actual_generation"
                        count_before = len(backend.generations)
                        try:
                            action = backend.next_action_from_prefix(prefix)
                        finally:
                            for generation in backend.generations[count_before:]:
                                model_output_count += 1
                                generations.append({"scope": "actual", **generation})
                            check_resources()
                        backend.prefixes[-1].assert_same_tokens(
                            prefix.token_ids, consumer="generation"
                        )
                        if not generations or generations[-1]["prefix_id"] != prefix.prefix_id:
                            raise ValueError("missing raw model generation or prefix identity")
                        generations[-1]["parsed_action"] = {
                            "kind": action.kind,
                            "content": action.content,
                            "tool_calls": [
                                {
                                    "name": call.name,
                                    "arguments": dict(call.arguments),
                                    "call_id": call.call_id,
                                }
                                for call in action.ordered_tool_calls()
                            ],
                        }
                        last_stage = stage
                        return action

                actual = None
                model_error = None
                try:
                    actual = run_agent(
                        MeasuredBackend(),
                        session.initial_messages,
                        recorder.tools,
                        max_steps=plan.config["experiment"]["max_steps"],
                    )
                except QwenToolCallParseError as exc:
                    model_error = str(exc)
                    if not generations:
                        model_output_count += 1
                        generations.append(
                            {"scope": "actual", "raw_text": exc.raw_text, "parser_error": str(exc)}
                        )
                    else:
                        generations[-1]["parser_error"] = str(exc)
                if actual is not None:
                    messages = _json_messages(actual.messages)
                    if actual.final_answer is not None:
                        messages.append(
                            {"role": "assistant", "content": actual.final_answer, "tool_calls": []}
                        )
                    if actual.stop_reason != "final_answer" or session.tool_errors:
                        model_error = actual.stop_reason + "; " + "; ".join(session.tool_errors)
                stage = "actual_evaluation"
                final = state_document(session.environment)
                final_answer = actual.final_answer if actual else None
                native = session.evaluate(final_answer)
                strict = strict_evaluation(
                    condition, plan.evaluator, initial, final, recorder.events
                )
                outcome = outcome_document(condition, native, strict)
                if model_error:
                    failure = {
                        "kind": "model_failure",
                        "stage": "actual_agent_loop",
                        "message": model_error,
                        "exception_type": "ModelBehaviorError",
                    }
                last_stage = stage
                # Only the 12 declared lead IPI require a separate fixed-prefix diagnostic.
                if condition["stage"] == "lead" and condition["has_attack"]:
                    stage = "diagnostic_setup"
                    diag_session = services.session(condition)
                    diag_recorder = RecordingSession(diag_session)
                    diag_initial = state_document(diag_session.environment)
                    first = condition["first_tool_call"]
                    result = diag_recorder.execute(
                        first["name"], first["arguments"], "diagnostic_0000"
                    )
                    if result.error is not None:
                        raise RuntimeError("fixed-prefix diagnostic tool failed")
                    diag_messages = [
                        *diag_session.initial_messages,
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {"id": "diagnostic_0000", "type": "function", "function": first}
                            ],
                        },
                        {
                            "role": "tool",
                            "name": first["name"],
                            "tool_call_id": "diagnostic_0000",
                            "content": result.content,
                            "error": None,
                            "untrusted": True,
                        },
                    ]
                    _, measured = measure(
                        services.backend(diag_session),
                        diag_messages,
                        scope="fixed_prefix_diagnostic",
                        resolve_exposure=True,
                        capture_activations=False,
                    )
                    if not measured["positions"]["exposed"] or measured["scores"] is None:
                        raise ValueError("diagnostic injection is missing")
                    diagnostic = {
                        "finite_scoring": True,
                        "prefix_token_identity": True,
                        "measurement_index": measured["index"],
                        "messages": diag_messages,
                        "events": diag_recorder.events,
                        "initial_state": diag_initial,
                        "final_state": state_document(diag_session.environment),
                    }
                    write_json("diagnostic.json", diagnostic, "fixed_prefix_diagnostic")
                check_resources()
        except Exception as exc:
            failure = {
                "kind": "technical_failure",
                "stage": stage,
                "message": str(exc),
                "exception_type": type(exc).__name__,
                "last_completed_stage": last_stage,
            }
            if isinstance(exc, QwenToolCallParseError):
                failure["raw_text"] = exc.raw_text
            retry_eligible = (
                isinstance(exc, ExternalInfrastructureInterruption) and model_output_count == 0
            )
        else:
            retry_eligible = False
        if session is not None:
            final = state_document(session.environment)
        # Flush the complete or partial trace even after timeout/OOM/alignment failure.
        resolved = {
            "sample": plan.config,
            "runtime_freeze": runtime,
            "model_config": plan.model_config,
            "domain_config": plan.domain_config,
            "runtime_report": services.runtime_report,
        }
        write_json("resolved_config.json", resolved, "resolved_config")
        write_json("condition.json", condition, "condition")
        write_json("messages.json", messages, "message_trace")
        write_json(
            "model_output.json",
            {
                "generations": generations,
                "final_answer": (
                    messages[-1]["content"]
                    if messages
                    and messages[-1]["role"] == "assistant"
                    and not messages[-1].get("tool_calls")
                    else None
                ),
            },
            "model_output",
        )
        write_json("prefixes.json", prefixes, "prefix_records")
        write_json("tool_events.json", recorder.events if recorder else [], "tool_event_log")
        write_json(
            "states.json",
            {
                "initial": initial,
                "final": final,
                "initial_sha256": state_checksum(initial) if initial is not None else None,
                "final_sha256": state_checksum(final) if final is not None else None,
            },
            "environment_states",
        )
        limit = plan.config["resources"]["maximum_storage_gib_per_condition"] * 2**30
        if written_bytes > limit:
            failure = {
                "kind": "technical_failure",
                "stage": "artifact_write",
                "message": "oom_or_resource_limit: serialized bundle exceeds storage ceiling",
            }
            retry_eligible = False
        record = {
            "schema_version": 1,
            "run_id": run_id,
            "condition_id": condition["condition_id"],
            "parent_run_id": parent_run_id,
            "sample_freeze_sha256": plan.sample_freeze_sha256,
            "runtime_freeze_sha256": runtime_sha256,
            "git_commit": git_commit,
            "git_dirty": git_dirty,
            "started_at": started_at,
            "ended_at": datetime.now(UTC).isoformat(),
            "model": {
                "name": plan.model_config["model"]["name"],
                "revision": plan.model_config["model"]["revision"],
            },
            "tokenizer": {
                "name": plan.model_config["model"]["name"],
                "revision": plan.model_config["model"]["tokenizer_revision"],
            },
            "resolved_config_sha256": sha256_bytes(canonical_json_bytes(resolved)),
            "seed": plan.config["experiment"]["seed"],
            "decoding": plan.config["decoding"],
            "split": condition["split"],
            "group_id": condition["group_id"],
            "task_openness": condition["task_openness"],
            "status": failure["kind"] if failure else "completed",
            "failure": failure,
            "retry_eligible": retry_eligible,
            "model_output_count": model_output_count,
            "actual_exposed_scored": actual_exposed_scored,
            "actual_measurement_missing_reason": (
                None
                if actual_exposed_scored
                else "no_observed_assistant_boundary_with_declared_vector"
                if condition["has_attack"]
                else "not_an_ipi_condition"
            ),
            "diagnostic": diagnostic,
            "outcome": outcome,
            "measurements": measurements,
            "elapsed_seconds": time.perf_counter() - started,
            "peak_gpu_memory_bytes": peak_memory,
            "artifacts": records.copy(),
        }
        from jsonschema import validate

        schema_path = plan.config_path.parents[2] / "data/schemas/pilot_run.schema.json"
        validate(record, json.loads(schema_path.read_text()))
        write_json("run.json", record, "run_record")
        # Include record and manifest overhead in the final storage check.
        projected = written_bytes + len(
            canonical_json_bytes({"schema_version": 1, "run_id": run_id, "artifacts": records})
        )
        if projected > limit and record["status"] != "technical_failure":
            # Existing bytes cannot be rewritten; preserve a separate resource-stop artifact.
            write_json(
                "resource_stop.json",
                {"kind": "technical_failure", "bytes": projected},
                "resource_stop",
            )
            record["status"] = "technical_failure"
            record["failure"] = {
                "kind": "technical_failure",
                "stage": "artifact_write",
                "message": "bundle overhead exceeds storage ceiling",
            }
        path = writer.commit()
    return path, record


def _validate_post_gate_continuation(
    plan: PilotPlan,
    artifact_root: str | Path,
    run_prefix: str,
    report: dict[str, Any],
    audit_path: str | Path | None,
    authorization_path: str | Path,
) -> dict[str, Any]:
    """Permit only the documented failed-clean-gate continuation of this pilot."""
    authorization = json.loads(Path(authorization_path).read_text())
    if (
        authorization.get("schema_version") != 1
        or authorization.get("decision_id") != "RDR-2026-10-07-01"
        or authorization.get("run_prefix") != run_prefix
        or authorization.get("sample_freeze_sha256") != plan.sample_freeze_sha256
    ):
        raise ConfigError("post-gate continuation authorization does not match this pilot")
    expected_conditions = [c for c in plan.conditions if c["stage"] == "expansion"]
    if len(expected_conditions) != 72 or authorization.get("condition_ids") != [
        c["condition_id"] for c in expected_conditions
    ]:
        raise ConfigError("post-gate continuation must preserve all 72 frozen conditions")
    if (
        report["lead_to_expansion"]
        or report["expansion_status"] != "gate_failed"
        or report["clean_success_count"] != 2
        or report["clean_denominator"] != 6
        or report["recorded_conditions"] != 18
        or report["technical_failures"]
        or report["unresolved_disagreements"]
        or not all(value for key, value in report["lead_checks"].items() if key != "clean_success")
    ):
        raise ConfigError("post-gate continuation requires the audited 2/6 clean-only gate failure")
    repo = plan.config_path.parents[2]
    source_files = {
        "decision": repo
        / "docs/decisions/2026-10-07_banking_pilot_post_gate_exploratory_continuation.md",
        "lead_report": repo / "artifacts/pilot-lead-report-2026-10-06.json",
        "lead_audit": Path(audit_path).resolve() if audit_path is not None else None,
        "lead_stage_manifest": Path(artifact_root)
        / "runs"
        / f"{run_prefix}-lead-status"
        / "manifest.json",
        "lead_runtime_freeze": repo / "artifacts/pilot-runtime.freeze.json",
    }
    digests = authorization.get("source_sha256")
    if not isinstance(digests, dict) or set(digests) != set(source_files):
        raise ConfigError("post-gate continuation source checksums are incomplete")
    for name, path in source_files.items():
        if path is None or not path.is_file() or sha256_file(path) != digests[name]:
            raise ConfigError(f"post-gate continuation source mismatch: {name}")
    frozen_report = json.loads(source_files["lead_report"].read_text())
    if report != frozen_report:
        raise ConfigError("post-gate continuation lead report differs from immutable evidence")
    if authorization.get("lead_runtime_freeze_sha256") != digests["lead_runtime_freeze"]:
        raise ConfigError("post-gate continuation runtime lineage mismatch")
    return authorization


def run_pilot(
    config_path: str | Path,
    runtime_path: str | Path,
    *,
    run_prefix: str,
    stage: str = "lead",
    artifact_root: str | Path | None = None,
    audit_path: str | Path | None = None,
    continuation_path: str | Path | None = None,
) -> tuple[Path, ...]:
    """Validate every gate before weights; execute only the requested frozen stage."""
    plan = load_pilot_plan(config_path)
    runtime = load_runtime_freeze(plan, runtime_path)
    root = artifact_root or plan.config["resources"]["artifact_root"]
    # Validate identifiers before using them in paths/globs or loading weights.
    ImmutableRunWriter(root, f"{run_prefix}-{stage}-status")
    existing = load_records(plan, root, run_prefix)
    audit = json.loads(Path(audit_path).read_text()) if audit_path is not None else None
    report = summarize_pilot(plan, existing, audit=audit)
    if stage not in {"lead", "expansion"}:
        raise ConfigError("pilot stage must be lead or expansion")
    continuation = None
    if continuation_path is not None:
        if stage != "expansion":
            raise ConfigError("post-gate continuation applies only to expansion")
        continuation = _validate_post_gate_continuation(
            plan, root, run_prefix, report, audit_path, continuation_path
        )
    if stage == "expansion" and not report["lead_to_expansion"] and continuation is None:
        raise ConfigError("expansion blocked by frozen lead/audit gate")
    selected = [c for c in plan.conditions if c["stage"] == stage]
    if any(r["condition_id"] in {c["condition_id"] for c in selected} for r in existing):
        raise ConfigError("stage already has attempts; never rerun existing conditions")
    runtime_sha256 = sha256_file(Path(runtime_path))
    preceding_runtime_sha256 = (
        continuation["lead_runtime_freeze_sha256"] if continuation else runtime_sha256
    )
    if any(r["runtime_freeze_sha256"] != preceding_runtime_sha256 for r in existing):
        raise ConfigError("runtime freeze differs from preceding stage")
    previous_seconds = 0.0
    if stage == "expansion":
        previous_path = Path(root) / "runs" / f"{run_prefix}-lead-status"
        manifest = json.loads((previous_path / "manifest.json").read_text())
        declared = set()
        for artifact in manifest["artifacts"]:
            relative = Path(artifact["relative_path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ConfigError("unsafe stage artifact path")
            declared.add(str(relative))
            if sha256_file(previous_path / relative) != artifact["sha256"]:
                raise ConfigError("preceding stage checksum mismatch")
        if not {"stage.json", "resolved_config.json", "native_preflight.json"}.issubset(declared):
            raise ConfigError("preceding stage lacks required provenance")
        previous_status = json.loads((previous_path / "stage.json").read_text())
        if (
            previous_status["runtime_freeze_sha256"] != preceding_runtime_sha256
            or previous_status["sample_freeze_sha256"] != plan.sample_freeze_sha256
            or previous_status["stop"] is not None
        ):
            raise ConfigError("preceding stage stopped or uses a different freeze")
        previous_seconds = previous_status["elapsed_seconds"]
    for condition in selected:
        for attempt in (1, 2):
            if (Path(root) / "runs" / condition_run_id(run_prefix, condition, attempt)).exists():
                raise ConfigError("immutable pilot attempt already exists")
    status_id = f"{run_prefix}-{stage}-status"
    if (Path(root) / "runs" / status_id).exists():
        raise ConfigError("immutable stage status already exists")
    paths = []
    new_records = []
    stop = None
    preflight = None
    batch_started = time.perf_counter()
    try:
        preflight = preflight_pilot(plan)
        from goal_takeover.pilot.services import HuggingFacePilotServices

        services = HuggingFacePilotServices(plan, runtime)
        total_started = batch_started
        for condition in selected:
            parent = None
            for attempt in (1, 2):
                attempt_count = report["attempts"] + len(paths)
                storage = sum(
                    p.stat().st_size
                    for p in (Path(root) / "runs").glob(f"{run_prefix}-*/**/*")
                    if p.is_file()
                )
                resources = plan.config["resources"]
                if (
                    attempt_count >= resources["maximum_total_attempts"]
                    or storage + resources["maximum_storage_gib_per_condition"] * 2**30
                    > resources["maximum_total_storage_gib"] * 2**30
                    or previous_seconds + time.perf_counter() - total_started
                    >= resources["maximum_total_wall_seconds"]
                ):
                    raise RuntimeError("oom_or_resource_limit: batch resource ceiling")
                path, record = execute_condition(
                    plan,
                    runtime,
                    services,
                    condition=condition,
                    artifact_root=root,
                    run_id=condition_run_id(run_prefix, condition, attempt),
                    runtime_sha256=runtime_sha256,
                    parent_run_id=parent,
                )
                paths.append(path)
                if record["retry_eligible"] and attempt == 1:
                    parent = record["run_id"]
                    continue
                new_records.append(record)
                if record["status"] == "technical_failure":
                    stop = record["failure"]
                break
            if stop is not None:
                break
    except Exception as exc:
        stop = {
            "kind": "technical_failure",
            "message": str(exc),
            "exception_type": type(exc).__name__,
        }
    with ImmutableRunWriter(root, status_id) as writer:
        writer.write_json(
            "resolved_config.json",
            {
                "sample": plan.config,
                "runtime_freeze": runtime,
                "model_config": plan.model_config,
                "domain_config": plan.domain_config,
            },
            kind="resolved_config",
        )
        if preflight is not None:
            writer.write_json("native_preflight.json", preflight, kind="native_preflight")
        accounted = {r["condition_id"] for r in [*existing, *new_records]}
        writer.write_json(
            "stage.json",
            {
                "schema_version": 1,
                "stage": stage,
                "sample_freeze_sha256": plan.sample_freeze_sha256,
                "runtime_freeze_sha256": runtime_sha256,
                "git_commit": _git_metadata()[0],
                "elapsed_seconds": time.perf_counter() - batch_started,
                "stop": stop,
                "status": "technical_stop" if stop else "awaiting_human_audit",
                "audit_sha256": sha256_file(Path(audit_path)) if audit_path else None,
                "post_gate_continuation": {
                    "decision_id": continuation["decision_id"],
                    "authorization_sha256": sha256_file(Path(continuation_path)),
                    "original_lead_gate_passed": False,
                }
                if continuation
                else None,
                "run_paths": [str(p.relative_to(Path(root))) for p in paths],
                "conditions": [
                    {
                        "condition_id": c["condition_id"],
                        "status": "recorded" if c["condition_id"] in accounted else "not_run",
                        "reason": None
                        if c["condition_id"] in accounted
                        else "technical_stop"
                        if stop
                        else "awaiting_lead_gate",
                    }
                    for c in plan.conditions
                ],
            },
            kind="pilot_stage_status",
        )
        paths.append(writer.commit())
    if stop is not None:
        raise RuntimeError(f"pilot stopped; immutable status at {paths[-1]}: {stop['message']}")
    return tuple(paths)
