"""Configuration loading and lightweight structural validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a configuration is missing required structure."""


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping.

    PyYAML is imported lazily so dependency-free unit tests can still run before
    the research environment is installed.
    """

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise RuntimeError("PyYAML is required; install the project first") from exc

    config_path = Path(path)
    with config_path.open(encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise ConfigError(f"{config_path} must contain a YAML mapping")
    return value


def validate_config(config: dict[str, Any], *, source: str = "<memory>") -> None:
    """Check common fields without pretending to validate model-specific details."""

    if config.get("schema_version") != 1:
        raise ConfigError(f"{source}: schema_version must be 1")
    if not isinstance(config.get("status"), str):
        raise ConfigError(f"{source}: status must be a string")

    known_sections = {"model", "domain", "experiment", "probe"}
    if not known_sections.intersection(config):
        raise ConfigError(
            f"{source}: expected at least one of {', '.join(sorted(known_sections))}"
        )
