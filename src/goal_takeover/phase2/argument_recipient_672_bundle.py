"""Immutable canonical teacher-capture bundle for the 672 collection."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from goal_takeover.instrumentation.capture import ActivationRecord
from goal_takeover.phase2.argument_recipient_672_capture import POSITION_RULE_VERSION
from goal_takeover.serialization.prefix import SerializedPrefix
from goal_takeover.storage.run_writer import ImmutableRunWriter


def write_canonical_capture_bundle(
    *,
    artifact_root: Path,
    run_id: str,
    condition: dict[str, Any],
    split: str,
    component_id: str,
    messages: tuple[dict[str, Any], ...],
    prefix: SerializedPrefix,
    position: dict[str, Any],
    activation: ActivationRecord,
    resolved_config: dict[str, Any],
    provenance: dict[str, Any],
) -> Path:
    """Publish one complete capture or leave no visible run directory.

    The caller verifies a design/runtime freeze before loading the model. This
    writer also requires those references and a clean Git commit in each run.
    """
    import torch
    from safetensors.torch import save

    if split not in {"train", "validation"} or split != condition["split_candidate"]:
        raise ValueError("canonical capture split differs from condition")
    if not component_id or not condition.get("condition_id"):
        raise ValueError("canonical capture group or condition ID missing")
    if not messages or messages[0] != {"role": "user", "content": condition["user_instruction"]}:
        raise ValueError("canonical history user instruction differs from condition")
    required = (
        "git_commit",
        "design_freeze_sha256",
        "runtime_freeze_sha256",
        "model_revision",
        "tokenizer_revision",
    )
    if provenance.get("git_dirty") is not False or not all(provenance.get(key) for key in required):
        raise ValueError("canonical capture requires clean frozen provenance")
    model_config = resolved_config.get("model", {})
    decoding = resolved_config.get("decoding", {})
    if (
        model_config.get("revision") != provenance["model_revision"]
        or model_config.get("tokenizer_revision") != provenance["tokenizer_revision"]
        or not isinstance(resolved_config.get("seed"), int)
        or decoding.get("do_sample") is not False
        or decoding.get("temperature") != 0.0
        or decoding.get("top_p") != 1.0
    ):
        raise ValueError("canonical capture model or deterministic decoding differs")
    if (
        position.get("prefix_id") != prefix.prefix_id
        or position.get("position_rule_version") != POSITION_RULE_VERSION
        or position.get("boundary") != prefix.boundary.value
        or position.get("name") != "Tend_assistant"
        or position.get("source_role") != condition["exposure"]["source_role"]
        or position.get("token_index") != len(prefix.token_ids) - 1
        or position.get("token_id") != prefix.token_ids[-1]
    ):
        raise ValueError("canonical capture position does not match final prompt token")
    activation.assert_matches(prefix)
    if activation.positions != (position["token_index"],):
        raise ValueError("canonical activation position differs")
    if not activation.values:
        raise ValueError("canonical capture has no residual layers")
    tensors = {}
    layers = {}
    for name, tensor in activation.values.items():
        if (
            not isinstance(tensor, torch.Tensor)
            or tensor.ndim != 3
            or tuple(tensor.shape[:2]) != (1, 1)
        ):
            raise ValueError(f"canonical residual shape differs: {name}")
        if not torch.isfinite(tensor).all():
            raise ValueError(f"canonical residual has nonfinite values: {name}")
        value = tensor.detach().cpu().contiguous()
        tensors[name] = value
        layers[name] = {"shape": list(value.shape), "dtype": str(value.dtype)}
    prefix_record = {
        "prefix_id": prefix.prefix_id,
        "boundary": prefix.boundary.value,
        "text": prefix.text,
        "text_sha256": hashlib.sha256(prefix.text.encode("utf-8")).hexdigest(),
        "token_ids": list(prefix.token_ids),
        "offsets": [asdict(offset) for offset in prefix.offsets],
        "metadata": prefix.metadata,
    }
    run = {
        "schema_version": 1,
        "status": "completed",
        "capture_role": "canonical_probe_teacher",
        "run_id": run_id,
        "condition_id": condition["condition_id"],
        "split": split,
        "group_id": component_id,
        "pair_id": condition["pair_id"],
        "seed": resolved_config["seed"],
        "decoding": resolved_config["decoding"],
        "git_commit": provenance["git_commit"],
        "git_dirty": False,
        "design_freeze_sha256": provenance["design_freeze_sha256"],
        "runtime_freeze_sha256": provenance["runtime_freeze_sha256"],
        "model": {
            "name": resolved_config["model"]["name"],
            "revision": provenance["model_revision"],
        },
        "tokenizer": {
            "name": resolved_config["model"]["name"],
            "revision": provenance["tokenizer_revision"],
        },
        "outcome_flags": {
            "behavior_executed": False,
            "user_task_success": None,
            "attack_success": None,
        },
        "selected_position": position,
        "activation_layers": layers,
    }
    with ImmutableRunWriter(artifact_root, run_id) as writer:
        writer.write_json("run.json", run, kind="canonical_capture_metadata")
        writer.write_json("condition.json", condition, kind="condition_declaration")
        writer.write_json("history.json", list(messages), kind="canonical_messages")
        writer.write_json("prefix.json", prefix_record, kind="serialized_prefix")
        writer.write_json("resolved_config.json", resolved_config, kind="resolved_configuration")
        writer.write_bytes("residual.safetensors", save(tensors), kind="residual_capture")
        return writer.commit()
