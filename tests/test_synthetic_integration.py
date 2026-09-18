import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from goal_takeover.schemas import TokenPositionName
from goal_takeover.synthetic import run_synthetic_integration


class SyntheticIntegrationTest(unittest.TestCase):
    def test_end_to_end_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = run_synthetic_integration(root, run_id="synthetic-001")
            second = run_synthetic_integration(root, run_id="synthetic-002")

            self.assertEqual(first.condition_id, second.condition_id)
            self.assertEqual(first.prefix_id, second.prefix_id)
            self.assertEqual(first.runner_token_ids, first.activation_token_ids)
            self.assertEqual(first.runner_token_ids, first.scorer_token_ids)
            self.assertEqual(
                set(first.positions),
                {
                    TokenPositionName.TPRE,
                    TokenPositionName.TPOST,
                    TokenPositionName.TEND_TOOL,
                    TokenPositionName.TEND_ASSISTANT,
                },
            )
            self.assertLess(
                first.positions[TokenPositionName.TPRE],
                first.positions[TokenPositionName.TPOST],
            )
            self.assertLessEqual(
                first.positions[TokenPositionName.TPOST],
                first.positions[TokenPositionName.TEND_TOOL],
            )
            self.assertLess(
                first.positions[TokenPositionName.TEND_TOOL],
                first.positions[TokenPositionName.TEND_ASSISTANT],
            )
            self.assertIsNone(first.margins.tool_name_margin)

            run_record = json.loads((first.run_path / "run.json").read_text(encoding="utf-8"))
            condition_record = json.loads(
                (first.run_path / "condition.json").read_text(encoding="utf-8")
            )
            self.assertEqual(run_record["condition_id"], first.condition_id)
            self.assertEqual(run_record["prefix_records"][0]["prefix_id"], first.prefix_id)
            self.assertEqual(
                {position["name"] for position in run_record["prefix_records"][0]["positions"]},
                {"Tpre", "Tpost", "Tend_tool", "Tend_assistant"},
            )
            self.assertEqual(
                {artifact["relative_path"] for artifact in run_record["artifacts"]},
                {
                    "resolved_config.json",
                    "condition.json",
                    "messages.json",
                    "tokens.json",
                    "activations/synthetic.json",
                    "scores.json",
                },
            )

            manifest = json.loads((first.run_path / "manifest.json").read_text(encoding="utf-8"))
            for artifact in manifest["artifacts"]:
                content = (first.run_path / artifact["relative_path"]).read_bytes()
                self.assertEqual(artifact["sha256"], hashlib.sha256(content).hexdigest())

            with self.assertRaises(FileExistsError):
                run_synthetic_integration(root, run_id="synthetic-001")

            try:
                from jsonschema import Draft202012Validator
            except ImportError:
                return
            schema_root = Path(__file__).parents[1] / "data" / "schemas"
            run_schema = json.loads((schema_root / "run.schema.json").read_text(encoding="utf-8"))
            condition_schema = json.loads(
                (schema_root / "condition.schema.json").read_text(encoding="utf-8")
            )
            Draft202012Validator(run_schema).validate(run_record)
            Draft202012Validator(condition_schema).validate(condition_record)


if __name__ == "__main__":
    unittest.main()
