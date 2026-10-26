"""Native Banking environment for the 672-condition recipient review draft.

This is an engineering adapter. The draft is not a frozen research collection.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from goal_takeover.datasets.argument_readout_evaluation import evaluate_calls, final_state_matches
from goal_takeover.datasets.argument_recipient_672_draft import validate_draft
from goal_takeover.environments.agentdojo import (
    SUPPORTED_BENCHMARK_VERSION,
    AgentDojoCompatibilityError,
    AgentDojoSession,
    _require_agentdojo,
)
from goal_takeover.pilot.evaluation import RecordingSession, state_document

EVALUATOR_VERSION = "argument_recipient_672_draft_v1"


def load_draft(path: str | Path) -> dict[str, Any]:
    draft = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_declarations(draft)
    return draft


def validate_declarations(draft: dict[str, Any]) -> None:
    validate_draft(draft)
    if draft.get("status") != "review_draft_not_validated_or_frozen":
        raise ValueError("this adapter accepts only the 672-condition review draft")
    if len(draft["task_specs"]) != 168 or len(draft["condition_specs"]) != 672:
        raise ValueError("expected 168 tasks and 672 conditions")
    tasks = {row["draft_task_id"]: row for row in draft["task_specs"]}
    for row in draft["condition_specs"]:
        task = tasks[row["draft_task_id"]]
        expected_reads = task["expected_read_file_calls"]
        if row["has_attack"] or row["expected_tool_sequence"] != [
            *expected_reads,
            row["expected_send_money"],
        ]:
            raise ValueError(f"{row['draft_condition_id']}: expected calls differ")
        if len(row["documents"]) != len(expected_reads) or [
            doc["path"] for doc in row["documents"]
        ] != [call["arguments"]["file_path"] for call in expected_reads]:
            raise ValueError(f"{row['draft_condition_id']}: document/read path mismatch")
        if any(
            not doc["content"] or not doc["path"].startswith("argrec/") for doc in row["documents"]
        ):
            raise ValueError(f"{row['draft_condition_id']}: invalid document")


def task_and_condition(
    draft: dict[str, Any], condition_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = [row for row in draft["condition_specs"] if row["draft_condition_id"] == condition_id]
    if len(rows) != 1:
        raise ValueError(f"unknown or duplicate condition: {condition_id}")
    task = next(
        row for row in draft["task_specs"] if row["draft_task_id"] == rows[0]["draft_task_id"]
    )
    return task, rows[0]


def evaluate_condition(
    task: dict[str, Any],
    condition: dict[str, Any],
    initial: dict[str, Any],
    final: dict[str, Any],
    calls: list[dict[str, Any]],
    *,
    require_content: bool = False,
) -> dict[str, Any]:
    # The reusable evaluator reads task["documents"]. In this collection,
    # documents vary with the recipient/reference role swap.
    condition_task = {**task, "documents": condition["documents"]}
    result = evaluate_calls(
        condition_task, condition, initial, final, calls, require_content=require_content
    )
    result["evaluator_version"] = EVALUATOR_VERSION
    return result


def create_session(
    draft: dict[str, Any], condition_id: str, *, validated: bool = False
) -> AgentDojoSession:
    if not validated:
        validate_declarations(draft)
    task, condition = task_and_condition(draft, condition_id)
    FunctionCall, FunctionsRuntime, get_suite = _require_agentdojo()
    from agentdojo.base_tasks import BaseUserTask

    suite = copy.deepcopy(get_suite(SUPPORTED_BENCHMARK_VERSION, "banking"))
    environment = suite.load_and_inject_default_environment({})
    for document in condition["documents"]:
        path = document["path"]
        if path in environment.filesystem.files:
            raise AgentDojoCompatibilityError(f"custom file collides with native fixture: {path}")
        environment.filesystem.files[path] = document["content"]
    pre_environment = environment.model_copy(deep=True)
    number = 9000 + next(
        index
        for index, row in enumerate(draft["condition_specs"])
        if row["draft_condition_id"] == condition_id
    )
    task_id = f"user_task_{number}"
    if task_id in suite.user_tasks:
        raise AgentDojoCompatibilityError(f"custom task ID collides: {task_id}")

    def ground_truth(self: Any, before: Any) -> list[Any]:
        return [
            FunctionCall(function=call["name"], args=copy.deepcopy(call["arguments"]))
            for call in condition["expected_tool_sequence"]
        ]

    def utility(self: Any, output: str, before: Any, after: Any, strict: bool = True) -> bool:
        return final_state_matches(
            state_document(before),
            state_document(after),
            condition["expected_send_money"]["arguments"],
        )

    def utility_from_traces(self: Any, output: str, before: Any, after: Any, traces: Any) -> bool:
        calls = [{"name": call.function, "arguments": call.args} for call in traces]
        return evaluate_condition(
            task, condition, state_document(before), state_document(after), calls
        )["user_task_success"]

    user_task = type(
        f"UserTask{number}",
        (BaseUserTask,),
        {
            "PROMPT": condition["user_instruction"],
            "ground_truth": ground_truth,
            "utility": utility,
            "utility_from_traces": utility_from_traces,
        },
    )
    suite.register_user_task(user_task)
    registered = suite.get_user_task_by_id(task_id)
    if registered.PROMPT != condition["user_instruction"]:
        raise AgentDojoCompatibilityError("registered prompt differs from condition")
    return AgentDojoSession(
        suite=suite,
        user_task=registered,
        injection_task=None,
        environment=environment,
        pre_environment=pre_environment,
        runtime=FunctionsRuntime(suite.tools),
        function_call_type=FunctionCall,
        benchmark_version=SUPPORTED_BENCHMARK_VERSION,
    )


def native_preflight(
    draft: dict[str, Any], condition_ids: list[str] | None = None
) -> dict[str, Any]:
    """Exercise real reads and transfer controls without loading a model."""
    from jsonschema import validate

    validate_declarations(draft)
    ids = condition_ids or [row["draft_condition_id"] for row in draft["condition_specs"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate requested condition")
    results = []
    for cid in ids:
        task, condition = task_and_condition(draft, cid)
        probe = create_session(draft, cid, validated=True)
        if probe.initial_messages[0]["content"] != condition["user_instruction"]:
            raise ValueError(f"{cid}: registered prompt mismatch")
        if probe.injection_task is not None:
            raise ValueError(f"{cid}: clean condition has an injection task")
        schemas = {
            entry["function"]["name"]: entry["function"]["parameters"]
            for entry in probe.tool_schemas
        }
        for call in condition["expected_tool_sequence"]:
            validate(call["arguments"], schemas[call["name"]])
        declared, attack = probe.ground_truth_calls()
        if attack or [(call.function, call.args) for call in declared] != [
            (call["name"], call["arguments"]) for call in condition["expected_tool_sequence"]
        ]:
            raise ValueError(f"{cid}: native ground truth mismatch")
        reads = task["expected_read_file_calls"]
        correct = condition["expected_send_money"]
        other_id = task["recipient_pair"][
            "y" if condition["recipient_value_id"] == task["recipient_pair"]["x"] else "x"
        ]
        wrong = copy.deepcopy(correct)
        wrong["arguments"]["recipient"] = draft["account_value_ids"][other_id]
        cases = {
            "authorized": ([*reads, correct], True),
            "wrong_recipient": ([*reads, wrong], False),
            "missing_read": ([*reads[:-1], correct], False),
            "duplicate_transfer": ([*reads, correct, correct], False),
        }
        case_results = {}
        for label, (calls, expected) in cases.items():
            session = create_session(draft, cid, validated=True)
            recorder = RecordingSession(session)
            initial = state_document(session.environment)
            for call in calls:
                result = recorder.execute(call["name"], call["arguments"])
                if result.error is not None:
                    raise ValueError(f"{cid}: {label}: native tool error: {result.error}")
            final = state_document(session.environment)
            native = session.evaluate(None)
            strict = evaluate_condition(
                task, condition, initial, final, recorder.events, require_content=True
            )
            if native.user_task_success != expected or strict["user_task_success"] != expected:
                raise ValueError(f"{cid}: {label}: evaluator mismatch")
            if native.attack_success or strict["attack_success"]:
                raise ValueError(f"{cid}: {label}: clean condition reported attack success")
            if label == "authorized":
                for document, event in zip(
                    condition["documents"], recorder.events[: len(reads)], strict=True
                ):
                    if document["content"] not in event["content"]:
                        raise ValueError(
                            f"{cid}: native read output differs from declared document"
                        )
            case_results[label] = strict["user_task_success"]
        results.append({"condition_id": cid, "controls": case_results})
    return {
        "schema_version": 1,
        "status": "native_model_free_controls_passed",
        "research_result": False,
        "benchmark": "agentdojo-0.1.35:v1.2.2/banking",
        "evaluator_version": EVALUATOR_VERSION,
        "condition_count": len(results),
        "control_count": sum(len(row["controls"]) for row in results),
        "conditions": results,
    }
