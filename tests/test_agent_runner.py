import unittest

from goal_takeover.agent.runner import AgentAction, ToolExecution, run_agent
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


if __name__ == "__main__":
    unittest.main()
