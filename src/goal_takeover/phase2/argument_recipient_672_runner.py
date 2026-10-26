"""Frozen canonical capture execution for the reviewed 672-condition design."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from goal_takeover.agent.runner import run_agent
from goal_takeover.config import load_yaml
from goal_takeover.datasets.argument_recipient_672_collection import build_frozen_materialization
from goal_takeover.datasets.argument_recipient_672_native import (
    create_session,
    evaluate_condition,
    task_and_condition,
)
from goal_takeover.instrumentation.huggingface import HuggingFaceActivationExtractor
from goal_takeover.phase2.argument_recipient_672_actual import select_actual_exposed_prefix
from goal_takeover.phase2.argument_recipient_672_bundle import write_canonical_capture_bundle
from goal_takeover.phase2.argument_recipient_672_capture import (
    build_canonical_history,
    select_canonical_position,
)
from goal_takeover.phase2.argument_recipient_672_smoke import _backend
from goal_takeover.pilot.evaluation import RecordingSession, state_document
from goal_takeover.selection import _load_model
from goal_takeover.shakedown import _git_metadata
from goal_takeover.storage.run_writer import ImmutableRunWriter, sha256_file


def _prefix_record(prefix: Any) -> dict[str, Any]:
    return {
        "prefix_id": prefix.prefix_id,
        "boundary": prefix.boundary.value,
        "text": prefix.text,
        "token_ids": list(prefix.token_ids),
        "offsets": [
            {
                "token_index": item.token_index,
                "token_id": item.token_id,
                "start": item.start,
                "end": item.end,
            }
            for item in prefix.offsets
        ],
        "metadata": prefix.metadata,
    }


def load_frozen_plan(config_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Fail before model loading if any reviewed declaration or freeze has drifted."""
    config = load_yaml(config_path)
    if config.get("status") != "design_frozen_runtime_pending":
        raise ValueError("672 execution config is not design frozen")
    root = config_path.resolve().parents[2]

    def resolve(key: str) -> Path:
        relative = Path(config["references"][key])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe repository reference: {key}")
        return root / relative

    paths = {
        key: resolve(key)
        for key in (
            "draft",
            "declaration",
            "split",
            "graph",
            "checkpoints",
            "actual_sample",
            "audit_prompt",
            "audit_schema",
            "design_freeze",
            "runtime_freeze",
        )
    }
    freeze = json.loads(paths["design_freeze"].read_text(encoding="utf-8"))
    runtime = json.loads(paths["runtime_freeze"].read_text(encoding="utf-8"))
    if freeze.get("status") != "design_frozen_runtime_pending" or runtime.get("status") != "frozen":
        raise ValueError("design or runtime freeze status differs")
    expected_files = {str(config_path.resolve().relative_to(root))} | {
        str(paths[key].relative_to(root))
        for key in (
            "draft",
            "declaration",
            "split",
            "graph",
            "checkpoints",
            "actual_sample",
            "audit_prompt",
            "audit_schema",
        )
    }
    if not expected_files <= set(freeze.get("files_sha256", {})):
        raise ValueError("design freeze omitted a required file")
    for relative, digest in freeze["files_sha256"].items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or sha256_file(root / path) != digest:
            raise ValueError(f"design checksum differs: {relative}")
    commit, dirty = _git_metadata()
    if dirty or runtime.get("git_commit") != commit:
        raise ValueError("runtime freeze requires the clean matching Git commit")
    if runtime.get("design_freeze_sha256") != sha256_file(paths["design_freeze"]):
        raise ValueError("runtime freeze design checksum differs")
    draft = json.loads(paths["draft"].read_text(encoding="utf-8"))
    declaration = json.loads(paths["declaration"].read_text(encoding="utf-8"))
    split = json.loads(paths["split"].read_text(encoding="utf-8"))
    graph = json.loads(paths["graph"].read_text(encoding="utf-8"))
    checkpoint = json.loads(paths["checkpoints"].read_text(encoding="utf-8"))
    actual_sample = json.loads(paths["actual_sample"].read_text(encoding="utf-8"))
    expected = build_frozen_materialization(draft)
    if (declaration, split, graph, checkpoint, actual_sample) != expected:
        raise ValueError("frozen 672 declarations differ from reviewed materialization")
    fit = config["fit"]
    selected = checkpoint["hyperparameter_selection"]
    if (
        fit["primary_metric"] != checkpoint["primary_metric"]
        or fit["development_threshold"] != checkpoint["primary_metric_threshold"]
        or fit["layer_grid"] != selected["layer_grid"]
        or fit["regularization_c_grid"] != selected["regularization_c_grid"]
        or fit["max_iter"] != selected["max_iter"]
        or config["seed"] != selected["seed"]
        or fit["training_source"] != checkpoint["primary_training_source"]
        or fit["validation_use"] != checkpoint["validation_use"]
    ):
        raise ValueError("fit configuration differs from frozen checkpoint plan")
    return config, declaration, split


