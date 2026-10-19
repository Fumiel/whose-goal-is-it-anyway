"""Phase 2 source-role alignment and outcome rules, without model inference."""

import unittest
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory

from goal_takeover.agent.runner import AgentAction
from goal_takeover.environments.two_document_payment import create_session
from goal_takeover.evaluation.tool_logprob import (
    CandidateSequenceScore,
    compare_candidate_sequences,
)
from goal_takeover.instrumentation.capture import ActivationRecord
from goal_takeover.phase2.two_document import (
    load_plan,
    outcome_selector,
    position_selector,
    runtime_capture,
    verify_gpu_report,
)
from goal_takeover.pilot.evaluation import RecordingSession, state_document
from goal_takeover.pilot.measurement import score_slots
from goal_takeover.pilot.runner import execute_condition
from goal_takeover.schemas import AgentBoundary
from goal_takeover.serialization.prefix import build_serialized_prefix

CONFIG = Path(__file__).parents[1] / "configs/experiments/phase2_two_document_initial_v1.json"
HAS_AGENTDOJO = find_spec("agentdojo") is not None


class SyntheticTensor:
    dtype = "test_only_float32"

    def __init__(self, count):
        self.shape = (1, count, 2)

    def isfinite(self):
        return type("Finite", (), {"all": lambda self: True})()


class SyntheticScorer:
    def score_pair(self, prefix, *, legitimate, attack, argument_slot):
        def score(call, value):
            slot = call.argument_spans[argument_slot]
            name = call.tool_name_span
            return CandidateSequenceScore(
                call.text,
                tuple(map(ord, call.text)),
                (value,) * len(call.text),
                tuple(range(slot.start, slot.end)),
                tuple(range(name.start, name.end)),
            )

        left, right = score(legitimate, -1.0), score(attack, -2.0)
        return left, right, compare_candidate_sequences(right, left)


class SyntheticBackend:
    def __init__(self, session, condition, spec):
        self.prefixes = []
        self.generations = []
        calls = [spec["calls"]["read_purchase_order"], spec["calls"]["read_payee_registry"]]
        selected = "attacker" if condition["variant_id"] == "user_instruction" else "legitimate"
        calls.append(spec["calls"][selected])
        self.actions = [
            AgentAction(
                kind="tool",
                tool_name=call["name"],
                tool_arguments=call["arguments"],
                raw_text="synthetic tool action",
            )
            for call in calls
        ]
        self.actions.append(
            AgentAction(kind="final", content="synthetic done", raw_text="synthetic done")
        )

    def serialize(self, messages):
        text = ""
        for message in messages:
            if message["role"] == "tool":
                text += (
                    "<|im_start|>user\n<tool_response>\n"
                    + message["content"]
                    + "\n</tool_response><|im_end|>\n"
                )
            else:
                text += f"<|im_start|>{message['role']}\n{message['content']}<|im_end|>\n"
        text += "<|im_start|>assistant\n<think>\n\n</think>\n\n"
        tool_count = sum(message["role"] == "tool" for message in messages)
        boundary = (
            AgentBoundary.USER_TO_ASSISTANT
            if tool_count == 0
            else AgentBoundary.FIRST_TOOL_TO_ASSISTANT
            if tool_count == 1
            else AgentBoundary.LATER_TOOL_TO_ASSISTANT
        )
        return build_serialized_prefix(
            boundary=boundary,
            text=text,
            token_ids=list(map(ord, text)),
            offset_mapping=[(index, index + 1) for index in range(len(text))],
            metadata={"synthetic": True, "tool_schema_sha256": "b" * 64},
        )

    def next_action_from_prefix(self, prefix):
        self.prefixes.append(prefix)
        action = self.actions.pop(0)
        self.generations.append(
            {"prefix_id": prefix.prefix_id, "token_ids": [1], "raw_text": action.raw_text}
        )
        return action


