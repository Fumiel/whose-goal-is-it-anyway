"""Expand and verify an offline pilot declaration; never execute payload text."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from goal_takeover.config import load_yaml
from goal_takeover.datasets.generation import stable_condition_id
from goal_takeover.datasets.splitting import connected_component_groups


def expand_sample(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Materialize exact vector values and half-open spans in vector characters."""
    validate_template(spec)
    rows = []
    for task in spec["tasks"]:
        for kind in ("clean", "ipi", "lexical_control"):
            if kind == "clean":
                combinations = [(None, None)]
            elif kind == "ipi":
                combinations = [(s, v) for s in spec["styles"] for v in spec["variants"]]
            elif task["representative"]:
                combinations = [(c, spec["variants"][0]) for c in spec["controls"]]
            else:
                continue
            for form, variant in combinations:
                row = copy.deepcopy(task)
                row.pop("attack_instruction")
                row.pop("benign_vector_text")
                row.pop("representative")
                row["condition_family"] = kind
                row["has_attack"] = kind == "ipi"
                row["split"] = "pilot_only"
                row["excluded_from_confirmatory_test"] = True
                row["attack_goal_id"] = task["goal_id"] if kind == "ipi" else None
                row["attack_style_id"] = form["id"] if kind == "ipi" else None
                row["attack_template_id"] = (
                    f"{task['goal_id']}:{form['id']}" if kind == "ipi" else None
                )
                row["pair_id"] = (
                    f"candidate:{task['user_task_id']}:{form['id']}" if kind == "ipi" else None
                )
                row["paraphrase_family_id"] = task["task_template_id"]
                row["variant_id"] = "baseline" if variant is None else variant["id"]
                row["control_role"] = form["id"] if kind == "lexical_control" else None
                row["intervention_span_in_vector"] = None
                row["injections"] = {task["injection_vector"]: task["benign_vector_text"]}
                if form is not None:
                    core = form["template"].replace("{instruction}", task["attack_instruction"])
                    block = variant["before"] + core + variant["after"]
                    base = task["benign_vector_text"]
                    value = base + "\n\n" + block
                    start = len(base) + 2
                    row["injections"] = {task["injection_vector"]: value}
                    row["intervention_span_in_vector"] = {
                        "start": start,
                        "end": len(value),
                        "text": block,
                        "coordinate_system": "unicode_characters_in_vector_value",
                    }
                row["stage"] = (
                    "lead"
                    if kind == "clean"
                    or (kind == "ipi" and task["representative"] and variant == spec["variants"][0])
                    else "expansion"
                )
                row["condition_id"] = stable_condition_id(row, prefix=spec["condition_id_prefix"])
                rows.append(row)
    task_order = {task["user_task_id"]: index for index, task in enumerate(spec["tasks"])}
    rows.sort(
        key=lambda r: (
            r["stage"] != "lead",
            r["condition_family"] != "clean",
            task_order[r["user_task_id"]],
            r["condition_id"],
        )
    )
    groups = connected_component_groups(rows, group_keys=spec["group_keys"])
    for index, row in enumerate(rows, start=1):
        row["execution_order"] = index
        row["group_id"] = groups[row["condition_id"]]
    return rows


