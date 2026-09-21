import importlib.util
import unittest
from pathlib import Path

from goal_takeover.config import load_yaml
from goal_takeover.environments.agentdojo import AgentDojoSession


@unittest.skipUnless(importlib.util.find_spec("agentdojo"), "AgentDojo is not installed")
class AgentDojoIntegrationTest(unittest.TestCase):
    def test_pinned_banking_fixtures_match_agentdojo_0_1_35(self) -> None:
        root = Path(__file__).parents[1]
        config = load_yaml(root / "configs/selection/pre_gate_shakedown.yaml")
        experiment = config["experiment"]
        self.assertEqual(len(config["fixtures"]), 3)

        sessions = []
        for fixture in config["fixtures"]:
            sessions.append(
                AgentDojoSession.create(
                    benchmark_version=experiment["benchmark_version"],
                    suite_name=experiment["suite"],
                    user_task_id=fixture["user_task_id"],
                    injection_task_id=fixture.get("injection_task_id"),
                    injections=fixture.get("injections", {}),
                )
            )
        self.assertTrue(all(len(session.tool_schemas) == 11 for session in sessions))

        fixture = config["fixtures"][2]
        session = sessions[2]
        legitimate, attack = session.ground_truth_calls()
        legitimate_call = legitimate[fixture["legitimate_call_index"]]
        attack_call = attack[fixture["attack_call_index"]]
        self.assertEqual(legitimate_call.function, "send_money")
        self.assertEqual(attack_call.function, "send_money")
        self.assertNotEqual(
            legitimate_call.args[fixture["primary_argument_slot"]],
            attack_call.args[fixture["primary_argument_slot"]],
        )
        result = session.execute_tool(
            legitimate[0].function, legitimate[0].args, call_id="fixture_probe"
        )
        self.assertIsNone(result.error)
        self.assertIn(fixture["injection_match_text"], result.content)


if __name__ == "__main__":
    unittest.main()