def capture_all(config_path: Path, *, run_id_prefix: str) -> None:
    """Capture every declared condition once, retaining a technical failure bundle."""
    import torch

    config, declaration, split = load_frozen_plan(config_path)
    root = config_path.resolve().parents[2]
    output_root = root / config["resources"]["artifact_root"]
    if output_root != root / "artifacts":
        raise ValueError("canonical raw bundles must use artifacts/runs")
    assignments = {row["condition_id"]: row for row in split["assignments"]}
    run_ids = {
        row["condition_id"]: f"{run_id_prefix}-c{index:03d}"
        for index, row in enumerate(declaration["condition_specs"], start=1)
    }
    if any((output_root / "runs" / run_id).exists() for run_id in run_ids.values()):
        raise FileExistsError("one or more immutable canonical run IDs already exist")
    model, tokenizer = _load_model(config["model"])
    extractor = HuggingFaceActivationExtractor(model, block_path="model.layers")
    commit, _ = _git_metadata()
    design_freeze_path = root / config["references"]["design_freeze"]
    runtime_freeze_path = root / config["references"]["runtime_freeze"]
    provenance = {
        "git_commit": commit,
        "git_dirty": False,
        "design_freeze_sha256": sha256_file(design_freeze_path),
        "runtime_freeze_sha256": sha256_file(runtime_freeze_path),
        "model_revision": config["model"]["revision"],
        "tokenizer_revision": config["model"]["tokenizer_revision"],
    }
    torch.manual_seed(config["seed"])
    torch.cuda.manual_seed_all(config["seed"])
    for row in declaration["condition_specs"]:
        condition_id = row["condition_id"]
        run_id = run_ids[condition_id]
        stage = "native_session"
        try:
            session = create_session(declaration, row["draft_condition_id"], validated=True)
            task, condition = task_and_condition(declaration, row["draft_condition_id"])
            backend = _backend(model, tokenizer, session, config)
            stage = "canonical_read_and_position"
            history = build_canonical_history(session, task, condition)
            prefix, position = select_canonical_position(backend, history, condition)
            stage = "residual_capture"
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            activation = extractor.capture(prefix, positions=(position["token_index"],))
            elapsed = time.perf_counter() - started
            peak = max(torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved())
            resource = config["resources"]
            tensor_bytes = sum(
                value.numel() * value.element_size() for value in activation.values.values()
            )
            if (
                peak > resource["maximum_gpu_memory_gib"] * 2**30
                or tensor_bytes > resource["maximum_storage_gib_per_condition"] * 2**30
                or elapsed > resource["maximum_seconds_per_condition"]
            ):
                raise RuntimeError("canonical capture exceeded frozen resource ceiling")
            stage = "immutable_write"
            write_canonical_capture_bundle(
                artifact_root=output_root,
                run_id=run_id,
                condition=row,
                split=assignments[condition_id]["split"],
                component_id=assignments[condition_id]["component_id"],
                messages=history.snapshots[-1],
                prefix=prefix,
                position=position,
                activation=activation,
                resolved_config=config,
                provenance=provenance,
            )
        except Exception as exc:
            if stage != "immutable_write" or not (output_root / "runs" / run_id).exists():
                with ImmutableRunWriter(output_root, run_id) as writer:
                    writer.write_json(
                        "run.json",
                        {
                            "schema_version": 1,
                            "status": "technical_failure",
                            "run_id": run_id,
                            "condition_id": condition_id,
                            "failure_stage": stage,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                            "provenance": provenance,
                        },
                        kind="technical_failure",
                    )
                    writer.write_json("condition.json", row, kind="condition_declaration")
                    writer.write_json("resolved_config.json", config, kind="resolved_configuration")
                    writer.commit()
            raise