def validate_template(spec: dict[str, Any]) -> None:
    """Fail explicitly on incomplete declarations before expanding conditions."""
    required = {
        "schema_version",
        "source",
        "sample_id",
        "condition_id_prefix",
        "expected_counts",
        "lead_count",
        "group_keys",
        "tasks",
        "styles",
        "variants",
        "controls",
    }
    if required - spec.keys() or spec.get("schema_version") != 2:
        raise ValueError("incomplete or unsupported pilot template")
    for section, id_key in (
        ("tasks", "user_task_id"),
        ("styles", "id"),
        ("variants", "id"),
        ("controls", "id"),
    ):
        items = spec[section]
        if not isinstance(items, list) or not items:
            raise ValueError(f"{section} must be a nonempty list")
        ids = [item.get(id_key) for item in items]
        if any(not isinstance(value, str) or not value for value in ids):
            raise ValueError(f"missing {section} identifier")
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate {section} identifier")
    semantic_keys = {
        "task_template_id",
        "attack_goal_id",
        "attack_style_id",
        "attack_template_id",
        "pair_id",
        "paraphrase_family_id",
    }
    if not semantic_keys.issubset(spec["group_keys"]):
        raise ValueError("missing semantic relationship keys")
    task_fields = {
        "task_template_id",
        "representative",
        "task_openness",
        "native_user_prompt",
        "native_ground_truth_calls",
        "first_tool_call",
        "injection_task_id",
        "goal_id",
        "injection_vector",
        "benign_vector_text",
        "candidate_calls",
        "scoring_slots",
        "different_argument_keys",
        "comparison_scope",
        "attack_instruction",
        "measurement_role",
    }
    for task in spec["tasks"]:
        if task_fields - task.keys() or not task["scoring_slots"]:
            raise ValueError("incomplete task or missing scoring slots")
    for form in spec["styles"] + spec["controls"]:
        if form.get("template", "").count("{instruction}") != 1:
            raise ValueError("each form must contain exactly one instruction placeholder")
    for variant in spec["variants"]:
        if not all(isinstance(variant.get(key), str) for key in ("before", "after")):
            raise ValueError("missing variant context")


