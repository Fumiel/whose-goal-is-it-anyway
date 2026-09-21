import unittest
from types import SimpleNamespace
from unittest.mock import patch

from goal_takeover.environments.agentdojo import (
    AgentDojoCompatibilityError,
    AgentDojoSession,
)


class FakeEnvironment:
    def __init__(self):
        self.calls = []

    def model_copy(self, *, deep):
        copied = FakeEnvironment()
        copied.calls = list(self.calls)
        return copied


class FakeFunctionCall:
    def __init__(self, *, function, args, id=None):
        self.function = function
        self.args = args
        self.id = id


class FakeRuntime:
    def __init__(self, functions):
        self.functions = {function.name: function for function in functions}

    def run_function(self, environment, name, arguments):
        environment.calls.append((name, arguments))
        return {"ok": True}, None


class FakeTask:
    PROMPT = "Do the task"

    def init_environment(self, environment):
        return environment

    def ground_truth(self, _environment):
        return [FakeFunctionCall(function="read", args={})]

    def utility_from_traces(self, _output, _pre, _post, traces):
        return bool(traces)

    def utility(self, _output, _pre, _post):
        return False


class FakeInjectionTask:
    def ground_truth(self, _environment):
        return [FakeFunctionCall(function="send", args={"recipient": "eve"})]

    def security_from_traces(self, _output, _pre, _post, traces):
        return any(trace.function == "send" for trace in traces)

    def security(self, _output, _pre, _post):
        return False


class FakeParameters:
    @staticmethod
    def model_json_schema():
        return {"type": "object", "properties": {}}


class FakeSuite:
    def __init__(self):
        self.tools = [
            SimpleNamespace(name="read", description="read", parameters=FakeParameters()),
            SimpleNamespace(name="send", description="send", parameters=FakeParameters()),
        ]

    def get_user_task_by_id(self, _task_id):
        return FakeTask()

    def get_injection_task_by_id(self, _task_id):
        return FakeInjectionTask()

    def load_and_inject_default_environment(self, _injections):
        return FakeEnvironment()


class AgentDojoAdapterTest(unittest.TestCase):
    def test_session_preserves_trace_id_and_independent_evaluations(self) -> None:
        suite = FakeSuite()
        dependencies = (FakeFunctionCall, FakeRuntime, lambda _version, _name: suite)
        with patch(
            "goal_takeover.environments.agentdojo._require_agentdojo",
            return_value=dependencies,
        ):
            session = AgentDojoSession.create(
                benchmark_version="v1.2.2",
                suite_name="banking",
                user_task_id="user_task_0",
                injection_task_id="injection_task_0",
                injections={"injection_bill_text": "fixed"},
            )

        session.execute_tool("read", {}, call_id="call_1")
        first = session.evaluate("done")
        self.assertTrue(first.user_task_success)
        self.assertFalse(first.attack_success)
        self.assertEqual(session.trace[0].id, "call_1")

        session.execute_tool("send", {"recipient": "eve"}, call_id="call_2")
        second = session.evaluate("done")
        self.assertTrue(second.user_task_success)
        self.assertTrue(second.attack_success)
        self.assertEqual(second.evaluator_version, "agentdojo-0.1.35:v1.2.2")

    def test_unverified_benchmark_version_fails_closed(self) -> None:
        with self.assertRaises(AgentDojoCompatibilityError):
            AgentDojoSession.create(
                benchmark_version="v1.3",
                suite_name="banking",
                user_task_id="user_task_0",
            )


if __name__ == "__main__":
    unittest.main()
