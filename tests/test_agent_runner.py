import unittest

from goal_takeover.agent.runner import AgentAction, run_agent
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


if __name__ == "__main__":
    unittest.main()
