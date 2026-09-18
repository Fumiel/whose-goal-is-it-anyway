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


if __name__ == "__main__":
    unittest.main()
