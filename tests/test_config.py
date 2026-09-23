import importlib.util
import unittest
from pathlib import Path

from goal_takeover.config import (
    ConfigError,
    load_yaml,
    validate_config,
    validate_config_references,
)


class ConfigTest(unittest.TestCase):
    def test_current_schema_version_is_accepted(self) -> None:
        validate_config(
            {"schema_version": 2, "status": "synthetic_example_only", "experiment": {}},
            source="test",
        )

    def test_stale_schema_version_is_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            validate_config(
                {"schema_version": 1, "status": "draft", "experiment": {}},
                source="test",
            )

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML is not installed")
    def test_selection_gate_references_resolve(self) -> None:
        path = Path(__file__).parents[1] / "configs/selection/integration_gate.yaml"
        config = load_yaml(path)
        validate_config(config, source=str(path))
        validate_config_references(config, source=path)
        self.assertEqual(config["status"], "frozen")
        self.assertEqual(
            config["selection"]["sample_manifest"],
            "banking_native_selection_sample.yaml",
        )


if __name__ == "__main__":
    unittest.main()
