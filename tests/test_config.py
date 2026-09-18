import unittest

from goal_takeover.config import ConfigError, validate_config


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


if __name__ == "__main__":
    unittest.main()
