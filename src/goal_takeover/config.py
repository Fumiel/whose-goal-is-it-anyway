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

    if config.get("schema_version") != 2:
        raise ConfigError(f"{source}: schema_version must be 2")
    if not isinstance(config.get("status"), str):
        raise ConfigError(f"{source}: status must be a string")

    known_sections = {"model", "domain", "experiment", "probe", "analysis", "selection"}
    if not known_sections.intersection(config):
        raise ConfigError(f"{source}: expected at least one of {', '.join(sorted(known_sections))}")


def validate_config_references(config: dict[str, Any], *, source: str | Path) -> None:
    """Require relative references and verify that their targets exist."""

    source_path = Path(source)
    references = config.get("references", {})
    if not isinstance(references, dict):
        raise ConfigError(f"{source_path}: references must be a mapping")
    for name, raw_path in references.items():
        if not isinstance(raw_path, str) or not raw_path:
            raise ConfigError(f"{source_path}: reference {name} must be a path string")
        reference = Path(raw_path)
        if reference.is_absolute():
            raise ConfigError(f"{source_path}: reference {name} must be relative")
        resolved = (source_path.parent / reference).resolve()
        if not resolved.is_file():
            raise ConfigError(f"{source_path}: reference {name} does not exist: {raw_path}")
