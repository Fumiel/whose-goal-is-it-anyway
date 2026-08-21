import unittest

from goal_takeover.agent.runner import AgentAction, run_agent
from goal_takeover.schemas import ProcessingStage


class ScriptedBackend:
    def __init__(self, actions: list[AgentAction]) -> None:
        self.actions = iter(actions)

    def next_action(self, _messages):
        return next(self.actions)


class AgentRunnerTest(unittest.TestCase):
    def test_tool_outputs_are_marked_untrusted_and_stages_are_emitted(self) -> None:
        backend = ScriptedBackend(
            [
                AgentAction(kind="tool", tool_name="read", tool_arguments={}),
                AgentAction(kind="tool", tool_name="send", tool_arguments={}),
                AgentAction(kind="final", content="done"),
            ]
        )
        stages = []
        run = run_agent(
            backend,
            [{"role": "user", "content": "test"}],
            {"read": lambda: "external text", "send": lambda: "sent"},
            on_stage=lambda stage, _messages: stages.append(stage),
        )

        tool_messages = [message for message in run.messages if message["role"] == "tool"]
        self.assertTrue(all(message["untrusted"] is True for message in tool_messages))
        self.assertIn(ProcessingStage.AFTER_USER_INSTRUCTION, stages)
        self.assertIn(ProcessingStage.AFTER_TOOL_OUTPUT, stages)
        self.assertIn(ProcessingStage.BEFORE_FINAL_TOOL_CALL, stages)
        self.assertEqual(run.final_answer, "done")


if __name__ == "__main__":
    unittest.main()
