"""Isolated AgentDojo Banking sessions for the reviewed argument-readout draft."""

from __future__ import annotations

import copy
from typing import Any

from goal_takeover.datasets.argument_readout_evaluation import (
    evaluate_calls,
    final_state_matches,
    task_and_condition,
    validate_execution_declarations,
)
from goal_takeover.environments.agentdojo import (
    SUPPORTED_BENCHMARK_VERSION,
    AgentDojoCompatibilityError,
    AgentDojoSession,
    _require_agentdojo,
)
from goal_takeover.pilot.evaluation import state_document


def create_session(draft: dict[str, Any], condition_id: str) -> AgentDojoSession:
    """Register one clean custom task in a fresh copy of the pinned Banking suite."""
    validate_execution_declarations(draft)
    task, condition = task_and_condition(draft, condition_id)
    FunctionCall, FunctionsRuntime, get_suite = _require_agentdojo()
    from agentdojo.base_tasks import BaseUserTask

    suite = copy.deepcopy(get_suite(SUPPORTED_BENCHMARK_VERSION, "banking"))
    environment = suite.load_and_inject_default_environment({})
    for document in task["documents"]:
        path = document["path"]
        if path in environment.filesystem.files:
            raise AgentDojoCompatibilityError(f"custom file collides with native fixture: {path}")
        environment.filesystem.files[path] = document["content"]
    pre_environment = environment.model_copy(deep=True)
    task_number = 8000 + next(
        i
        for i, row in enumerate(draft["condition_specs"])
        if row["draft_condition_id"] == condition_id
    )
    user_task_id = f"user_task_{task_number}"
    if user_task_id in suite.user_tasks:
        raise AgentDojoCompatibilityError(
            f"custom task ID collides with native suite: {user_task_id}"
        )

    def ground_truth(self: Any, pre_environment: Any) -> list[Any]:
        return [
            FunctionCall(function=call["name"], args=copy.deepcopy(call["arguments"]))
            for call in condition["expected_tool_sequence"]
        ]

    def utility(self: Any, model_output: str, before: Any, after: Any, strict: bool = True) -> bool:
        # State-only callers can check the transfer; the trace-aware path below
        # additionally requires the declared document reads before payment.
        return final_state_matches(
            state_document(before),
            state_document(after),
            condition["expected_send_money"]["arguments"],
        )

    def utility_from_traces(
        self: Any, model_output: str, before: Any, after: Any, traces: Any
    ) -> bool:
        calls = [{"name": call.function, "arguments": call.args} for call in traces]
        return evaluate_calls(
            task, condition, state_document(before), state_document(after), calls
        )["user_task_success"]

    user_task_class = type(
        f"UserTask{task_number}",
        (BaseUserTask,),
        {
            "PROMPT": condition["user_instruction"],
            "ground_truth": ground_truth,
            "utility": utility,
            "utility_from_traces": utility_from_traces,
        },
    )
    suite.register_user_task(user_task_class)
    if suite.get_user_task_by_id(user_task_id).PROMPT != condition["user_instruction"]:
        raise AgentDojoCompatibilityError("registered prompt differs from condition")
    return AgentDojoSession(
        suite=suite,
        user_task=suite.get_user_task_by_id(user_task_id),
        injection_task=None,
        environment=environment,
        pre_environment=pre_environment,
        runtime=FunctionsRuntime(suite.tools),
        function_call_type=FunctionCall,
        benchmark_version=SUPPORTED_BENCHMARK_VERSION,
    )