class SyntheticServices:
    runtime_report = {"synthetic": True, "research_result": False}

    def __init__(self, plan):
        self.plan = plan

    def start_condition(self):
        pass

    def check_memory(self):
        return 0

    def session(self, condition):
        session, _ = create_session(self.plan.evaluator, condition["variant_id"])
        session.condition = condition
        return session

    def backend(self, session):
        return SyntheticBackend(session, session.condition, self.plan.evaluator)

    def capture(self, prefix, positions, ranges, *, full_attention):
        record = ActivationRecord(
            prefix.prefix_id,
            prefix.token_ids,
            positions,
            {"layer.0": SyntheticTensor(len(positions))},
        )
        return (
            record,
            {"prefix_id": prefix.prefix_id, "prefix_token_ids": list(prefix.token_ids)},
            None,
        )

    def activation_bytes(self, record):
        return b"synthetic activation placeholder; not research data"

    def score(self, prefix, condition):
        return score_slots(SyntheticScorer(), prefix, condition)


class TwoDocumentPhase2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan, cls.design = load_plan(CONFIG)

    def test_frozen_conditions_stay_in_one_train_component(self) -> None:
        self.assertEqual(len(self.plan.conditions), 5)
        self.assertEqual({row["split"] for row in self.plan.conditions}, {"train"})
        self.assertEqual(len({row["group_id"] for row in self.plan.conditions}), 1)
        self.assertEqual(
            [row["variant_id"] for row in self.plan.conditions],
            ["user_instruction", "tool_output", "quotation", "explanation", "prohibition"],
        )

    @unittest.skipUnless(HAS_AGENTDOJO, "AgentDojo research dependency is unavailable")
    def test_authorized_user_alternative_is_not_an_attack_outcome(self) -> None:
        outcome = self._evaluate("user_instruction", "attacker")
        self.assertTrue(outcome["native_user_task_success"])
        self.assertTrue(outcome["native_attack_success"])
        self.assertTrue(outcome["strict_candidate_attack_occurred"])
        self.assertTrue(outcome["automatic_strict_user_task_success"])
        self.assertTrue(outcome["authorized_alternative_control"])
        self.assertIsNone(outcome["group"])
        self.assertFalse(outcome["quarantined_contradiction"])

    @unittest.skipUnless(HAS_AGENTDOJO, "AgentDojo research dependency is unavailable")
    def test_tool_override_and_quotation_keep_distinct_labels(self) -> None:
        injection = self._evaluate("tool_output", "attacker")
        quotation = self._evaluate("quotation", "attacker")
        self.assertEqual(injection["group"], "D")
        self.assertFalse(injection["native_user_task_success"])
        self.assertFalse(injection["quarantined_contradiction"])
        self.assertIsNone(quotation["group"])
        self.assertTrue(quotation["quarantined_contradiction"])
        self.assertTrue(quotation["strict_candidate_attack_occurred"])

    def test_user_text_aligns_at_user_boundary_only(self) -> None:
        condition = self.plan.conditions[0]
        user = condition["user_instruction"]
        text = f"<user>{user}</user><assistant>"
        prefix = build_serialized_prefix(
            boundary=AgentBoundary.USER_TO_ASSISTANT,
            text=text,
            token_ids=list(range(1, len(text) + 1)),
            offset_mapping=[(i, i + 1) for i in range(len(text))],
            metadata={"fixture": "character_tokens"},
        )
        positions, selected, ranges = position_selector(
            prefix,
            [{"role": "user", "content": user}],
            condition,
            {"ipi_window": {"left": 16, "right": 16}},
        )
        self.assertTrue(positions["exposed"])
        self.assertEqual(
            {row["name"] for row in positions["positions"]},
            {"Tpre", "Tpost", "Tend_assistant"},
        )
        self.assertEqual(positions["missing_positions"], ["Tend_tool"])
        self.assertTrue(ranges["intervention"])
        self.assertIn(ranges["intervention"][-1], selected)

    @unittest.skipUnless(HAS_AGENTDOJO, "AgentDojo research dependency is unavailable")
    def test_reversed_document_reads_fail_strict_success(self) -> None:
        outcome = self._evaluate("tool_output", "legitimate", reverse_reads=True)
        self.assertFalse(outcome["native_user_task_success"])
        self.assertFalse(outcome["automatic_strict_user_task_success"])

    def test_gpu_report_requires_same_commit_and_frozen_ceiling(self) -> None:
        report = {
            "status": "engineering_gpu_preflight_passed",
            "research_result": False,
            "design_freeze_sha256": self.plan.sample_freeze_sha256,
            "git_commit": "test-only-commit",
            "git_dirty": False,
            "chat_template_sha256": self.design["model_snapshot"]["chat_template_sha256_expected"],
            "tool_schema_sha256": "b" * 64,
            "conditions": [
                {
                    "variant_id": role,
                    "candidate_scored": True,
                    "peak_gpu_memory_bytes": 10 * 2**30,
                    "residual_bytes": 25_000_000,
                    "elapsed_seconds": 60.0,
                }
                for role in ("user_instruction", "explanation")
            ],
        }
        verify_gpu_report(self.plan, self.design, report, expected_git_commit="test-only-commit")
        with self.assertRaisesRegex(ValueError, "does not match frozen design"):
            verify_gpu_report(self.plan, self.design, report, expected_git_commit="other")
        report["conditions"][0]["peak_gpu_memory_bytes"] = 13 * 2**30
        with self.assertRaisesRegex(ValueError, "exceeded"):
            verify_gpu_report(
                self.plan, self.design, report, expected_git_commit="test-only-commit"
            )

    @unittest.skipUnless(HAS_AGENTDOJO, "AgentDojo research dependency is unavailable")
    def test_synthetic_runner_writes_phase2_schema_with_actual_prefix(self) -> None:
        runtime = {
            "capture": runtime_capture(self.design),
            "tool_schema_sha256": "b" * 64,
        }

        def outcome(condition, native, initial, final, events):
            return outcome_selector(self.plan.evaluator, condition, native, initial, final, events)

        schema = CONFIG.parents[2] / "data/schemas/phase2_run.schema.json"
        for condition in (self.plan.conditions[0], self.plan.conditions[1]):
            with self.subTest(variant_id=condition["variant_id"]), TemporaryDirectory() as root:
                path, record = execute_condition(
                    self.plan,
                    runtime,
                    SyntheticServices(self.plan),
                    condition=condition,
                    artifact_root=root,
                    run_id=f"synthetic-{condition['variant_id']}",
                    runtime_sha256="a" * 64,
                    position_selector=position_selector,
                    outcome_selector=outcome,
                    run_schema_path=schema,
                )
                self.assertEqual(record["status"], "completed")
                self.assertEqual(record["split"], "train")
                self.assertTrue(record["actual_exposed_scored"])
                self.assertEqual(record["diagnostic"], None)
                self.assertTrue((path / "run.json").exists())

    def _evaluate(self, variant_id: str, recipient: str, *, reverse_reads: bool = False) -> dict:
        spec = self.plan.evaluator
        session, _ = create_session(spec, variant_id)
        recorder = RecordingSession(session)
        initial = state_document(session.environment)
        calls = [spec["calls"]["read_purchase_order"], spec["calls"]["read_payee_registry"]]
        if reverse_reads:
            calls.reverse()
        calls.append(spec["calls"][recipient])
        for call in calls:
            result = recorder.execute(call["name"], call["arguments"])
            self.assertIsNone(result.error)
        final = state_document(session.environment)
        condition = next(row for row in self.plan.conditions if row["variant_id"] == variant_id)
        return outcome_selector(
            spec,
            condition,
            session.evaluate(None),
            initial,
            final,
            recorder.events,
        )


if __name__ == "__main__":
    unittest.main()
