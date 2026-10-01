"""Provenance and immutability checks for derived pilot detail captures."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from goal_takeover.config import ConfigError
from goal_takeover.pilot.detail import (
    EXPECTED_CONDITIONS,
    load_detail_plan,
    run_detail,
    source_prefix,
)
from goal_takeover.schemas import AgentBoundary
from goal_takeover.serialization.prefix import build_serialized_prefix

CONFIG = Path(__file__).parents[1] / "configs/experiments/banking_pilot_detail_v1.yaml"


class PilotDetailTest(unittest.TestCase):
    def test_declared_detail_sample_and_missing_sources_are_immutable(self):
        config, plan = load_detail_plan(CONFIG)
        self.assertEqual(tuple(config["experiment"]["selected_condition_ids"]), EXPECTED_CONDITIONS)
        self.assertEqual(len(plan.conditions), 90)
        with tempfile.TemporaryDirectory() as root:
            with patch("goal_takeover.pilot.detail._git_metadata", return_value=("a" * 40, False)):
                with self.assertRaisesRegex(ConfigError, "run the lead stage first"):
                    run_detail(CONFIG, run_prefix="test-only", artifact_root=root)
                fake_record = {
                    "condition_id": EXPECTED_CONDITIONS[0],
                    "run_id": "test-only-c007-a1",
                    "sample_freeze_sha256": plan.sample_freeze_sha256,
                }
                with (
                    patch("goal_takeover.pilot.detail.load_records", return_value=[fake_record]),
                    patch("goal_takeover.pilot.detail.read_bundle", return_value=fake_record),
                    patch("goal_takeover.pilot.detail.source_prefix", return_value=None),
                ):
                    paths = run_detail(CONFIG, run_prefix="test-only", artifact_root=root)
                self.assertEqual(len(paths), 4)
                self.assertEqual(len(set(paths)), 4)
                for path in paths:
                    detail = json.loads((path / "detail.json").read_text())
                    self.assertEqual(detail["status"], "missing_source")
                    self.assertEqual(
                        detail["source_exists"], detail["condition_id"] == EXPECTED_CONDITIONS[0]
                    )
                    self.assertTrue((path / "manifest.json").exists())
                with (
                    patch("goal_takeover.pilot.detail.load_records", return_value=[fake_record]),
                    patch("goal_takeover.pilot.detail.read_bundle", return_value=fake_record),
                    patch("goal_takeover.pilot.detail.source_prefix", return_value=None),
                    self.assertRaises(FileExistsError),
                ):
                    run_detail(CONFIG, run_prefix="test-only", artifact_root=root)

    def test_source_prefix_checks_exact_ids_offsets_and_revision(self):
        metadata = {
            "tokenizer_revision": "rev",
            "chat_template_sha256": "a" * 64,
            "tool_schema_sha256": "b" * 64,
        }
        prefix = build_serialized_prefix(
            boundary=AgentBoundary.FIRST_TOOL_TO_ASSISTANT,
            text="abc",
            token_ids=[10, 11],
            offset_mapping=[(0, 1), (1, 3)],
            metadata=metadata,
        )
        row = {
            "scope": "fixed_prefix_diagnostic",
            "step_index": 1,
            "boundary": prefix.boundary.value,
            "text": prefix.text,
            "serialized_text_sha256": hashlib.sha256(prefix.text.encode()).hexdigest(),
            "token_ids": list(prefix.token_ids),
            "offsets": [
                {"token_index": i, "token_id": token, "start": start, "end": end}
                for i, (token, start, end) in enumerate(((10, 0, 1), (11, 1, 3)))
            ],
            "metadata": metadata,
            "prefix_id": prefix.prefix_id,
            "boundary_token_index": 1,
            "boundary_token_id": 11,
        }
        record = {
            "condition_id": EXPECTED_CONDITIONS[0],
            "diagnostic": {"measurement_index": 1},
            "measurements": [
                {
                    "index": 1,
                    "scope": "fixed_prefix_diagnostic",
                    "prefix_id": prefix.prefix_id,
                    "scores": {"finite": True},
                }
            ],
            "model": {"name": "test-model", "revision": "rev"},
            "tokenizer": {"name": "test-model", "revision": "rev"},
        }
        resolved = {
            "model_config": {
                "model": {"name": "test-model", "revision": "rev", "tokenizer_revision": "rev"}
            },
            "runtime_freeze": {
                "chat_template_sha256": "a" * 64,
                "tool_schema_sha256": "b" * 64,
            },
        }
        with tempfile.TemporaryDirectory() as root:
            bundle = Path(root)
            (bundle / "prefixes.json").write_text(json.dumps([row]))
            (bundle / "resolved_config.json").write_text(json.dumps(resolved))
            self.assertEqual(source_prefix(bundle, record, EXPECTED_CONDITIONS[0]), prefix)
            bad = copy.deepcopy(row)
            bad["offsets"][1]["token_id"] = 12
            (bundle / "prefixes.json").write_text(json.dumps([bad]))
            with self.assertRaisesRegex(ConfigError, "offset alignment"):
                source_prefix(bundle, record, EXPECTED_CONDITIONS[0])
            (bundle / "prefixes.json").write_text(json.dumps([row]))
            resolved["model_config"]["model"]["tokenizer_revision"] = "other"
            (bundle / "resolved_config.json").write_text(json.dumps(resolved))
            with self.assertRaisesRegex(ConfigError, "revision|serialization"):
                source_prefix(bundle, record, EXPECTED_CONDITIONS[0])


if __name__ == "__main__":
    unittest.main()
