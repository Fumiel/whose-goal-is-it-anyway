"""Small command-line entry points for repository checks."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from goal_takeover.config import ConfigError, load_yaml, validate_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goal-takeover")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-config", help="validate a YAML config")
    validate.add_argument("path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-config":
        try:
            config = load_yaml(args.path)
            validate_config(config, source=args.path)
        except (ConfigError, OSError, RuntimeError) as exc:
            print(f"invalid: {exc}")
            return 1
        print(f"valid: {args.path}")
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
