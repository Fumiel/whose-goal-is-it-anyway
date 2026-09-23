import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from goal_takeover.cli import main
from goal_takeover.models.qwen import QwenToolCallParseError
from goal_takeover.shakedown import write_shakedown_failure


class ShakedownFailureTest(unittest.TestCase):
    def test_failure_records_fixture_stage_and_raw_model_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_text = '<tool_call>{"name":"broken"}</tool_call>'
            error = QwenToolCallParseError("missing arguments", raw_text=raw_text)
            with patch(
                "goal_takeover.shakedown.load_yaml",
                return_value={"experiment": {"artifact_root": directory}},
            ):
                path = write_shakedown_failure(
                    "configs/selection/pre_gate_shakedown.yaml",
                    run_prefix="test-multiple-calls",
                    stage="actual_agent_loop",
                    fixture_id="banking_multistep_user_task_3",
                    error=error,
                )

            failure = json.loads((Path(path) / "failure.json").read_text())
            self.assertEqual(failure["fixture_id"], "banking_multistep_user_task_3")
            self.assertEqual(failure["stage"], "actual_agent_loop")
            self.assertEqual(failure["raw_model_output"], raw_text)
            self.assertEqual(failure["kind"], "QwenToolCallParseError")
            self.assertTrue((Path(path) / "manifest.json").exists())

    def test_cli_passes_current_fixture_and_stage_to_failure_writer(self) -> None:
        recorded = {}

        def fail_run(_config, _model_config, *, run_prefix, progress):
            self.assertEqual(run_prefix, "test-multiple-calls")
            progress.fixture_id = "banking_multistep_user_task_3"
            progress.stage = "measurement_generation"
            raise QwenToolCallParseError("invalid", raw_text="<tool_call>bad</tool_call>")

        def record_failure(_config, **kwargs):
            recorded.update(kwargs)
            return Path("artifacts/runs/test-multiple-calls-technical-failure")

        with (
            patch("goal_takeover.shakedown.run_agentdojo_shakedown", side_effect=fail_run),
            patch("goal_takeover.shakedown.write_shakedown_failure", side_effect=record_failure),
            redirect_stdout(io.StringIO()),
        ):
            status = main(
                [
                    "agentdojo-shakedown",
                    "configs/selection/pre_gate_shakedown.yaml",
                    "--model-config",
                    "configs/models/qwen3_8b_int8.yaml",
                    "--run-prefix",
                    "test-multiple-calls",
                ]
            )

        self.assertEqual(status, 1)
        self.assertEqual(recorded["fixture_id"], "banking_multistep_user_task_3")
        self.assertEqual(recorded["stage"], "measurement_generation")
        self.assertIsInstance(recorded["error"], QwenToolCallParseError)


if __name__ == "__main__":
    unittest.main()