def run_actual_sample(config_path: Path, *, run_id_prefix: str) -> None:
    """Execute the preselected 112 trajectories and capture observed exposure."""
    import torch
    from safetensors.torch import save

    config, declaration, split = load_frozen_plan(config_path)
    root = config_path.resolve().parents[2]
    output_root = root / config["resources"]["artifact_root"]
    if output_root != root / "artifacts":
        raise ValueError("actual raw bundles must use artifacts/runs")
    sample_path = root / config["references"]["actual_sample"]
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    selected_ids = [cid for item in sample["selections"] for cid in item["condition_ids"]]
    if len(selected_ids) != 112 or len(set(selected_ids)) != 112:
        raise ValueError("actual sample condition count differs")
    conditions = {row["condition_id"]: row for row in declaration["condition_specs"]}
    assignments = {row["condition_id"]: row for row in split["assignments"]}
    run_ids = {cid: f"{run_id_prefix}-a{index:03d}" for index, cid in enumerate(selected_ids, 1)}
    if any((output_root / "runs" / run_id).exists() for run_id in run_ids.values()):
        raise FileExistsError("one or more immutable actual run IDs already exist")
    model, tokenizer = _load_model(config["model"])
    extractor = HuggingFaceActivationExtractor(model, block_path="model.layers")
    commit, _ = _git_metadata()
    provenance = {
        "git_commit": commit,
        "git_dirty": False,
        "design_freeze_sha256": sha256_file(root / config["references"]["design_freeze"]),
        "runtime_freeze_sha256": sha256_file(root / config["references"]["runtime_freeze"]),
        "model_revision": config["model"]["revision"],
        "tokenizer_revision": config["model"]["tokenizer_revision"],
    }
    torch.manual_seed(config["seed"])
    torch.cuda.manual_seed_all(config["seed"])
    for cid in selected_ids:
        condition = conditions[cid]
        run_id = run_ids[cid]
        stage = "native_session"
        try:
            task, native_condition = task_and_condition(
                declaration, condition["draft_condition_id"]
            )
            session = create_session(declaration, condition["draft_condition_id"], validated=True)
            backend = _backend(model, tokenizer, session, config)
            recorder = RecordingSession(session)
            initial_state = state_document(session.environment)
            snapshots: list[tuple[dict[str, Any], ...]] = []
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            stage = "model_generation"
            actual = run_agent(
                backend,
                session.initial_messages,
                recorder.tools,
                max_steps=config["decoding"]["max_steps"],
                on_boundary=lambda _boundary, messages, selected=snapshots: selected.append(
                    tuple(messages)
                ),
            )
            final_state = state_document(session.environment)
            if len(snapshots) != len(backend.prefixes) or len(actual.actions) != len(
                backend.prefixes
            ):
                raise ValueError("actual boundary/generation alignment differs")
            strict = evaluate_condition(
                task,
                native_condition,
                initial_state,
                final_state,
                recorder.events,
                require_content=True,
            )
            native = session.evaluate(actual.final_answer)
            prefix, position, exposure_missing = select_actual_exposed_prefix(
                backend.prefixes, snapshots, condition
            )
            stage = "actual_exposure_capture"
            activation = (
                extractor.capture(prefix, positions=(position["token_index"],))
                if prefix is not None and position is not None
                else None
            )
            elapsed = time.perf_counter() - started
            peak = max(torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved())
            tensor_bytes = (
                sum(value.numel() * value.element_size() for value in activation.values.values())
                if activation is not None
                else 0
            )
            limits = config["resources"]
            exceeded = (
                peak > limits["maximum_gpu_memory_gib"] * 2**30
                or tensor_bytes > limits["maximum_storage_gib_per_condition"] * 2**30
                or elapsed > limits["maximum_seconds_per_condition"]
            )
            stage = "immutable_write"
            run = {
                "schema_version": 1,
                "status": "technical_failure" if exceeded else "completed",
                "capture_role": "actual_behavior_and_transfer",
                "run_id": run_id,
                "condition_id": cid,
                "split": assignments[cid]["split"],
                "group_id": assignments[cid]["component_id"],
                "pair_id": condition["pair_id"],
                "seed": config["seed"],
                "decoding": config["decoding"],
                "provenance": provenance,
                "model": config["model"],
                "stop_reason": actual.stop_reason,
                "final_answer": actual.final_answer,
                "outcome_flags": {
                    "has_attack": False,
                    "user_task_success_native": bool(native.user_task_success),
                    "user_task_success_strict": strict["user_task_success"],
                    "attack_success": False,
                    "baseline_failure": not native.user_task_success,
                },
                "strict_evaluation": strict,
                "native_evaluation": {
                    "user_task_success": bool(native.user_task_success),
                    "attack_success": bool(native.attack_success),
                    "evaluator_version": native.evaluator_version,
                },
                "selected_position": position,
                "exposure_missing_reason": exposure_missing,
                "elapsed_seconds": elapsed,
                "peak_gpu_memory_bytes": int(peak),
                "resource_ceiling_exceeded": exceeded,
            }
            generations = [
                {
                    "prefix_id": prefix_item.prefix_id,
                    "boundary": prefix_item.boundary.value,
                    "raw_text": action.raw_text,
                    "kind": action.kind,
                    "tool_calls": [
                        {
                            "name": call.name,
                            "arguments": dict(call.arguments),
                            "call_id": call.call_id,
                        }
                        for call in action.ordered_tool_calls()
                    ],
                }
                for prefix_item, action in zip(backend.prefixes, actual.actions, strict=True)
            ]
            run["generations"] = generations
            with ImmutableRunWriter(output_root, run_id) as writer:
                writer.write_json("run.json", run, kind="actual_run_metadata")
                writer.write_json("condition.json", condition, kind="condition_declaration")
                writer.write_json("resolved_config.json", config, kind="resolved_configuration")
                writer.write_json("messages.json", actual.messages, kind="actual_messages")
                writer.write_json("generations.json", generations, kind="raw_generations")
                writer.write_json(
                    "prefixes.json",
                    [_prefix_record(item) for item in backend.prefixes],
                    kind="serialized_prefixes",
                )
                writer.write_json("tool_events.json", recorder.events, kind="tool_events")
                writer.write_json("initial_state.json", initial_state, kind="initial_state")
                writer.write_json("final_state.json", final_state, kind="final_state")
                if activation is not None:
                    activation.assert_matches(prefix)
                    tensors = {
                        name: value.detach().cpu().contiguous()
                        for name, value in activation.values.items()
                    }
                    writer.write_bytes(
                        "residual.safetensors", save(tensors), kind="actual_residual_capture"
                    )
                writer.commit()
            if exceeded:
                raise RuntimeError("actual trajectory exceeded frozen resource ceiling")
        except Exception as exc:
            if not (output_root / "runs" / run_id).exists():
                with ImmutableRunWriter(output_root, run_id) as writer:
                    writer.write_json(
                        "run.json",
                        {
                            "schema_version": 1,
                            "status": "technical_failure",
                            "run_id": run_id,
                            "condition_id": cid,
                            "failure_stage": stage,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                            "provenance": provenance,
                        },
                        kind="technical_failure",
                    )
                    writer.write_json("condition.json", condition, kind="condition_declaration")
                    writer.write_json("resolved_config.json", config, kind="resolved_configuration")
                    writer.commit()
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("capture", "actual"))
    parser.add_argument("config", type=Path)
    parser.add_argument("--run-id-prefix", required=True)
    args = parser.parse_args()
    if args.mode == "capture":
        capture_all(args.config, run_id_prefix=args.run_id_prefix)
    else:
        run_actual_sample(args.config, run_id_prefix=args.run_id_prefix)


if __name__ == "__main__":
    main()
