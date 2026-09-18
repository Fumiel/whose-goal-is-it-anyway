"""Small command-line entry points for repository checks."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from goal_takeover.config import (
    ConfigError,
    load_yaml,
    validate_config,
    validate_config_references,
)
from goal_takeover.synthetic import run_synthetic_integration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goal-takeover")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-config", help="validate a YAML config")
    validate.add_argument("path")
    subparsers.add_parser(
        "validate-repository", help="validate every config and JSON Schema declaration"
    )
    synthetic = subparsers.add_parser(
        "synthetic-dry-run", help="write one clearly labelled synthetic run bundle"
    )
    synthetic.add_argument("--artifact-root", default="artifacts")
    synthetic.add_argument("--run-id", required=True)
    return parser


def _validate_repository(root: Path) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise RuntimeError("jsonschema is required; install the project first") from exc

    for path in sorted((root / "configs").glob("**/*.yaml")):
        config = load_yaml(path)
        validate_config(config, source=str(path))
        validate_config_references(config, source=path)
    for path in sorted((root / "data" / "schemas").glob("*.json")):
        with path.open(encoding="utf-8") as stream:
            schema = json.load(stream)
        Draft202012Validator.check_schema(schema)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-config":
        try:
            config = load_yaml(args.path)
            validate_config(config, source=args.path)
            validate_config_references(config, source=args.path)
        except (ConfigError, OSError, RuntimeError) as exc:
            print(f"invalid: {exc}")
            return 1
        print(f"valid: {args.path}")
        return 0
    if args.command == "validate-repository":
        try:
            _validate_repository(Path.cwd())
        except (ConfigError, OSError, RuntimeError, ValueError) as exc:
            print(f"invalid: {exc}")
            return 1
        print("valid: repository declarations")
        return 0
    if args.command == "synthetic-dry-run":
        try:
            result = run_synthetic_integration(args.artifact_root, run_id=args.run_id)
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"failed: {exc}")
            return 1
        print(f"created: {result.run_path}")
        print(f"condition_id: {result.condition_id}")
        print(f"prefix_id: {result.prefix_id}")
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
