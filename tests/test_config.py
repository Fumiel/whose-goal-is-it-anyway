import importlib.util
import tempfile
import unittest
from pathlib import Path

from goal_takeover.cli import _validate_config_path
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

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML is not installed")
    def test_recipient_config_uses_frozen_schema_and_repository_references(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "configs/experiments/phase2_argument_recipient_672_v1.yaml"
            path.parent.mkdir(parents=True)
            declaration = root / "data/declaration.json"
            declaration.parent.mkdir()
            declaration.write_text("{}")
            path.write_text(
                "schema_version: 1\n"
                "status: frozen\n"
                "model: {}\n"
                "decoding: {}\n"
                "references:\n"
                "  declaration: data/declaration.json\n"
                "  runtime_freeze: artifacts/runtime.freeze.json\n"
            )
            _validate_config_path(path, root)
            declaration.unlink()
            with self.assertRaisesRegex(ConfigError, "declaration does not exist"):
                _validate_config_path(path, root)


if __name__ == "__main__":
    unittest.main()
