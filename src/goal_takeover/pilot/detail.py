"""Derived, immutable full-sequence residual captures from declared pilot diagnostics."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from goal_takeover.config import ConfigError, load_yaml
from goal_takeover.pilot.plan import load_pilot_plan
from goal_takeover.pilot.report import condition_run_id, load_records, read_bundle
from goal_takeover.pilot.runner import condition_deadline
from goal_takeover.schemas import AgentBoundary
from goal_takeover.serialization.prefix import SerializedPrefix, build_serialized_prefix
from goal_takeover.shakedown import _git_metadata, _save_activations
from goal_takeover.storage.run_writer import ImmutableRunWriter, sha256_file

EXPECTED_CONDITIONS = (
    "banking_pilot_v1_4fb7f8324a191b52",
    "banking_pilot_v1_4bcd2e89355ab958",
    "banking_pilot_v1_0ec8e0587c4a88e7",
    "banking_pilot_v1_196e79c78200e3c1",
)


def load_detail_plan(path: str | Path) -> tuple[dict[str, Any], Any]:
    path = Path(path).resolve()
    config = load_yaml(path)
    experiment = config.get("experiment", {})
    if (
        config.get("schema_version") != 2
        or config.get("status") != "preregistered_execution_pending"
        or experiment.get("source_scope") != "fixed_prefix_diagnostic"
        or experiment.get("source_boundary") != "first_tool_to_assistant"
        or experiment.get("capture") != "all_layers_full_sequence_block_output_bfloat16"
        or tuple(experiment.get("selected_condition_ids", ())) != EXPECTED_CONDITIONS
        or experiment.get("missing_source_policy") != "record_missing_no_replacement"
        or experiment.get("maximum_seconds_per_capture") != 300
        or experiment.get("maximum_gpu_memory_gib") != 12
        or experiment.get("maximum_storage_gib_per_capture") != 1.5
        or experiment.get("maximum_total_storage_gib") != 6.0
    ):
        raise ConfigError("detail plan conflicts with RDR-2026-10-02-01")
    refs = config.get("references", {})
    if (
        refs.get("pilot_sample") != "banking_pilot_v1.yaml"
        or refs.get("pilot_sample_freeze") != "banking_pilot_v1.freeze.json"
    ):
        raise ConfigError("detail plan must reference the frozen pilot sample")
    pilot = load_pilot_plan(path.parent / refs["pilot_sample"])
    if not {row["condition_id"] for row in pilot.conditions}.issuperset(EXPECTED_CONDITIONS):
        raise ConfigError("detail condition is absent from the frozen sample")
    return config, pilot


def source_prefix(
    bundle: Path, record: dict[str, Any], condition_id: str
) -> SerializedPrefix | None:
    """Return the one declared diagnostic prefix, or None for a genuinely absent source."""
    if record["condition_id"] != condition_id:
        raise ConfigError("detail source condition mismatch")
    prefixes = json.loads((bundle / "prefixes.json").read_text())
    selected = [row for row in prefixes if row.get("scope") == "fixed_prefix_diagnostic"]
    if not selected:
        return None
    if len(selected) != 1 or record.get("diagnostic") is None:
        raise ConfigError("detail source must have exactly one diagnostic")
    row = selected[0]
    index = record["diagnostic"]["measurement_index"]
    measured = [m for m in record["measurements"] if m["index"] == index]
    if (
        row.get("step_index") != index
        or row.get("boundary") != AgentBoundary.FIRST_TOOL_TO_ASSISTANT.value
        or len(measured) != 1
        or measured[0]["scope"] != "fixed_prefix_diagnostic"
        or measured[0]["prefix_id"] != row["prefix_id"]
        or measured[0]["scores"] is None
    ):
        raise ConfigError("detail diagnostic prefix/measurement mismatch")
    if row.get("serialized_text_sha256") != hashlib.sha256(row["text"].encode("utf-8")).hexdigest():
        raise ConfigError("detail source text checksum mismatch")
    offsets = row["offsets"]
    if [item["token_index"] for item in offsets] != list(range(len(offsets))) or [
        item["token_id"] for item in offsets
    ] != row["token_ids"]:
        raise ConfigError("detail source offset alignment mismatch")
    prefix = build_serialized_prefix(
        boundary=AgentBoundary.FIRST_TOOL_TO_ASSISTANT,
        text=row["text"],
        token_ids=row["token_ids"],
        offset_mapping=[(item["start"], item["end"]) for item in offsets],
        metadata=row["metadata"],
    )
    if (
        prefix.prefix_id != row["prefix_id"]
        or row["boundary_token_index"] != len(prefix.token_ids) - 1
        or row["boundary_token_id"] != prefix.token_ids[-1]
    ):
        raise ConfigError("detail source prefix identity mismatch")
    resolved = json.loads((bundle / "resolved_config.json").read_text())
    model = resolved["model_config"]["model"]
    if (
        record["model"]["name"] != model["name"]
        or record["tokenizer"]["name"] != model["name"]
        or record["model"]["revision"] != model["revision"]
        or record["tokenizer"]["revision"] != model["tokenizer_revision"]
        or prefix.metadata["tokenizer_revision"] != model["tokenizer_revision"]
        or prefix.metadata["chat_template_sha256"]
        != resolved["runtime_freeze"]["chat_template_sha256"]
        or prefix.metadata["tool_schema_sha256"] != resolved["runtime_freeze"]["tool_schema_sha256"]
    ):
        raise ConfigError("detail source model/tokenizer/serialization mismatch")
    return prefix


def run_detail(
    config_path: str | Path,
    *,
    run_prefix: str,
    detail_prefix: str | None = None,
    artifact_root: str | Path = "artifacts",
) -> tuple[Path, ...]:
    """Capture each declared source once; missing sources remain explicit immutable records."""
    config, plan = load_detail_plan(config_path)
    commit, dirty = _git_metadata()
    if not commit or dirty:
        raise ConfigError("detail capture requires a clean committed implementation")
    detail_root = Path(artifact_root) / "processed" / "pilot_detail_v1"
    detail_prefix = detail_prefix or run_prefix
    ImmutableRunWriter(detail_root, f"{detail_prefix}-detail-check")
    source_root = Path(artifact_root) / "runs"
    records = {row["condition_id"]: row for row in load_records(plan, artifact_root, run_prefix)}
    if not any(condition_id in records for condition_id in EXPECTED_CONDITIONS):
        raise ConfigError("no declared pilot detail source exists; run the lead stage first")
    selected = {row["condition_id"]: row for row in plan.conditions}
    experiment = config["experiment"]
    total_bytes = 0
    outputs = []
    for condition_id in EXPECTED_CONDITIONS:
        condition = selected[condition_id]
        record = records.get(condition_id)
        source = source_root / (
            record["run_id"] if record is not None else condition_run_id(run_prefix, condition)
        )
        output_id = f"{detail_prefix}-detail-{condition_id}"
        if (detail_root / "runs" / output_id).exists():
            raise FileExistsError("immutable detail capture already exists")
        record = read_bundle(source) if record is not None else None
        if record is not None and record["sample_freeze_sha256"] != plan.sample_freeze_sha256:
            raise ConfigError("detail source sample freeze mismatch")
        prefix = source_prefix(source, record, condition_id) if record is not None else None
        if prefix is None:
            with ImmutableRunWriter(detail_root, output_id) as writer:
                writer.write_json(
                    "detail.json",
                    {
                        "status": "missing_source",
                        "condition_id": condition_id,
                        "source_run_id": source.name,
                        "source_exists": record is not None,
                        "detail_config_sha256": sha256_file(Path(config_path)),
                        "sample_freeze_sha256": plan.sample_freeze_sha256,
                        "git_commit": commit,
                    },
                    kind="missing_source_record",
                )
                outputs.append(writer.commit())
            continue
        import torch

        from goal_takeover.instrumentation.huggingface import HuggingFaceActivationExtractor
        from goal_takeover.runtime import assert_model_has_no_cpu_offload
        from goal_takeover.selection import _load_model

        started = time.perf_counter()
        with condition_deadline(experiment["maximum_seconds_per_capture"]):
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            model, tokenizer = _load_model(plan.model_config["model"])
            assert_model_has_no_cpu_offload(model)
            if (
                tuple(tokenizer(prefix.text, add_special_tokens=False)["input_ids"])
                != prefix.token_ids
            ):
                raise ConfigError("loaded tokenizer does not reproduce source prefix tokens")
            extractor = HuggingFaceActivationExtractor(
                model, block_path=plan.model_config["instrumentation"]["transformer_block_path"]
            )
            capture = extractor.capture(prefix, positions=range(len(prefix.token_ids)))
            capture.assert_matches(prefix)
            if capture.positions != tuple(range(len(prefix.token_ids))):
                raise ConfigError("detail capture omitted sequence positions")
            if set(capture.values) != set(extractor.module_names):
                raise ConfigError("detail capture omitted a transformer layer")
            if any(
                tensor.ndim != 3
                or tensor.shape[0] != 1
                or tensor.shape[1] != len(prefix.token_ids)
                or tensor.dtype != torch.bfloat16
                or not bool(tensor.isfinite().all())
                for tensor in capture.values.values()
            ):
                raise ConfigError("detail residual shape, dtype or finite-value check failed")
            peak = max(torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved())
            if peak > experiment["maximum_gpu_memory_gib"] * 2**30:
                raise RuntimeError("oom_or_resource_limit: detail GPU ceiling exceeded")
            data = _save_activations(capture.values)
            if len(data) > experiment["maximum_storage_gib_per_capture"] * 2**30:
                raise RuntimeError("oom_or_resource_limit: detail storage ceiling exceeded")
            if total_bytes + len(data) > experiment["maximum_total_storage_gib"] * 2**30:
                raise RuntimeError("oom_or_resource_limit: detail total storage ceiling exceeded")
            detail = {
                "status": "captured",
                "condition_id": condition_id,
                "source_scope": "fixed_prefix_diagnostic",
                "source_run_id": source.name,
                "source_manifest_sha256": sha256_file(source / "manifest.json"),
                "source_prefixes_sha256": sha256_file(source / "prefixes.json"),
                "source_runtime_freeze_sha256": record["runtime_freeze_sha256"],
                "detail_config_sha256": sha256_file(Path(config_path)),
                "sample_freeze_sha256": plan.sample_freeze_sha256,
                "git_commit": commit,
                "model": record["model"],
                "tokenizer": record["tokenizer"],
                "prefix_id": prefix.prefix_id,
                "token_ids": list(prefix.token_ids),
                "positions": list(capture.positions),
                "layers": {
                    name: {"shape": list(value.shape), "dtype": str(value.dtype)}
                    for name, value in capture.values.items()
                },
                "peak_gpu_memory_bytes": int(peak),
                "elapsed_seconds": time.perf_counter() - started,
            }
            if detail["elapsed_seconds"] > experiment["maximum_seconds_per_capture"]:
                raise RuntimeError("oom_or_resource_limit: detail time ceiling exceeded")
            with ImmutableRunWriter(detail_root, output_id) as writer:
                tensor_record = writer.write_bytes(
                    "residual.safetensors", data, kind="full_sequence_residual"
                )
                detail["residual_sha256"] = tensor_record["sha256"]
                writer.write_json("detail.json", detail, kind="detail_provenance")
                outputs.append(writer.commit())
            total_bytes += sum(
                entry.stat().st_size for entry in outputs[-1].iterdir() if entry.is_file()
            )
        del model, tokenizer, capture, data
        torch.cuda.empty_cache()
    return tuple(outputs)
