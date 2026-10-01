import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from goal_takeover.datasets.pilot_sample import (
    expand_sample,
    validate_pilot_config,
    validate_sample,
    verify_freeze,
)

ROOT = Path(__file__).parents[1]
TEMPLATE = ROOT / "data/templates/banking_pilot_v1.json"
CONFIG = ROOT / "configs/experiments/banking_pilot_v1.yaml"
FREEZE = ROOT / "configs/experiments/banking_pilot_v1.freeze.json"


class PilotSampleTest(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(TEMPLATE.read_text())
        self.rows = expand_sample(self.spec)

    def test_fixed_counts_stage_order_and_determinism(self):
        summary = validate_sample(self.spec, self.rows)
        self.assertEqual(self.rows, expand_sample(copy.deepcopy(self.spec)))
        self.assertEqual(summary["counts"], {"clean": 6, "ipi": 72, "lexical_control": 12})
        self.assertEqual(summary["task_families"], 4)
        self.assertEqual(summary["connected_components"], 1)
        self.assertTrue(all(row["stage"] == "lead" for row in self.rows[:18]))
        self.assertTrue(all(row["stage"] == "expansion" for row in self.rows[18:]))
        self.assertTrue(all(row["condition_family"] == "clean" for row in self.rows[:6]))
        self.assertEqual(self.rows[0]["user_task_id"], "user_task_14")

    def test_control_semantics_and_unicode_span_alignment(self):
        self.spec["tasks"][0]["benign_vector_text"] = "履歴📄"
        rows = expand_sample(self.spec)
        validate_sample(self.spec, rows)
        for row in rows:
            self.assertEqual(row["split"], "pilot_only")
            self.assertTrue(row["excluded_from_confirmatory_test"])
            span = row["intervention_span_in_vector"]
            if span:
                value = row["injections"][row["injection_vector"]]
                self.assertEqual(value[span["start"] : span["end"]], span["text"])
            if row["condition_family"] == "lexical_control":
                self.assertFalse(row["has_attack"])
                self.assertIsNone(row["attack_goal_id"])
                self.assertIn(row["control_role"], {"quotation", "explanation", "prohibition"})

    def test_manifest_tampering_is_rejected(self):
        for field, value in (
            ("condition_id", "changed"),
            ("group_id", "separate"),
            ("split", "test"),
            ("intervention_span_in_vector", None),
        ):
            rows = copy.deepcopy(self.rows)
            rows[6][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_sample(self.spec, rows)
        with self.assertRaises(ValueError):
            validate_sample(self.spec, self.rows[:-1])

    def test_incomplete_or_duplicate_template_is_rejected(self):
        for change in ("missing_slots", "duplicate_task", "empty_variants", "missing_group_key"):
            spec = copy.deepcopy(self.spec)
            if change == "missing_slots":
                del spec["tasks"][0]["scoring_slots"]
            elif change == "duplicate_task":
                spec["tasks"].append(copy.deepcopy(spec["tasks"][0]))
            elif change == "empty_variants":
                spec["variants"] = []
            else:
                spec["group_keys"].remove("attack_style_id")
            with self.subTest(change=change), self.assertRaises(ValueError):
                expand_sample(spec)

    def test_multi_argument_changes_and_missing_values_are_rejected(self):
        for change in ("incorrect_changes", "missing_argument", "same_tool_violation"):
            spec = copy.deepcopy(self.spec)
            task = next(t for t in spec["tasks"] if t["user_task_id"] == "user_task_3")
            if change == "incorrect_changes":
                task["different_argument_keys"] = ["recipient"]
            elif change == "missing_argument":
                del task["candidate_calls"]["attacker"]["arguments"]["amount"]
            else:
                task["candidate_calls"]["attacker"]["name"] = "update_password"
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_sample(spec, expand_sample(spec))

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML is not installed")
    def test_config_denominators_and_failure_policy(self):
        from goal_takeover.config import load_yaml

        config = load_yaml(CONFIG)
        summary = validate_sample(self.spec, self.rows)
        validate_pilot_config(config, summary)
        for section, key, value in (
            ("lead_to_expansion", "clean_denominator", 5),
            ("final_transition", "minimum_attack_success_count", 1),
            ("retry", "allowed_only", "model_failure"),
        ):
            changed = copy.deepcopy(config)
            changed["stop_and_transition"][section][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_pilot_config(changed, summary)

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML is not installed")
    def test_freeze_checksums_and_pin_coverage(self):
        self.assertEqual(verify_freeze(FREEZE)["conditions"], 90)
        freeze = json.loads(FREEZE.read_text())
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "configs/experiments/banking_pilot_v1.freeze.json"
            target.parent.mkdir(parents=True)
            for reference in freeze["files_sha256"]:
                destination = target.parent / reference
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((FREEZE.parent / reference).read_bytes())
            target.write_text(json.dumps(freeze))
            self.assertEqual(verify_freeze(target)["conditions"], 90)
            manifest = target.parent / freeze["manifest"]
            manifest.write_text(manifest.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                verify_freeze(target)
            del freeze["files_sha256"][freeze["manifest"]]
            target.write_text(json.dumps(freeze))
            with self.assertRaisesRegex(ValueError, "must pin"):
                verify_freeze(target)


if __name__ == "__main__":
    unittest.main()
