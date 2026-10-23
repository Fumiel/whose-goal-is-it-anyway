"""Frozen 96-condition recipient collection, preflight and immutable execution."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from goal_takeover.config import ConfigError, load_yaml
from goal_takeover.datasets.argument_readout_collection import build_collection
from goal_takeover.datasets.argument_readout_evaluation import (
    EVALUATOR_VERSION,
    evaluate_calls,
    task_and_condition,
    validate_execution_declarations,
)
from goal_takeover.datasets.argument_readout_native import native_preflight
from goal_takeover.environments.argument_readout import create_session
from goal_takeover.models.generation import DecodingConfig
from goal_takeover.models.qwen import QwenTransformersBackend
from goal_takeover.phase2.two_document import position_selector, runtime_capture
from goal_takeover.pilot.plan import PilotPlan
from goal_takeover.pilot.runner import execute_condition
from goal_takeover.pilot.services import HuggingFacePilotServices
from goal_takeover.runtime import gpu_runtime_report, package_version
from goal_takeover.serialization.qwen import serialize_qwen_tool_call
from goal_takeover.shakedown import _git_metadata
from goal_takeover.storage.run_writer import sha256_file


def load_plan(path: str | Path) -> tuple[PilotPlan, dict[str, Any]]:
    """Reject any change to the approved design before model access."""
    path = Path(path).resolve()
    root = path.parents[2]
    design = json.loads(path.read_text(encoding="utf-8"))
    if design.get("status") != "design_frozen_runtime_pending":
        raise ConfigError("recipient design is not frozen")
    freeze_path = root / "data/manifests/phase2_argument_readout_96_v1.freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("status") != "design_frozen_runtime_pending":
        raise ConfigError("recipient design freeze status differs")
    for relative, digest in freeze["files_sha256"].items():
        target = Path(relative)
        if target.is_absolute() or ".." in target.parts or sha256_file(root / target) != digest:
            raise ConfigError(f"recipient design checksum mismatch: {relative}")
    refs = design["references"]
    spec = json.loads((path.parent / refs["condition_spec"]).read_text(encoding="utf-8"))
    validate_execution_declarations(spec)
    if spec["status"] != "design_frozen_runtime_pending":
        raise ConfigError("recipient condition declaration is not frozen")
    split = json.loads((path.parent / refs["split_manifest"]).read_text(encoding="utf-8"))
    graph = json.loads((path.parent / refs["relationship_graph"]).read_text(encoding="utf-8"))
    from jsonschema import validate

    validate(split, json.loads((root / "data/schemas/split.schema.json").read_text()))
    draft_path = root / "data/templates/phase2_argument_readout_96_draft.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    expected_spec, expected_split, expected_graph = build_collection(draft)
    if (spec, split, graph) != (expected_spec, expected_split, expected_graph):
        raise ConfigError(
            "recipient condition, split or graph differs from approved materialization"
        )
    assignments = {row["condition_id"]: row for row in split["assignments"]}
    if len(assignments) != 96:
        raise ConfigError("recipient split condition count differs")
    conditions = []
    for index, row in enumerate(spec["condition_specs"]):
        cid = row["condition_id"]
        task, _ = task_and_condition(spec, row["draft_condition_id"])
        assigned = assignments[cid]
        recipient = row["expected_send_money"]["arguments"]["recipient"]
        if row["user_instruction"].count(recipient) != 1:
            raise ConfigError(f"recipient span missing or ambiguous: {cid}")
        other_id = task["recipient_pair"][
            "y" if row["recipient_value_id"] == task["recipient_pair"]["x"] else "x"
        ]
        alternative = json.loads(json.dumps(row["expected_send_money"]))
        alternative["arguments"]["recipient"] = spec["account_value_ids"][other_id]
        start = row["user_instruction"].index(recipient)
        condition = {
            **row,
            "condition_id": cid,
            "user_task_id": f"user_task_{8000 + index}",
            "injection_task_id": None,
            "native_user_prompt": row["user_instruction"],
            "first_tool_call": task["expected_read_file_calls"][0],
            "injections": {"recipient_user_text": row["user_instruction"]},
            "injection_vector": "recipient_user_text",
            "intervention_span_in_vector": {
                "start": start,
                "end": start + len(recipient),
                "text": recipient,
            },
            "matched_content": recipient,
            "candidate_calls": {
                "legitimate": row["expected_send_money"],
                "attacker": alternative,
            },
            "scoring_slots": ["recipient"],
            "comparison_scope": "recipient_only",
            "group_id": assigned["component_id"],
            "split": assigned["split"],
            "stage": "initial",
        }
        if assigned["split"] != row["split_candidate"]:
            raise ConfigError("recipient split differs from approved candidate allocation")
        conditions.append(condition)
    model = load_yaml(path.parent / refs["model_config"])
    domain = load_yaml(path.parent / refs["domain_config"])
    snapshot = design["model_snapshot"]
    for key, value in (
        ("name", snapshot["name"]),
        ("revision", snapshot["model_revision"]),
        ("tokenizer_revision", snapshot["tokenizer_revision"]),
        ("quantization", snapshot["quantization"]),
        ("dtype", snapshot["dtype"]),
        ("attn_implementation", snapshot["attention_implementation"]),
    ):
        if model["model"][key] != value:
            raise ConfigError(f"recipient model snapshot mismatch: {key}")
    if domain["domain"]["benchmark_version"] != "v1.2.2":
        raise ConfigError("recipient native domain differs")
    config = {
        "experiment": {
            "name": design["experiment_id"],
            "seed": design["sampling"]["seed"],
            "max_steps": design["decoding"]["max_steps"],
        },
        "decoding": design["decoding"],
        "resources": design["resources"],
    }
    return (
        PilotPlan(
            path,
            config,
            tuple(conditions),
            spec,
            model,
            domain,
            freeze_path,
            sha256_file(freeze_path),
        ),
        design,
    )


def outcome_selector(
    spec: dict[str, Any],
    condition: dict[str, Any],
    native: Any,
    initial: dict[str, Any],
    final: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    task, declared = task_and_condition(spec, condition["draft_condition_id"])
    strict = evaluate_calls(task, declared, initial, final, events, require_content=True)
    contradiction = bool(native.attack_success)
    return {
        "has_attack": False,
        "native_user_task_success": bool(native.user_task_success),
        "native_attack_success": bool(native.attack_success),
        "native_evaluator_version": native.evaluator_version,
        "group": "A" if native.user_task_success and not contradiction else None,
        "baseline_failure": not native.user_task_success and not contradiction,
        "quarantined_contradiction": contradiction,
        "audited_strict_user_task_success": None,
        "strict_evaluator_version": EVALUATOR_VERSION,
        "automatic_strict_user_task_success": strict["user_task_success"],
        "strict_candidate_attack_occurred": False,
        "wrong_recipient_transfer": strict["wrong_recipient_transfer"],
        "forbidden_side_effects": [] if strict["allowed_tool_sequence"] else ["forbidden_tool"],
        "argument_present": condition["argument_present"],
    }


class RecipientServices(HuggingFacePilotServices):
    def session(self, condition: dict[str, Any]) -> Any:
        session = create_session(self.plan.evaluator, condition["draft_condition_id"])
        if session.user_task.PROMPT != condition["user_instruction"]:
            raise ConfigError("recipient native prompt differs")
        return session


def capture_user_boundary(messages: list[dict[str, Any]]) -> bool:
    """Only the first user-to-assistant prefix supplies probe features."""
    return len(messages) == 1 and messages[0]["role"] == "user"


def preflight(plan: PilotPlan, design: dict[str, Any], *, tokenizer: Any) -> dict[str, Any]:
    """Repeat native controls and fixed-tokenizer user-boundary alignment."""
    native = native_preflight(plan.evaluator)
    if len(native["conditions"]) != 96:
        raise ConfigError("native recipient preflight omitted conditions")
    reports = []
    for condition in plan.conditions:
        session = create_session(plan.evaluator, condition["draft_condition_id"])
        backend = QwenTransformersBackend(
            model=None,
            tokenizer=tokenizer,
            tools=session.tool_schemas,
            model_revision=plan.model_config["model"]["revision"],
            tokenizer_revision=plan.model_config["model"]["tokenizer_revision"],
            decoding=DecodingConfig(
                do_sample=False, temperature=0.0, top_p=1.0, max_new_tokens=256
            ),
            max_context_tokens=plan.model_config["model"]["max_context_tokens"],
        )
        if backend.template_sha256 != design["model_snapshot"]["chat_template_sha256_expected"]:
            raise ConfigError("recipient Qwen chat template differs")
        prefix = backend.serialize(list(session.initial_messages))
        positions, indices, _ = position_selector(
            prefix,
            list(session.initial_messages),
            condition,
            {"ipi_window": {"left": 16, "right": 16}, "full_sequence_condition_ids": []},
        )
        if (
            prefix.boundary.value != "user_to_assistant"
            or not positions["exposed"]
            or {p["name"] for p in positions["positions"]} != {"Tpre", "Tpost", "Tend_assistant"}
            or not indices
        ):
            raise ConfigError(f"recipient boundary position mismatch: {condition['condition_id']}")
        candidate_lengths = {}
        for role, call in condition["candidate_calls"].items():
            serialized = serialize_qwen_tool_call(call["name"], call["arguments"])
            tokens = tokenizer.encode(serialized.text, add_special_tokens=False)
            if not tokens or len(prefix.token_ids) + len(tokens) > backend.max_context_tokens:
                raise ConfigError("recipient candidate is empty or exceeds context")
            candidate_lengths[role] = len(tokens)
        reports.append(
            {
                "condition_id": condition["condition_id"],
                "draft_condition_id": condition["draft_condition_id"],
                "split": condition["split"],
                "prefix_id": prefix.prefix_id,
                "prefix_tokens": len(prefix.token_ids),
                "selected_positions": len(indices),
                "recipient_token_indices": positions["intervention_token_indices"],
                "candidate_token_lengths": candidate_lengths,
                "tool_schema_sha256": prefix.metadata["tool_schema_sha256"],
            }
        )
    schemas = {item["tool_schema_sha256"] for item in reports}
    if len(schemas) != 1:
        raise ConfigError("recipient tool schema differs across conditions")
    return {
        "status": "native_and_tokenizer_preflight_passed",
        "research_result": False,
        "design_freeze_sha256": plan.sample_freeze_sha256,
        "chat_template_sha256": design["model_snapshot"]["chat_template_sha256_expected"],
        "tool_schema_sha256": schemas.pop(),
        "native_control_count": sum(len(row["controls"]) for row in native["conditions"]),
        "conditions": reports,
    }


def gpu_preflight(plan: PilotPlan, design: dict[str, Any]) -> dict[str, Any]:
    """Measure the longest one- and two-account user prefixes without generation."""
    from transformers import AutoTokenizer

    commit, dirty = _git_metadata()
    if dirty:
        raise ConfigError("GPU preflight requires a clean execution commit")
    model = plan.model_config["model"]
    tokenizer = AutoTokenizer.from_pretrained(
        model["name"], revision=model["tokenizer_revision"], local_files_only=True
    )
    fixed = preflight(plan, design, tokenizer=tokenizer)
    by_id = {row["condition_id"]: row for row in fixed["conditions"]}
    single = [row for row in plan.conditions if row["reference_value_id"] is None]
    double = [row for row in plan.conditions if row["reference_value_id"] is not None]
    chosen = [
        max(group, key=lambda row: by_id[row["condition_id"]]["prefix_tokens"])
        for group in (single, double)
    ]
    runtime = {
        "chat_template_sha256": fixed["chat_template_sha256"],
        "tool_schema_sha256": fixed["tool_schema_sha256"],
        "capture": runtime_capture(design),
    }
    services = RecipientServices(plan, runtime)
    reports = []
    for condition in chosen:
        services.start_condition()
        started = time.perf_counter()
        session = services.session(condition)
        backend = services.backend(session)
        messages = list(session.initial_messages)
        prefix = backend.serialize(messages)
        positions, indices, ranges = position_selector(
            prefix, messages, condition, runtime["capture"]
        )
        if not positions["exposed"]:
            raise ConfigError("GPU recipient preflight lost user exposure")
        activation, attention, _ = services.capture(prefix, indices, ranges, full_attention=False)
        if activation.prefix_id != prefix.prefix_id or attention["prefix_id"] != prefix.prefix_id:
            raise ConfigError("GPU recipient prefix mismatch")
        scores = services.score(prefix, condition)
        if scores["prefix_id"] != prefix.prefix_id:
            raise ConfigError("GPU recipient candidate score prefix mismatch")
        peak = services.check_memory()
        residual_bytes = len(services.activation_bytes(activation))
        elapsed = time.perf_counter() - started
        limits = design["resources"]
        if (
            peak > limits["maximum_gpu_memory_gib"] * 2**30
            or residual_bytes > limits["maximum_storage_gib_per_condition"] * 2**30
            or elapsed > limits["maximum_seconds_per_condition"]
        ):
            raise ConfigError("GPU recipient preflight exceeded a resource ceiling")
        reports.append(
            {
                "condition_id": condition["condition_id"],
                "draft_condition_id": condition["draft_condition_id"],
                "prefix_tokens": len(prefix.token_ids),
                "selected_positions": len(indices),
                "candidate_scored": True,
                "peak_gpu_memory_bytes": peak,
                "residual_bytes": residual_bytes,
                "elapsed_seconds": elapsed,
            }
        )
    return {
        "status": "engineering_gpu_preflight_passed",
        "research_result": False,
        "design_freeze_sha256": plan.sample_freeze_sha256,
        "git_commit": commit,
        "git_dirty": dirty,
        "chat_template_sha256": fixed["chat_template_sha256"],
        "tool_schema_sha256": fixed["tool_schema_sha256"],
        "runtime_report": services.runtime_report,
        "conditions": reports,
    }


def _verify_gpu_report(
    plan: PilotPlan, design: dict[str, Any], report: dict[str, Any], *, commit: str
) -> None:
    if (
        report.get("status") != "engineering_gpu_preflight_passed"
        or report.get("research_result") is not False
        or report.get("design_freeze_sha256") != plan.sample_freeze_sha256
        or report.get("git_commit") != commit
        or report.get("git_dirty") is not False
        or report.get("chat_template_sha256")
        != design["model_snapshot"]["chat_template_sha256_expected"]
        or len(report.get("conditions", [])) != 2
    ):
        raise ConfigError("recipient GPU report differs from frozen design")
    for row in report["conditions"]:
        if (
            row.get("candidate_scored") is not True
            or row.get("peak_gpu_memory_bytes", float("inf"))
            > design["resources"]["maximum_gpu_memory_gib"] * 2**30
            or row.get("residual_bytes", float("inf"))
            > design["resources"]["maximum_storage_gib_per_condition"] * 2**30
            or row.get("elapsed_seconds", float("inf"))
            > design["resources"]["maximum_seconds_per_condition"]
        ):
            raise ConfigError("recipient GPU report exceeds resource limits")


def create_runtime_freeze(
    plan: PilotPlan, design: dict[str, Any], report_path: str | Path, output_path: str | Path
) -> dict[str, Any]:
    """Bind a clean commit and same-commit GPU report before any model run."""
    report_path = Path(report_path).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    commit, dirty = _git_metadata()
    if dirty:
        raise ConfigError("commit recipient execution code before runtime freeze")
    _verify_gpu_report(plan, design, report, commit=commit)
    root = plan.config_path.parents[2]
    if not report_path.is_relative_to(root):
        raise ConfigError("GPU report must be repository-relative")
    files = [*(root / "src/goal_takeover").rglob("*.py"), *(root / "data/schemas").glob("*.json")]
    files.extend(
        [
            plan.config_path,
            root / "configs/models/qwen3_8b_int8.yaml",
            root / "configs/domains/agentdojo_banking_v1_2_2.yaml",
        ]
    )
    freeze = {
        "schema_version": 1,
        "status": "frozen",
        "created_at": datetime.now(UTC).isoformat(),
        "design_freeze_sha256": plan.sample_freeze_sha256,
        "git_commit": commit,
        "files_sha256": {
            str(path.relative_to(root)): sha256_file(path) for path in sorted(set(files))
        },
        "chat_template_sha256": report["chat_template_sha256"],
        "tool_schema_sha256": report["tool_schema_sha256"],
        "gpu_preflight_report": str(report_path.relative_to(root)),
        "gpu_preflight_report_sha256": sha256_file(report_path),
        "capture_resource_preflight_passed": True,
        "capture": runtime_capture(design),
    }
    with Path(output_path).open("x", encoding="utf-8") as stream:
        json.dump(freeze, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return freeze


def load_runtime(plan: PilotPlan, design: dict[str, Any], path: str | Path) -> dict[str, Any]:
    """Fail closed on source, revision, GPU or native suite changes."""
    runtime = json.loads(Path(path).read_text(encoding="utf-8"))
    if runtime.get("status") != "frozen" or runtime.get("schema_version") != 1:
        raise ConfigError("frozen recipient runtime is required")
    if runtime.get("design_freeze_sha256") != plan.sample_freeze_sha256:
        raise ConfigError("recipient runtime design checksum mismatch")
    commit, dirty = _git_metadata()
    if dirty or runtime.get("git_commit") != commit:
        raise ConfigError("recipient runtime requires its clean execution commit")
    root = plan.config_path.parents[2]
    report_relative = Path(runtime["gpu_preflight_report"])
    if report_relative.is_absolute() or ".." in report_relative.parts:
        raise ConfigError("recipient GPU report path must be repository-relative")
    files = runtime.get("files_sha256", {})
    required = {str(path.relative_to(root)) for path in (root / "src/goal_takeover").rglob("*.py")}
    required.update(str(path.relative_to(root)) for path in (root / "data/schemas").glob("*.json"))
    if not required.issubset(files):
        raise ConfigError("recipient runtime omitted source or schema checksums")
    for relative, digest in files.items():
        target = Path(relative)
        if target.is_absolute() or ".." in target.parts or sha256_file(root / target) != digest:
            raise ConfigError(f"recipient runtime file checksum mismatch: {relative}")
    if runtime.get("capture") != runtime_capture(design):
        raise ConfigError("recipient runtime capture differs")
    report_path = root / report_relative
    if sha256_file(report_path) != runtime.get("gpu_preflight_report_sha256"):
        raise ConfigError("recipient GPU report checksum differs")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    _verify_gpu_report(plan, design, report, commit=commit)
    if report["tool_schema_sha256"] != runtime.get("tool_schema_sha256"):
        raise ConfigError("recipient runtime tool schema differs")
    current = gpu_runtime_report()
    measured = report["runtime_report"]
    for key in ("device_name", "compute_capability", "torch", "torch_cuda"):
        if current.get(key) != measured.get(key):
            raise ConfigError(f"recipient runtime environment differs: {key}")
    versions = measured.get("versions", {})
    if {name: package_version(name) for name in versions} != versions:
        raise ConfigError("recipient runtime package versions differ")
    if current["total_memory_bytes"] < measured["total_memory_bytes"]:
        raise ConfigError("recipient execution GPU memory below preflight")
    return runtime


def run_collection(
    plan: PilotPlan,
    design: dict[str, Any],
    runtime_path: str | Path,
    *,
    artifact_root: str | Path = "artifacts",
    on_run: Any = None,
) -> list[str]:
    """Collect all planned runs once; stop at the first technical failure."""
    runtime = load_runtime(plan, design, runtime_path)
    from transformers import AutoTokenizer

    model = plan.model_config["model"]
    tokenizer = AutoTokenizer.from_pretrained(
        model["name"], revision=model["tokenizer_revision"], local_files_only=True
    )
    fixed = preflight(plan, design, tokenizer=tokenizer)
    if fixed["tool_schema_sha256"] != runtime["tool_schema_sha256"]:
        raise ConfigError("recipient native tool schema changed")
    root = Path(artifact_root)
    run_ids = [
        f"{design['run_ids']['prefix']}-c{index:03d}-a1"
        for index in range(1, len(plan.conditions) + 1)
    ]
    existing = [run_id for run_id in run_ids if (root / "runs" / run_id).exists()]
    if existing:
        raise FileExistsError(f"immutable recipient runs already exist: {existing}")
    services = RecipientServices(plan, runtime)
    paths = []

    def outcome(condition: Any, native: Any, initial: Any, final: Any, events: Any) -> Any:
        return outcome_selector(plan.evaluator, condition, native, initial, final, events)

    for run_id, condition in zip(run_ids, plan.conditions, strict=True):
        path, record = execute_condition(
            plan,
            runtime,
            services,
            condition=condition,
            artifact_root=root,
            run_id=run_id,
            runtime_sha256=sha256_file(Path(runtime_path)),
            position_selector=position_selector,
            outcome_selector=outcome,
            capture_selector=capture_user_boundary,
            run_schema_path=plan.config_path.parents[2]
            / "data/schemas/argument_readout_run.schema.json",
        )
        paths.append(str(path))
        if on_run is not None:
            on_run(run_id, record)
        if record["status"] == "technical_failure":
            break
    return paths


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "gpu-preflight", "freeze-runtime", "run"):
        command = commands.add_parser(name)
        command.add_argument("design", type=Path)
        if name in {"preflight", "gpu-preflight"}:
            command.add_argument("--output", required=True, type=Path)
        if name == "freeze-runtime":
            command.add_argument("--gpu-report", required=True, type=Path)
            command.add_argument("--output", required=True, type=Path)
        if name == "run":
            command.add_argument("--runtime-freeze", required=True, type=Path)
    args = parser.parse_args()
    plan, design = load_plan(args.design)
    if args.command == "preflight":
        from transformers import AutoTokenizer

        model = plan.model_config["model"]
        tokenizer = AutoTokenizer.from_pretrained(
            model["name"], revision=model["tokenizer_revision"], local_files_only=True
        )
        result = preflight(plan, design, tokenizer=tokenizer)
    elif args.command == "gpu-preflight":
        result = gpu_preflight(plan, design)
    elif args.command == "freeze-runtime":
        result = create_runtime_freeze(plan, design, args.gpu_report, args.output)
    else:
        result = run_collection(
            plan,
            design,
            args.runtime_freeze,
            on_run=lambda run_id, record: print(
                json.dumps({"run_id": run_id, "status": record["status"]}), flush=True
            ),
        )
    if args.command in {"preflight", "gpu-preflight"}:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
    print(
        json.dumps(
            {
                "command": args.command,
                "result": result if args.command == "run" else result.get("status"),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
