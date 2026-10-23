"""Materialize the approved 96-condition recipient collection without model runs."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from goal_takeover.datasets.argument_readout_evaluation import validate_execution_declarations
from goal_takeover.datasets.generation import stable_condition_id

EXISTING_TRAIN_COMPONENT = "component_2db488e29b6eaafa"
TRAIN_SERIES = frozenset(
    {"invoice_payment", "personal_refund", "product_payment", "expense_reimbursement"}
)
VALIDATION_SERIES = frozenset({"recurring_payment", "donation_transfer"})


def _component_id(condition_ids: list[str]) -> str:
    return "component_" + hashlib.sha256("\n".join(sorted(condition_ids)).encode()).hexdigest()[:16]


def build_collection(
    draft: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Assign stable IDs and preserve connected task/series groups across splits."""
    validate_execution_declarations(draft)
    if len(draft["task_specs"]) != 24 or len(draft["condition_specs"]) != 96:
        raise ValueError("approved collection size changed")
    final = copy.deepcopy(draft)
    final["status"] = "design_frozen_runtime_pending"
    final["source_draft_status"] = draft["status"]
    tasks = {task["draft_task_id"]: task for task in final["task_specs"]}
    by_series: dict[str, list[str]] = {}
    for condition in final["condition_specs"]:
        task = tasks[condition["draft_task_id"]]
        series = task["semantic_series_id"]
        if series not in TRAIN_SERIES | VALIDATION_SERIES:
            raise ValueError(f"unreviewed semantic series: {series}")
        expected_split = "train" if series in TRAIN_SERIES else "validation"
        if (
            task["split_candidate"] != expected_split
            or condition["split_candidate"] != expected_split
        ):
            raise ValueError("approved series/split candidate changed")
        condition["task_template_id"] = task["draft_task_template_id"]
        condition["pair_id"] = task["draft_pair_id"]
        condition["paraphrase_family_id"] = series
        condition["argument_slot_id"] = "send_money.recipient"
        condition["task_openness"] = "param_open"
        # The four content cells stay in condition_variant. The measurement
        # selector uses variant_id for the exposure surface.
        condition["variant_id"] = "user_instruction"
        condition["condition_id"] = stable_condition_id(
            {
                "task_template_id": condition["task_template_id"],
                "variant_id": condition["variant_id"],
                "condition_variant": condition["condition_variant"],
                "user_instruction": condition["user_instruction"],
                "documents": task["documents"],
                "account_values": draft["account_value_ids"],
                "argument_present": condition["argument_present"],
            },
            prefix="phase2_arg_recipient",
        )
        by_series.setdefault(series, []).append(condition["condition_id"])
    if len({row["condition_id"] for row in final["condition_specs"]}) != 96:
        raise ValueError("stable condition IDs collided")
    components = {
        series: EXISTING_TRAIN_COMPONENT if series in TRAIN_SERIES else _component_id(ids)
        for series, ids in by_series.items()
    }
    assignments = []
    for condition in final["condition_specs"]:
        series = tasks[condition["draft_task_id"]]["semantic_series_id"]
        assignments.append(
            {
                "condition_id": condition["condition_id"],
                "component_id": components[series],
                "split": condition["split_candidate"],
            }
        )
    split = {
        "schema_version": 2,
        "split_version": "phase2_argument_readout_96_v1",
        "seed": 20261024,
        "group_keys": [
            "task_template_id",
            "pair_id",
            "paraphrase_family_id",
            "semantic_series_id",
            "semantic_relation_to_prior_pilot",
        ],
        "assignments": assignments,
    }
    graph = {
        "schema_version": 1,
        "status": "design_frozen_runtime_pending",
        "existing_train_component_id": EXISTING_TRAIN_COMPONENT,
        "component_by_series": components,
        "edges": [
            {
                "from": "invoice_payment",
                "to": EXISTING_TRAIN_COMPONENT,
                "reason": "near_pilot_bill_payment_and_two_document_v2",
            },
            {
                "from": "personal_refund",
                "to": EXISTING_TRAIN_COMPONENT,
                "reason": "near_pilot_friend_refund",
            },
            {
                "from": "product_payment",
                "to": EXISTING_TRAIN_COMPONENT,
                "reason": "near_purchase_order_reconciliation",
            },
            {
                "from": "expense_reimbursement",
                "to": "personal_refund",
                "reason": "near_reimbursement_and_personal_settlement",
            },
        ],
        "reviewed_non_edges": [
            {
                "from": "recurring_payment",
                "to": EXISTING_TRAIN_COMPONENT,
                "reason": (
                    "current-period one-time membership transfer differs "
                    "from prior schedule updates"
                ),
            },
            {
                "from": "donation_transfer",
                "to": "expense_reimbursement",
                "reason": (
                    "grant allocation and expense reimbursement differ in "
                    "objective, beneficiary and source record"
                ),
            },
            {
                "from": "shared_account_phrasing",
                "to": "cross_series_tasks",
                "reason": (
                    "short recipient/reference sentence scaffold is a lexical control, "
                    "not a close paraphrase of the task objective or document"
                ),
            },
        ],
        "condition_ids_by_series": by_series,
        "split_counts": {"train": 64, "validation": 32},
    }
    return final, split, graph


def write_collection(
    draft_path: Path, template_path: Path, split_path: Path, graph_path: Path
) -> None:
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    final, split, graph = build_collection(draft)
    for target, value in (
        (template_path, final),
        (split_path, split),
        (graph_path, graph),
    ):
        if target.exists():
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("template", type=Path)
    parser.add_argument("split", type=Path)
    parser.add_argument("graph", type=Path)
    args = parser.parse_args()
    write_collection(args.draft, args.template, args.split, args.graph)
