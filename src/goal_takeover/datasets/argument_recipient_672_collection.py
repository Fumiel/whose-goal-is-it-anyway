"""Materialize stable review IDs and the family-aware 672 split.

The output remains review-only until the research runtime is frozen.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from goal_takeover.datasets.argument_recipient_672_native import validate_declarations
from goal_takeover.datasets.generation import stable_condition_id

TRAIN_FAMILIES = frozenset("ABCDEF")
VALIDATION_FAMILIES = frozenset("GHIJ")
PRIOR_TRAIN_COMPONENT = "component_2db488e29b6eaafa"
PRIOR_REC_COMPONENT = "component_0bb81a7a4a45e9ee"
PRIOR_DON_COMPONENT = "component_793e36b0cefb3ebb"

# These are questions raised by the pre-result design review, not declared
# non-edges. The final graph must adjudicate each before claiming independence.
CROSS_SPLIT_REVIEW = (
    ("I", "A", "request-to-pay and name-check invoice versus supplier invoice"),
    ("I", "D", "failed card debit versus loan repayment"),
    ("J", "C", "rental deposit return versus personal refund and repayment"),
    ("J", "E", "estate distribution versus remuneration or payout"),
)

REVIEWED_NON_EDGES = (
    ("G", "B", "tax, certificate, penalty and toll obligations differ from recurring private fees"),
    ("H", "A", "seller revenue distribution differs from buyer purchase payment"),
    ("H", "E", "rights revenue and referral incentives differ from labour and service fees"),
)


def _component_id(family: str) -> str:
    if family in "ACDEIJ":
        return PRIOR_TRAIN_COMPONENT
    if family == "B":
        return PRIOR_REC_COMPONENT
    if family == "F":
        return PRIOR_DON_COMPONENT
    return "component_" + hashlib.sha256(f"argrec672-family:{family}".encode()).hexdigest()[:16]


def build_review_collection(
    draft: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Preserve current family allocation while exposing unresolved graph edges."""
    validate_declarations(draft)
    final = copy.deepcopy(draft)
    final["status"] = "condition_review_runtime_pending"
    final["source_draft_status"] = draft["status"]
    tasks = {task["draft_task_id"]: task for task in final["task_specs"]}
    ids_by_family: dict[str, list[str]] = {family: [] for family in "ABCDEFGHIJ"}
    assignments = []
    for row in final["condition_specs"]:
        task = tasks[row["draft_task_id"]]
        family = row["family_id"]
        split = "train" if family in TRAIN_FAMILIES else "validation"
        if family not in TRAIN_FAMILIES | VALIDATION_FAMILIES or any(
            item["split_candidate"] != split for item in (task, row)
        ):
            raise ValueError(f"split candidate differs from fixed family allocation: {family}")
        row["task_template_id"] = f"argrec672:{task['draft_task_id']}"
        row["pair_id"] = task["draft_pair_id"]
        row["paraphrase_family_id"] = task["semantic_series_id"]
        row["argument_slot_id"] = "send_money.recipient"
        row["task_openness"] = "param_open"
        row["variant_id"] = row["condition_variant"]
        row["source_role"] = row["exposure"]["source_role"]
        row["condition_id"] = stable_condition_id(
            {
                "task_template_id": row["task_template_id"],
                "condition_variant": row["condition_variant"],
                "user_instruction": row["user_instruction"],
                "documents": row["documents"],
                "argument_present": row["argument_present"],
                "expected_tool_sequence": row["expected_tool_sequence"],
            },
            prefix="phase2_argrec672",
        )
        ids_by_family[family].append(row["condition_id"])
        assignments.append(
            {
                "condition_id": row["condition_id"],
                "component_id": _component_id(family),
                "split": split,
            }
        )
    if len({row["condition_id"] for row in assignments}) != 672:
        raise ValueError("stable condition IDs collided")
    if Counter(row["split"] for row in assignments) != {"train": 480, "validation": 192}:
        raise ValueError("fixed train/validation allocation changed")
    batch_counts = Counter(
        row["training_batch"]
        for row in final["condition_specs"]
        if row["split_candidate"] == "train"
    )
    if batch_counts != {f"B{i}": 96 for i in range(1, 6)}:
        raise ValueError("training batch count changed")
    split = {
        "schema_version": 2,
        "split_version": "phase2_argument_recipient_672_review_not_frozen",
        "seed": 20261027,
        "group_keys": [
            "task_template_id",
            "pair_id",
            "paraphrase_family_id",
            "family_id",
            "semantic_relation_to_prior_collections",
        ],
        "assignments": assignments,
    }
    graph = {
        "schema_version": 1,
        "status": "primary_validation_graph_reviewed_runtime_pending",
        "independent_validation_certified": False,
        "primary_validation_independence_certified": True,
        "current_family_allocation": {
            family: "train" if family in TRAIN_FAMILIES else "validation" for family in "ABCDEFGHIJ"
        },
        "component_by_family": {family: _component_id(family) for family in "ABCDEFGHIJ"},
        "prior_train_component": PRIOR_TRAIN_COMPONENT,
        "confirmed_cross_split_edges": [
            {
                "validation_series": "I4",
                "to": PRIOR_TRAIN_COMPONENT,
                "reason": (
                    "invoice plus checked-payee registry closely matches prior two-document payment"
                ),
            },
            {
                "validation_series": "J3",
                "to": PRIOR_TRAIN_COMPONENT,
                "reason": "returning a customer's rental deposit is close to prior REF refund",
            },
        ],
        "family_reporting_role": {
            "G": "independent_validation_primary",
            "H": "independent_validation_primary",
            "I": "train_linked_diagnostic_only",
            "J": "train_linked_diagnostic_only",
        },
        "required_cross_split_reviews": [
            {"validation_family": validation, "train_family": train, "reason": reason}
            for validation, train, reason in CROSS_SPLIT_REVIEW
        ],
        "reviewed_non_edges": [
            {"validation_family": validation, "train_family": train, "reason": reason}
            for validation, train, reason in REVIEWED_NON_EDGES
        ],
        "condition_ids_by_family": ids_by_family,
        "split_counts": {"train": 480, "validation": 192},
        "batch_counts": dict(sorted(batch_counts.items())),
    }
    return final, split, graph


