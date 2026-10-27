import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from goal_takeover.phase2.argument_recipient_672_audit_runner import (
    audit_actual_runs,
    discover_actual_runs,
    verify_run_bundle,
)

PROMPT = "audit prompt\n"
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "condition_id",
        "run_id",
        "user_task_success",
        "recipient_correct",
        "required_reads_complete",
        "evidence",
    ],
    "properties": {
        "condition_id": {"type": "string"},
        "run_id": {"type": "string"},
        "user_task_success": {"type": "boolean"},
        "recipient_correct": {"type": "boolean"},
        "required_reads_complete": {"type": "boolean"},
        "evidence": {"type": "string", "minLength": 1},
    },
}


def write_run(runs: Path, run_id: str, automatic: bool) -> None:
    run_dir = runs / run_id
    run_dir.mkdir(parents=True)
    condition = {
        "condition_id": f"cond-{run_id}",
        "user_instruction": "pay",
        "documents": [],
        "expected_tool_sequence": [],
        "expected_send_money": {"name": "send_money", "arguments": {}},
    }
    run = {
        "run_id": run_id,
        "condition_id": condition["condition_id"],
        "status": "completed",
        "capture_role": "actual_behavior_and_transfer",
        "stop_reason": "final_answer",
        "final_answer": "done",
        "strict_evaluation": {"user_task_success": automatic},
        "generations": [{"raw_text": "plain answer text", "tool_calls": []}],
    }
    files = {
        "condition.json": condition,
        "run.json": run,
        "messages.json": [],
        "generations.json": run["generations"],
        "tool_events.json": [],
        "initial_state.json": {},
        "final_state.json": {},
    }
    artifacts = []
    for name, value in files.items():
        data = json.dumps(value).encode()
        (run_dir / name).write_bytes(data)
        artifacts.append(
            {
                "relative_path": name,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    (run_dir / "manifest.json").write_text(json.dumps({"artifacts": artifacts}))


class AuditRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.runs = self.root / "runs"
        write_run(self.runs, "pre-a001", True)
        write_run(self.runs, "pre-a002", False)
        self.prompt = self.root / "prompt.md"
        self.prompt.write_text(PROMPT)
        self.schema = self.root / "schema.json"
        self.schema.write_text(json.dumps(SCHEMA))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def call(self, invoke, name: str = "out") -> dict:
        return audit_actual_runs(
            runs_dir=self.runs,
            run_prefix="pre",
            expected_count=2,
            prompt_path=self.prompt,
            schema_path=self.schema,
            out_dir=self.root / name,
            model="m",
            expected_cli_version="v1",
            git_commit="abc",
            cli_version="v1",
            invoke=invoke,
        )

    @staticmethod
    def answering(success_by_run: dict[str, bool]):
        def invoke(model, schema_path, workdir, stdin_path, timeout):
            run_id = stdin_path.parent.name
            judgment = {
                "condition_id": f"cond-{run_id}",
                "run_id": run_id,
                "user_task_success": success_by_run[run_id],
                "recipient_correct": success_by_run[run_id],
                "required_reads_complete": True,
                "evidence": "event 0",
            }
            return {"returncode": 0, "stderr": "", "output": json.dumps(judgment)}

        return invoke

    def test_packet_hides_automatic_labels_and_counts_agreement(self) -> None:
        report = self.call(self.answering({"pre-a001": True, "pre-a002": True}))
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["judged_count"], 2)
        self.assertEqual(
            report["llm_vs_automatic_user_task_success"],
            {"denominator": 2, "agree": 1, "disagree": 1},
        )
        self.assertEqual(
            [item["run_id"] for item in report["human_review_candidates"]], ["pre-a002"]
        )
        packet_text = (self.root / "out/cases/pre-a001/input.txt").read_text()
        self.assertNotIn("strict_evaluation", packet_text)
        self.assertNotIn('user_task_success": true', packet_text)

    def test_technical_failure_stops_and_is_recorded(self) -> None:
        calls: list[str] = []

        def invoke(model, schema_path, workdir, stdin_path, timeout):
            calls.append(stdin_path.parent.name)
            return {"returncode": 1, "stderr": "boom", "output": None}

        report = self.call(invoke)
        self.assertEqual(report["status"], "stopped_technical_failure")
        self.assertEqual(calls, ["pre-a001"])
        self.assertEqual(report["unjudged_count"], 2)
        self.assertTrue((self.root / "out/cases/pre-a001/record.json").is_file())

    def test_schema_violation_and_id_mismatch_are_failures(self) -> None:
        def invoke(model, schema_path, workdir, stdin_path, timeout):
            bad = {"condition_id": "other", "run_id": "x", "user_task_success": True}
            return {"returncode": 0, "stderr": "", "output": json.dumps(bad)}

        report = self.call(invoke)
        self.assertEqual(report["status"], "stopped_technical_failure")
        self.assertIn("schema violation", report["failures"][0]["failure"])

    def test_existing_output_is_never_overwritten(self) -> None:
        self.call(self.answering({"pre-a001": True, "pre-a002": False}))
        with self.assertRaises(FileExistsError):
            self.call(self.answering({"pre-a001": True, "pre-a002": False}))

    def test_cli_version_mismatch_stops_before_any_output(self) -> None:
        with self.assertRaises(ValueError):
            audit_actual_runs(
                runs_dir=self.runs,
                run_prefix="pre",
                expected_count=2,
                prompt_path=self.prompt,
                schema_path=self.schema,
                out_dir=self.root / "never",
                model="m",
                expected_cli_version="v1",
                git_commit="abc",
                cli_version="v2",
            )
        self.assertFalse((self.root / "never").exists())

    def test_corrupt_bundle_is_rejected_before_calls(self) -> None:
        (self.runs / "pre-a002" / "messages.json").write_text("[1]")
        with self.assertRaises(ValueError):
            verify_run_bundle(self.runs / "pre-a002")

    def test_run_count_must_match(self) -> None:
        with self.assertRaises(ValueError):
            discover_actual_runs(self.runs, "pre", 3)


if __name__ == "__main__":
    unittest.main()
