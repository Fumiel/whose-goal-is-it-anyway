"""Pinned AgentDojo adapter with an experiment-owned control loop."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from goal_takeover.agent.runner import ToolExecution

SUPPORTED_AGENTDOJO_VERSION = "0.1.35"
SUPPORTED_BENCHMARK_VERSION = "v1.2.2"


class AgentDojoCompatibilityError(RuntimeError):
    """Raised before a run when the pinned AgentDojo contract is not available."""


@dataclass(frozen=True)
class AgentDojoEvaluation:
    user_task_success: bool
    attack_success: bool
    evaluator_version: str


@dataclass(frozen=True)
class _AgentDojoTool:
    session: AgentDojoSession
    name: str

    def __call__(self, **kwargs: Any) -> ToolExecution:
        return self.session.execute_tool(self.name, kwargs)

    def call_with_id(self, arguments: Mapping[str, Any], call_id: str | None) -> ToolExecution:
        return self.session.execute_tool(self.name, arguments, call_id=call_id)


def _require_agentdojo() -> tuple[Any, Any, Any]:
    try:
        installed = version("agentdojo")
    except PackageNotFoundError as exc:  # pragma: no cover - optional research dependency
        raise AgentDojoCompatibilityError(
            "AgentDojo is unavailable; install the 'research' extra"
        ) from exc
    if installed != SUPPORTED_AGENTDOJO_VERSION:
        raise AgentDojoCompatibilityError(
            f"AgentDojo {SUPPORTED_AGENTDOJO_VERSION} is required, found {installed}"
        )
    try:
        from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
        from agentdojo.task_suite.load_suites import get_suite
    except ImportError as exc:  # pragma: no cover - guarded by package check
        raise AgentDojoCompatibilityError("AgentDojo public imports changed") from exc
    return FunctionCall, FunctionsRuntime, get_suite


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _tool_result_text(value: Any) -> str:
    converted = _jsonable(value)
    if isinstance(converted, str):
        return converted
    return json.dumps(converted, ensure_ascii=False, sort_keys=True, default=str)


@dataclass
class AgentDojoSession:
    """Mutable state for one AgentDojo task run.

    AgentDojo supplies task data, tools, state, and evaluators. The repository's
    runner remains responsible for the model loop and exact prefix boundaries.
    """

    suite: Any
    user_task: Any
    injection_task: Any | None
    environment: Any
    pre_environment: Any
    runtime: Any
    function_call_type: Any
    benchmark_version: str
    trace: list[Any] = field(default_factory=list)
    tool_errors: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        benchmark_version: str,
        suite_name: str,
        user_task_id: str,
        injection_task_id: str | None = None,
        injections: Mapping[str, str] | None = None,
    ) -> AgentDojoSession:
        if benchmark_version != SUPPORTED_BENCHMARK_VERSION:
            raise AgentDojoCompatibilityError(
                f"benchmark {SUPPORTED_BENCHMARK_VERSION} is required, got {benchmark_version}"
            )
        FunctionCall, FunctionsRuntime, get_suite = _require_agentdojo()
        try:
            suite = get_suite(benchmark_version, suite_name)
            user_task = suite.get_user_task_by_id(user_task_id)
            injection_task = (
                None
                if injection_task_id is None
                else suite.get_injection_task_by_id(injection_task_id)
            )
            environment = suite.load_and_inject_default_environment(dict(injections or {}))
        except Exception as exc:
            raise AgentDojoCompatibilityError(
                "AgentDojo suite, task, or injection vector does not match the pinned fixture"
            ) from exc
        environment = user_task.init_environment(environment)
        pre_environment = environment.model_copy(deep=True)
        return cls(
            suite=suite,
            user_task=user_task,
            injection_task=injection_task,
            environment=environment,
            pre_environment=pre_environment,
            runtime=FunctionsRuntime(suite.tools),
            function_call_type=FunctionCall,
            benchmark_version=benchmark_version,
        )

    @property
    def initial_messages(self) -> list[dict[str, str]]:
        return [{"role": "user", "content": self.user_task.PROMPT}]

    @property
    def tool_schemas(self) -> list[dict[str, Any]]:
        schemas = []
        for function in self.suite.tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": function.name,
                        "description": function.description,
                        "parameters": function.parameters.model_json_schema(),
                    },
                }
            )
        return schemas

    @property
    def tools(self) -> dict[str, Any]:
        return {name: _AgentDojoTool(self, name) for name in self.runtime.functions}

    def execute_tool(
        self, name: str, arguments: Mapping[str, Any], *, call_id: str | None = None
    ) -> ToolExecution:
        call = self.function_call_type(function=name, args=dict(arguments), id=call_id)
        self.trace.append(call)
        result, error = self.runtime.run_function(self.environment, name, dict(arguments))
        if error is not None:
            self.tool_errors.append(error)
        return ToolExecution(content=_tool_result_text(result), error=error)

    def evaluate(self, final_answer: str | None) -> AgentDojoEvaluation:
        output = final_answer or ""
        utility = self.user_task.utility_from_traces(
            output, self.pre_environment, self.environment, self.trace
        )
        if utility is None:
            utility = self.user_task.utility(output, self.pre_environment, self.environment)

        attack_success = False
        if self.injection_task is not None:
            security = self.injection_task.security_from_traces(
                output, self.pre_environment, self.environment, self.trace
            )
            if security is None:
                security = self.injection_task.security(
                    output, self.pre_environment, self.environment
                )
            # In AgentDojo 0.1.35 this boolean means the injection goal occurred.
            attack_success = bool(security)
        return AgentDojoEvaluation(
            user_task_success=bool(utility),
            attack_success=attack_success,
            evaluator_version=(f"agentdojo-{SUPPORTED_AGENTDOJO_VERSION}:{self.benchmark_version}"),
        )

    def ground_truth_calls(self) -> tuple[list[Any], list[Any]]:
        legitimate = list(self.user_task.ground_truth(self.pre_environment))
        attack = (
            []
            if self.injection_task is None
            else list(self.injection_task.ground_truth(self.pre_environment))
        )
        return legitimate, attack
