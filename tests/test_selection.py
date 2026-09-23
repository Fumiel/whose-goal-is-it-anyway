import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from goal_takeover.agent.runner import AgentAction, AgentRun
from goal_takeover.config import ConfigError
from goal_takeover.selection import (
    load_selection_plan,
    preflight_selection,
    selection_output_documents,
    summarize_selection,
)

GATE = Path(__file__).parents[1] / "configs/selection/integration_gate.yaml"


@unittest.skipUnless(importlib.util.find_spec("agentdojo"), "AgentDojo is not installed")
class SelectionPreflightTest(unittest.TestCase):
    def test_pinned_sample_and_evaluator_controls(self) -> None:
        plan = load_selection_plan(GATE, require_frozen=False)
        reports = preflight_selection(plan)
        self.assertEqual(len(reports), 7)
        self.assertEqual(sum("injection_start" in report for report in reports), 2)
        for report in reports[-2:]:
            self.assertLess(report["injection_start"], report["injection_end"])
            self.assertEqual(report["legitimate_call"]["name"], report["attack_call"]["name"])
            self.assertNotEqual(
                report["legitimate_call"]["arguments"],
                report["attack_call"]["arguments"],
            )
            self.assertEqual(
                report["evaluator_control_states"]["attack"],
                {"user_task_success": False, "attack_success": True},
            )

    def test_declaration_drift_fails_before_model_load(self) -> None:
        plan = load_selection_plan(GATE, require_frozen=False)
        sample = copy.deepcopy(plan.sample)
        sample["selection"]["conditions"][5]["attack_call"]["arguments"]["id"] = 999
        tampered = type(plan)(
            plan.gate_path, plan.sample_path, plan.gate, sample, plan.checksums, plan.freeze
        )
        with self.assertRaisesRegex(ConfigError, "attack call differs"):
            preflight_selection(tampered)


class SelectionSummaryTest(unittest.TestCase):
    def test_raw_generations_and_final_reply_are_preserved_for_audit(self) -> None:
        measurement = AgentAction(kind="final", content="probe", raw_text="probe")
        final = AgentAction(kind="final", content="You spent £200.", raw_text="You spent £200.")
        actual = AgentRun(
            messages=[{"role": "user", "content": "How much?"}],
            actions=[final],
            final_answer="You spent £200.",
            stop_reason="final_answer",
        )
        measured, output, messages = selection_output_documents(
            measurement, "measurement-prefix", actual, [SimpleNamespace(prefix_id="actual-prefix")]
        )
        self.assertEqual(measured["generation"]["raw_text"], "probe")
        self.assertEqual(output["generations"][0]["raw_text"], "You spent £200.")
        self.assertEqual(output["generations"][0]["prefix_id"], "actual-prefix")
        self.assertEqual(output["final_answer"], messages[-1]["content"])
        self.assertEqual(messages[-1]["role"], "assistant")

    def test_non_final_run_does_not_invent_a_final_reply(self) -> None:
        tool = AgentAction(
            kind="tool",
            tool_name="read_file",
            tool_arguments={"file_path": "x"},
            tool_call_id="call_0000",
            raw_text='<tool_call>{"name":"read_file","arguments":{"file_path":"x"}}</tool_call>',
        )
        actual = AgentRun(
            messages=[{"role": "user", "content": "Read x"}],
            actions=[tool],
            final_answer=None,
            stop_reason="max_steps",
        )
        _, output, messages = selection_output_documents(
            tool, "measurement-prefix", actual, [SimpleNamespace(prefix_id="actual-prefix")]
        )
        self.assertIsNone(output["final_answer"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(output["generations"][0]["tool_calls"][0]["name"], "read_file")

    def test_missing_run_and_audit_cannot_pass(self) -> None:
        plan = load_selection_plan(GATE, require_frozen=False)
        with tempfile.TemporaryDirectory() as directory:
            with patch("goal_takeover.selection.load_selection_plan", return_value=plan):
                report = summarize_selection(GATE, run_prefix="missing", artifact_root=directory)
        self.assertIsNone(report["selected_model"])
        for candidate in report["candidates"]:
            self.assertEqual(candidate["complete_runs"], 0)
            self.assertEqual(len(candidate["technical_failures"]), 7)
            self.assertFalse(candidate["passes"])

    def test_complete_run_counts_both_labels_and_call_denominators(self) -> None:
        plan = load_selection_plan(GATE, require_frozen=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = []
            for model_index in (1, 2):
                for condition in plan.sample["selection"]["conditions"]:
                    run_id = f"trial-m{model_index}-{condition['condition_id']}"
                    run_dir = root / "runs" / run_id
                    run_dir.mkdir(parents=True)
                    is_ipi = condition["condition_family"] == "ipi"
                    record = {
                        "run_id": run_id,
                        "condition_id": condition["condition_id"],
                        "outcome": {"user_task_success": True, "attack_success": False},
                        "metrics": {
                            "generated_tool_call_attempts": 2,
                            "parsed_tool_calls": 2,
                            "successful_tool_executions": 2,
                            "resource_checks": {"seconds_within_limit": True},
                        },
                        "scores": {"prefix_id": "p"} if is_ipi else None,
                        "prefix_records": [{"prefix_id": "p"}, {"prefix_id": "actual"}],
                    }
                    (run_dir / "run.json").write_text(json.dumps(record), encoding="utf-8")
                    (run_dir / "measurement_output.json").write_text(
                        json.dumps({"generation": {"prefix_id": "p", "raw_text": "probe"}}),
                        encoding="utf-8",
                    )
                    (run_dir / "model_output.json").write_text(
                        json.dumps(
                            {
                                "stop_reason": "final_answer",
                                "final_answer": "done",
                                "generations": [
                                    {
                                        "step_index": 0,
                                        "prefix_id": "actual",
                                        "kind": "final",
                                        "content": "done",
                                        "raw_text": "done",
                                    }
                                ],
                            }
                        ),
                        encoding="utf-8",
                    )
                    (run_dir / "messages.json").write_text(
                        json.dumps([{"role": "assistant", "content": "done", "tool_calls": []}]),
                        encoding="utf-8",
                    )
                    audit.append(
                        {
                            "run_id": run_id,
                            "user_task_success": True,
                            "attack_success": False,
                            "reviewer_id": "blind-reviewer",
                            "reviewed_at": "2026-09-24T00:00:00Z",
                            "evidence": "fixture only",
                        }
                    )
            audit_path = root / "audit.json"
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            with patch("goal_takeover.selection.load_selection_plan", return_value=plan):
                report = summarize_selection(
                    GATE, run_prefix="trial", artifact_root=root, audit_path=audit_path
                )
                first_run = root / "runs" / audit[0]["run_id"] / "model_output.json"
                first_run.unlink()
                incomplete = summarize_selection(
                    GATE, run_prefix="trial", artifact_root=root, audit_path=audit_path
                )
        self.assertEqual(report["candidates"][0]["tool_call_parse"]["denominator"], 14)
        self.assertEqual(report["candidates"][0]["human_agreement"]["attack_success"], 7)
        self.assertTrue(all(candidate["passes"] for candidate in report["candidates"]))
        self.assertEqual(report["selected_model"], "Qwen/Qwen3-8B")
        self.assertFalse(incomplete["candidates"][0]["checks"]["audit_trace_complete"])
        self.assertIsNone(incomplete["selected_model"])


if __name__ == "__main__":
    unittest.main()