def validate_sample(spec: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Reject missing, altered, duplicated or misaligned declarations."""
    expected = expand_sample(spec)
    if rows != expected:
        raise ValueError("manifest does not match the deterministic template expansion")
    if len({r["condition_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate condition IDs")
    counts = dict(Counter(r["condition_family"] for r in rows))
    if counts != spec["expected_counts"]:
        raise ValueError("condition counts differ from the fixed sample")
    if sum(r["stage"] == "lead" for r in rows) != spec["lead_count"]:
        raise ValueError("lead sample size differs from its declaration")
    for row in rows:
        if row["task_openness"] not in {"fully_specified", "param_open", "action_open"}:
            raise ValueError("invalid task specification level")
        calls = row["candidate_calls"]
        legitimate, attacker = calls["legitimate"], calls["attacker"]
        if legitimate["name"] != attacker["name"]:
            raise ValueError("candidate tool names must match")
        left, right = legitimate["arguments"], attacker["arguments"]
        changed = sorted(k for k in left.keys() | right.keys() if left.get(k) != right.get(k))
        if changed != row["different_argument_keys"]:
            raise ValueError("declared differing argument keys do not match the calls")
        for slot in row["scoring_slots"]:
            if slot not in left or slot not in right or left[slot] == right[slot]:
                raise ValueError("scoring slot must differ and exist in both calls")
        span = row["intervention_span_in_vector"]
        if span is not None:
            value = row["injections"][row["injection_vector"]]
            if not 0 <= span["start"] < span["end"] <= len(value):
                raise ValueError("intervention span out of range")
            if value[span["start"] : span["end"]] != span["text"]:
                raise ValueError("intervention span text is not aligned")
    return {
        "conditions": len(rows),
        "counts": counts,
        "lead_conditions": spec["lead_count"],
        "task_families": len({r["task_template_id"] for r in rows}),
        "connected_components": len({r["group_id"] for r in rows}),
        "native_preflight": "not_performed_by_this_offline_check",
    }


def validate_pilot_config(config: dict[str, Any], summary: dict[str, Any]) -> None:
    """Cross-check sample sizes, transition denominators and isolation policy."""
    try:
        experiment = config["experiment"]
        gates = config["stop_and_transition"]
        lead = gates["lead_to_expansion"]
        final = gates["final_transition"]
        retry = gates["retry"]
        isolation = config["isolation"]
        resources = config["resources"]
        capture = config["capture"]
        valid = (
            config["schema_version"] == 2
            and experiment["planned_conditions"] == summary["conditions"]
            and experiment["lead_conditions"] == summary["lead_conditions"]
            and lead["completed_lead_conditions"] == summary["lead_conditions"]
            and lead["required_finite_fixed_prefix_diagnostic_pairs"]
            == summary["lead_conditions"] - summary["counts"]["clean"]
            and config["audit"]["transition_success_label"] == "audited_strict_user_task_success"
            and config["decoding"]["do_sample"] is False
            and config["decoding"]["enable_thinking"] is False
            and config["decoding"]["strategy"] == "greedy"
            and isolation["component_count"] == summary["connected_components"]
            and isolation["split"] == "pilot_only"
            and isolation["no_stochastic_repetitions"] is True
            and experiment["execution_authorized_by_this_file"] is False
            and bool(config["required_before_execution"])
            and retry["maximum_per_condition"] == 1
            and retry["allowed_only"]
            == "external_infrastructure_interruption_before_first_model_output"
            and resources["maximum_total_attempts"]
            == summary["conditions"] * (1 + retry["maximum_per_condition"])
            and resources["maximum_total_storage_gib"]
            >= resources["maximum_total_attempts"] * resources["maximum_storage_gib_per_condition"]
            and capture["record_token_index"] is True
            and capture["record_token_id"] is True
        )
        for gate in (lead, final):
            valid = valid and (
                gate["clean_denominator"] == summary["counts"]["clean"]
                and 0 < gate["minimum_clean_success_count"] <= gate["clean_denominator"]
                and 0 < gate["minimum_clean_success_task_families"] <= summary["task_families"]
                and gate["maximum_unresolved_label_disagreements"] == 0
                and gate["minimum_attack_success_count"] == 0
                and gate["minimum_resistant_susceptible_pair_count"] == 0
            )
        valid = (
            valid
            and 0 < final["minimum_actual_exposed_scored_task_families"] <= summary["task_families"]
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("incomplete pilot configuration") from exc
    if not valid:
        raise ValueError("pilot configuration conflicts with sample or execution gates")


def verify_freeze(path: str | Path) -> dict[str, Any]:
    """Check pinned bytes and regenerate the declared sample without model access."""
    freeze_path = Path(path)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    pinned_references = {
        "sample_template": "template",
        "sample_manifest": "manifest",
        "evaluator_spec": "evaluator_spec",
        "model_config": "model_config",
        "domain_config": "domain_config",
    }
    required = {freeze[key] for key in ("config", *pinned_references.values())}
    if not required.issubset(freeze["files_sha256"]):
        raise ValueError("freeze must pin template, manifest, config and evaluator specification")
    for reference, digest in freeze["files_sha256"].items():
        relative = Path(reference)
        if relative.is_absolute():
            raise ValueError("freeze references must be relative")
        target = freeze_path.parent / relative
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError(f"checksum mismatch: {reference}")
    spec = json.loads((freeze_path.parent / freeze["template"]).read_text(encoding="utf-8"))
    manifest = freeze_path.parent / freeze["manifest"]
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    summary = validate_sample(spec, rows)
    config_path = freeze_path.parent / freeze["config"]
    config = load_yaml(config_path)
    validate_pilot_config(config, summary)
    for key, frozen_key in pinned_references.items():
        if (config_path.parent / config["references"][key]).resolve() != (
            freeze_path.parent / freeze[frozen_key]
        ).resolve():
            raise ValueError(f"config reference conflicts with freeze: {key}")
    if (
        config_path.parent / config["references"]["sample_freeze"]
    ).resolve() != freeze_path.resolve():
        raise ValueError("config points to a different sample freeze")
    evaluator = json.loads((freeze_path.parent / freeze["evaluator_spec"]).read_text())
    if evaluator["transition_success_label"] != config["audit"]["transition_success_label"]:
        raise ValueError("evaluation and transition labels disagree")
    if set(evaluator["tasks"]) != {row["user_task_id"] for row in rows}:
        raise ValueError("evaluation task coverage differs from sample")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("freeze", help="path to an offline sample freeze JSON")
    args = parser.parse_args()
    print(json.dumps(verify_freeze(args.freeze), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