def build_checkpoint_plan(declaration: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    """Predeclare the cumulative B1..B5 development evaluations."""
    if graph["independent_validation_certified"] is not False:
        raise ValueError("review checkpoint plan expects unresolved graph status")
    train_by_batch: dict[str, list[str]] = {f"B{i}": [] for i in range(1, 6)}
    validation = []
    primary_candidate = []
    primary_metric = []
    linked_diagnostic = []
    for row in declaration["condition_specs"]:
        if row["split_candidate"] == "train":
            train_by_batch[row["training_batch"]].append(row["condition_id"])
        else:
            validation.append(row["condition_id"])
            if row["family_id"] in "GH":
                primary_candidate.append(row["condition_id"])
                if row["condition_variant"] in {"rx_ref_y", "ry_ref_x"}:
                    primary_metric.append(row["condition_id"])
            else:
                linked_diagnostic.append(row["condition_id"])
    if len(validation) != 192 or any(len(ids) != 96 for ids in train_by_batch.values()):
        raise ValueError("checkpoint condition counts changed")
    if len(primary_candidate) != 96 or len(linked_diagnostic) != 96:
        raise ValueError("validation reporting allocation changed")
    if len(primary_metric) != 48:
        raise ValueError("role-swap primary metric condition count changed")
    stages = []
    cumulative: list[str] = []
    for index in range(1, 6):
        cumulative.extend(train_by_batch[f"B{index}"])
        stages.append(
            {
                "stage_id": "B1" if index == 1 else f"B1_to_B{index}",
                "added_batch": f"B{index}",
                "train_condition_ids": list(cumulative),
                "validation_condition_ids": list(validation),
                "primary_validation_candidate_ids": list(primary_candidate),
                "primary_metric_condition_ids": list(primary_metric),
                "train_linked_diagnostic_ids": list(linked_diagnostic),
                "train_count": len(cumulative),
                "validation_count": len(validation),
                "primary_validation_candidate_count": len(primary_candidate),
                "primary_metric_condition_count": len(primary_metric),
                "train_linked_diagnostic_count": len(linked_diagnostic),
            }
        )
    return {
        "schema_version": 1,
        "status": "review_pending_fit_and_runtime_spec",
        "primary_metric": "role_swap_auc",
        "primary_metric_variants": ["rx_ref_y", "ry_ref_x"],
        "primary_metric_families": ["G", "H"],
        "primary_metric_candidate_aggregation": "four_candidate_equal_mean",
        "primary_metric_missing_policy": "undefined_if_any_expected_score_missing",
        "primary_metric_threshold": 0.8,
        "secondary_metric": "lexical_present_four_candidate_mean_auc",
        "validation_use": "same_series_repeated_each_stage_adaptive_development",
        "primary_training_source": "new_672_batches_only",
        "prior_96_training_condition_count": 0,
        "prior_rec_don_use": "separate_auxiliary_analysis_only",
        "hyperparameter_selection": {
            "stage": "B1_train_before_validation",
            "method": "leave_one_semantic_series_out_pooled_role_swap_auc",
            "series_count": 8,
            "layer_grid": [0, 8, 16, 24, 32, 35],
            "regularization_c_grid": [0.01, 0.1, 1.0],
            "max_iter": 1000,
            "seed": 20261027,
            "tie_break": "earlier_declared_layer_then_smaller_c",
            "reuse_selected_pair_through": "B5",
        },
        "rule_changes_between_stages": False,
        "independent_validation_certified": False,
        "primary_validation_independence_certified": True,
        "stages": stages,
    }


def build_actual_sample_plan(declaration: dict[str, Any]) -> dict[str, Any]:
    """Preselect one task and its two role-swap variants per semantic series."""
    tasks_by_series: dict[str, list[dict[str, Any]]] = {}
    for task in declaration["task_specs"]:
        tasks_by_series.setdefault(task["semantic_series_id"], []).append(task)
    if len(tasks_by_series) != 56:
        raise ValueError("actual sample requires all 56 series")
    conditions_by_task: dict[str, list[dict[str, Any]]] = {}
    for condition in declaration["condition_specs"]:
        conditions_by_task.setdefault(condition["draft_task_id"], []).append(condition)
    selections = []
    for series_id in sorted(tasks_by_series, key=lambda value: (value[0], int(value[1:]))):
        tasks = sorted(tasks_by_series[series_id], key=lambda task: task["draft_task_id"])
        if len(tasks) != 3:
            raise ValueError(f"actual sample series does not have three tasks: {series_id}")
        series_number = int(series_id[1:])
        selected_task = tasks[(series_number - 1) % 3]
        variants = {
            row["condition_variant"]: row
            for row in conditions_by_task[selected_task["draft_task_id"]]
        }
        if set(variants) != {"rx", "ry", "rx_ref_y", "ry_ref_x"}:
            raise ValueError(f"actual sample task variants differ: {series_id}")
        selections.append(
            {
                "semantic_series_id": series_id,
                "family_id": series_id[0],
                "task_id": selected_task["draft_task_id"],
                "task_position": (series_number - 1) % 3 + 1,
                "split": variants["rx_ref_y"]["split_candidate"],
                "condition_ids": [
                    variants[variant]["condition_id"] for variant in ("rx_ref_y", "ry_ref_x")
                ],
                "condition_variants": ["rx_ref_y", "ry_ref_x"],
            }
        )
    if len({cid for item in selections for cid in item["condition_ids"]}) != 112:
        raise ValueError("actual sample condition IDs are not unique")
    return {
        "schema_version": 1,
        "status": "review_runtime_pending",
        "selection_rule": "one_task_per_series_rotating_task_position_and_both_role_swap_variants",
        "series_count": 56,
        "condition_count": 112,
        "sample_role": "actual_behavior_and_canonical_to_actual_transfer",
        "selections": selections,
    }


def build_frozen_materialization(
    draft: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Apply the same stable content to separate execution-version records."""
    declaration, split, graph = build_review_collection(draft)
    checkpoint = build_checkpoint_plan(declaration, graph)
    actual_sample = build_actual_sample_plan(declaration)
    declaration["status"] = "design_frozen_runtime_pending"
    split["split_version"] = "phase2_argument_recipient_672_v1"
    graph["status"] = "design_frozen_runtime_pending"
    checkpoint["status"] = "design_frozen_runtime_pending"
    actual_sample["status"] = "design_frozen_runtime_pending"
    return declaration, split, graph, checkpoint, actual_sample


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("condition_output", type=Path)
    parser.add_argument("split_output", type=Path)
    parser.add_argument("graph_output", type=Path)
    parser.add_argument("checkpoint_output", type=Path)
    parser.add_argument("--actual-sample-output", type=Path)
    args = parser.parse_args()
    targets = (args.condition_output, args.split_output, args.graph_output, args.checkpoint_output)
    if args.actual_sample_output is not None:
        targets += (args.actual_sample_output,)
    if len(set(targets)) != 4 or any(target.exists() for target in targets):
        raise FileExistsError("collection review outputs must be distinct new files")
    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    final, split, graph = build_review_collection(draft)
    checkpoints = build_checkpoint_plan(final, graph)
    actual_sample = build_actual_sample_plan(final)
    from jsonschema import validate

    schema = json.loads(Path("data/schemas/split.schema.json").read_text(encoding="utf-8"))
    validate(split, schema)
    values = (final, split, graph, checkpoints)
    if args.actual_sample_output is not None:
        values += (actual_sample,)
    for target, value in zip(targets, values, strict=True):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
