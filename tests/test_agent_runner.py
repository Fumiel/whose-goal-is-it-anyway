import unittest

from goal_takeover.agent.runner import AgentAction, AgentToolCall, ToolExecution, run_agent
from goal_takeover.models.qwen import parse_qwen_action
from goal_takeover.schemas import AgentBoundary


class ScriptedBackend:
    def __init__(self, actions: list[AgentAction]) -> None:
        self.actions = iter(actions)

    def next_action(self, _messages):
        return next(self.actions)


class AgentRunnerTest(unittest.TestCase):
    def test_tool_outputs_are_marked_untrusted_and_boundaries_are_emitted(self) -> None:
        backend = ScriptedBackend(
            [
                AgentAction(kind="tool", tool_name="read", tool_arguments={}),
                AgentAction(kind="tool", tool_name="send", tool_arguments={}),
                AgentAction(kind="final", content="done"),
            ]
        )
        boundaries = []
        run = run_agent(
            backend,
            [{"role": "user", "content": "test"}],
            {"read": lambda: "external text", "send": lambda: "sent"},
            on_boundary=lambda boundary, _messages: boundaries.append(boundary),
        )

        tool_messages = [message for message in run.messages if message["role"] == "tool"]
        self.assertTrue(all(message["untrusted"] is True for message in tool_messages))
        self.assertEqual(
            boundaries,
            [
                AgentBoundary.USER_TO_ASSISTANT,
                AgentBoundary.FIRST_TOOL_TO_ASSISTANT,
                AgentBoundary.LATER_TOOL_TO_ASSISTANT,
            ],
        )
        self.assertEqual(run.final_answer, "done")

    def test_raw_tool_call_id_and_error_are_preserved(self) -> None:
        class ToolWithCallId:
            def call_with_id(self, arguments, call_id):
                self.observed = (arguments, call_id)
                return ToolExecution(content="", error="ValidationError: invalid")

        tool = ToolWithCallId()
        assistant_message = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_7",
                    "type": "function",
                    "function": {"name": "send", "arguments": {"amount": -1}},
                }
            ],
        }
        run = run_agent(
            ScriptedBackend(
                [
                    AgentAction(
                        kind="tool",
                        tool_name="send",
                        tool_arguments={"amount": -1},
                        tool_call_id="call_7",
                        raw_text="<tool_call>...</tool_call>",
                        assistant_message=assistant_message,
                    ),
                    AgentAction(kind="final", content="done"),
                ]
            ),
            [{"role": "user", "content": "test"}],
            {"send": tool},
        )

        self.assertEqual(tool.observed, ({"amount": -1}, "call_7"))
        self.assertEqual(run.messages[1], assistant_message)
        self.assertEqual(run.messages[2]["tool_call_id"], "call_7")
        self.assertEqual(run.messages[2]["error"], "ValidationError: invalid")

    def test_multiple_qwen_calls_execute_in_order_with_one_assistant_message(self) -> None:
        observed = []

        def read(account):
            observed.append(("read", account))
            return "balance"

        def refund(amount):
            observed.append(("refund", amount))
            return "refunded"

        action = parse_qwen_action(
            '<tool_call>{"name":"read","arguments":{"account":"A"}}</tool_call>'
            '<tool_call>{"name":"refund","arguments":{"amount":4}}</tool_call>',
            call_id="call_0000",
        )
        boundaries = []
        run = run_agent(
            ScriptedBackend([action, AgentAction(kind="final", content="done")]),
            [{"role": "user", "content": "test"}],
            {"read": read, "refund": refund},
            on_boundary=lambda boundary, _messages: boundaries.append(boundary),
        )

        self.assertEqual(observed, [("read", "A"), ("refund", 4)])
        self.assertEqual(
            [message["role"] for message in run.messages],
            ["user", "assistant", "tool", "tool"],
        )
        self.assertEqual(
            [message["tool_call_id"] for message in run.messages[2:]],
            ["call_0000", "call_0000_1"],
        )
        self.assertTrue(all(message["untrusted"] for message in run.messages[2:]))
        self.assertEqual(
            boundaries,
            [AgentBoundary.USER_TO_ASSISTANT, AgentBoundary.LATER_TOOL_TO_ASSISTANT],
        )
        self.assertEqual(run.final_answer, "done")

    def test_unknown_call_in_batch_does_not_execute_any_tool(self) -> None:
        observed = []
        action = AgentAction(
            kind="tool",
            tool_calls=(
                AgentToolCall("read", {}, "call_1"),
                AgentToolCall("missing", {}, "call_2"),
            ),
        )

        run = run_agent(
            ScriptedBackend([action]),
            [{"role": "user", "content": "test"}],
            {"read": lambda: observed.append("read")},
        )

        self.assertEqual(observed, [])
        self.assertEqual(run.stop_reason, "unknown_tool")
        self.assertEqual(len(run.messages[1]["tool_calls"]), 2)


if __name__ == "__main__":
    unittest.main()
