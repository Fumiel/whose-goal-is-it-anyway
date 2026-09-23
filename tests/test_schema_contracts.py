import json
import unittest
from pathlib import Path


class SchemaContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_root = Path(__file__).parents[1] / "data" / "schemas"

    def test_run_schema_uses_current_boundaries_and_positions(self) -> None:
        schema = json.loads((self.schema_root / "run.schema.json").read_text(encoding="utf-8"))
        prefix = schema["$defs"]["prefixRecord"]
        position = schema["$defs"]["position"]
        self.assertEqual(
            prefix["properties"]["boundary"]["enum"],
            ["user_to_assistant", "first_tool_to_assistant", "later_tool_to_assistant"],
        )
        self.assertEqual(
            position["properties"]["name"]["enum"],
            ["Tpre", "Tpost", "Tend_tool", "Tend_assistant"],
        )

    def test_all_json_schemas_are_well_formed_when_jsonschema_is_available(self) -> None:
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is not installed")

        for path in sorted(self.schema_root.glob("*.json")):
            with self.subTest(path=path.name):
                Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))

    def test_selection_metrics_and_boundary_ids_match_run_schema(self) -> None:
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is not installed")
        schema = json.loads((self.schema_root / "run.schema.json").read_text(encoding="utf-8"))
        metrics = {
            "generated_tool_call_attempts": 2,
            "parsed_tool_calls": 2,
            "executed_tool_calls": 2,
            "successful_tool_executions": 2,
            "no_call": False,
            "elapsed_seconds": 1.0,
            "peak_gpu_memory_bytes": 1024,
            "bundle_bytes": 2048,
            "resource_checks": {
                "seconds_within_limit": True,
                "gpu_memory_within_limit": True,
                "storage_within_limit": True,
            },
        }
        Draft202012Validator(schema["properties"]["metrics"]).validate(metrics)
        prefix_schema = {"$defs": schema["$defs"], "$ref": "#/$defs/prefixRecord"}
        Draft202012Validator(prefix_schema).validate(
            {
                "boundary": "user_to_assistant",
                "prefix_id": "p",
                "serialized_text_sha256": "a" * 64,
                "token_ids": [42],
                "positions": [],
                "boundary_token_index": 0,
                "boundary_token_id": 42,
            }
        )


if __name__ == "__main__":
    unittest.main()
