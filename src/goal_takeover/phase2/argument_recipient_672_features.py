"""Verified mixed-source feature loading from canonical capture bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from goal_takeover.phase2.argument_probe import FeatureRow
from goal_takeover.phase2.argument_recipient_672_capture import POSITION_RULE_VERSION
from goal_takeover.storage.run_writer import sha256_file


def _verified_artifact(bundle: Path, manifest: dict[str, Any], name: str) -> Path:
    entries = [item for item in manifest["artifacts"] if item["relative_path"] == name]
    if len(entries) != 1:
        raise ValueError(f"{bundle.name}: missing or duplicate artifact {name}")
    path = bundle / name
    if (
        not path.is_file()
        or path.stat().st_size != entries[0]["bytes"]
        or sha256_file(path) != entries[0]["sha256"]
    ):
        raise ValueError(f"{bundle.name}: artifact checksum differs: {name}")
    return path


def _read_json(bundle: Path, manifest: dict[str, Any], name: str) -> Any:
    return json.loads(_verified_artifact(bundle, manifest, name).read_text(encoding="utf-8"))


def load_canonical_features(
    declaration: dict[str, Any],
    split: dict[str, Any],
    runs_root: Path,
    run_ids_by_condition: dict[str, str],
    *,
    layers: list[str],
    design_freeze_sha256: str,
    runtime_freeze_sha256: str,
) -> tuple[dict[str, list[FeatureRow]], dict[str, str]]:
    """Load exact Tend_assistant residuals; reject provenance or exposure drift."""
    import numpy as np
    from safetensors import safe_open

    if not layers or len(layers) != len(set(layers)):
        raise ValueError("feature layer list is empty or duplicated")
    declared = {row["condition_id"]: row for row in declaration["condition_specs"]}
    assignments = {row["condition_id"]: row for row in split["assignments"]}
    if set(run_ids_by_condition) - set(declared) or set(run_ids_by_condition) - set(assignments):
        raise ValueError("capture mapping contains undeclared condition")
    if len(set(run_ids_by_condition.values())) != len(run_ids_by_condition):
        raise ValueError("capture run IDs are not unique")
    extracted: dict[str, list[FeatureRow]] = {layer: [] for layer in layers}
    manifest_hashes = {}
    identities = set()
    hidden_sizes: dict[str, int] = {}
    for condition_id, run_id in run_ids_by_condition.items():
        if Path(run_id).name != run_id or run_id in {".", ".."}:
            raise ValueError("unsafe canonical run ID")
        condition = declared[condition_id]
        assigned = assignments[condition_id]
        bundle = runs_root / run_id
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["run_id"] != run_id:
            raise ValueError(f"{run_id}: manifest run ID differs")
        manifest_hashes[run_id] = sha256_file(manifest_path)
        run = _read_json(bundle, manifest, "run.json")
        raw_condition = _read_json(bundle, manifest, "condition.json")
        history = _read_json(bundle, manifest, "history.json")
        prefix = _read_json(bundle, manifest, "prefix.json")
        if (
            run["run_id"] != run_id
            or run["condition_id"] != condition_id
            or run["status"] != "completed"
            or run["capture_role"] != "canonical_probe_teacher"
            or run["split"] != assigned["split"]
            or run["group_id"] != assigned["component_id"]
            or run["git_dirty"] is not False
            or run["design_freeze_sha256"] != design_freeze_sha256
            or run["runtime_freeze_sha256"] != runtime_freeze_sha256
            or raw_condition != condition
            or not history
            or history[0] != {"role": "user", "content": condition["user_instruction"]}
        ):
            raise ValueError(f"{run_id}: canonical capture declaration or provenance differs")
        identity = (
            run["model"]["name"],
            run["model"]["revision"],
            run["tokenizer"]["name"],
            run["tokenizer"]["revision"],
        )
        if not all(identity):
            raise ValueError(f"{run_id}: model or tokenizer revision missing")
        identities.add(identity)
        position = run["selected_position"]
        token_ids = prefix["token_ids"]
        index = position["token_index"]
        if (
            position["position_rule_version"] != POSITION_RULE_VERSION
            or position["prefix_id"] != prefix["prefix_id"]
            or position["boundary"] != condition["exposure"]["boundary"]
            or position["boundary"] != prefix["boundary"]
            or position["name"] != "Tend_assistant"
            or index != len(token_ids) - 1
            or position["token_id"] != token_ids[index]
            or prefix["text_sha256"] != hashlib.sha256(prefix["text"].encode("utf-8")).hexdigest()
            or len(prefix["offsets"]) != len(token_ids)
            or prefix["offsets"][index]["token_id"] != position["token_id"]
        ):
            raise ValueError(f"{run_id}: canonical position or prefix differs")
        account = condition["expected_send_money"]["arguments"]["recipient"]
        if prefix["text"].count(account) != 1:
            raise ValueError(f"{run_id}: recipient account exposure differs")
        lexical = {
            candidate: int(value in prefix["text"])
            for candidate, value in declaration["account_value_ids"].items()
        }
        if any(
            label and not lexical[candidate]
            for candidate, label in condition["argument_present"].items()
        ):
            raise ValueError(f"{run_id}: positive argument was not exposed")
        tensor_path = _verified_artifact(bundle, manifest, "residual.safetensors")
        with safe_open(tensor_path, framework="pt", device="cpu") as handle:
            for layer in layers:
                if layer not in handle.keys() or layer not in run["activation_layers"]:
                    raise ValueError(f"{run_id}: residual layer missing: {layer}")
                tensor = handle.get_tensor(layer)
                expected = run["activation_layers"][layer]
                if list(tensor.shape) != expected["shape"] or tuple(tensor.shape[:2]) != (1, 1):
                    raise ValueError(f"{run_id}: residual layer shape differs: {layer}")
                if str(tensor.dtype) != expected["dtype"]:
                    raise ValueError(f"{run_id}: residual layer dtype differs: {layer}")
                vector = np.asarray(tensor[0, 0].float().numpy(), dtype=np.float64)
                if vector.ndim != 1 or not np.isfinite(vector).all():
                    raise ValueError(f"{run_id}: residual vector invalid: {layer}")
                if layer in hidden_sizes and hidden_sizes[layer] != len(vector):
                    raise ValueError(f"{run_id}: residual hidden size differs: {layer}")
                hidden_sizes[layer] = len(vector)
                extracted[layer].append(
                    FeatureRow(
                        condition_id=condition_id,
                        run_id=run_id,
                        split=assigned["split"],
                        component_id=assigned["component_id"],
                        task_template_id=condition["task_template_id"],
                        user_instruction=prefix["text"],
                        prefix_id=prefix["prefix_id"],
                        boundary=prefix["boundary"],
                        token_index=index,
                        token_id=position["token_id"],
                        layer=layer,
                        position_name="Tend_assistant",
                        labels=condition["argument_present"],
                        lexical_presence=lexical,
                        vector=vector,
                    )
                )
    if len(identities) > 1:
        raise ValueError("canonical features mix model or tokenizer revisions")
    return extracted, manifest_hashes
