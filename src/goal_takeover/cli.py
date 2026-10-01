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
    gpu = subparsers.add_parser("gpu-preflight", help="verify the CUDA research runtime")
    gpu.add_argument("--json", action="store_true", dest="as_json")
    dojo = subparsers.add_parser(
        "agentdojo-preflight", help="verify pinned AgentDojo fixtures without loading a model"
    )
    dojo.add_argument("config")
    shakedown = subparsers.add_parser(
        "agentdojo-shakedown", help="run the authorized three-fixture GPU shakedown"
    )
    shakedown.add_argument("config")
    shakedown.add_argument("--model-config", required=True)
    shakedown.add_argument("--run-prefix", required=True)
    selection_preflight = subparsers.add_parser(
        "selection-preflight", help="verify all pinned model-selection conditions without a model"
    )
    selection_preflight.add_argument("gate")
    selection = subparsers.add_parser(
        "agentdojo-selection", help="run the frozen seven-condition sample for both candidates"
    )
    selection.add_argument("gate")
    selection.add_argument("--run-prefix", required=True)
    selection.add_argument("--artifact-root", default="artifacts")
    report = subparsers.add_parser("selection-report", help="summarize the frozen selection gate")
    report.add_argument("gate")
    report.add_argument("--run-prefix", required=True)
    report.add_argument("--artifact-root", default="artifacts")
    report.add_argument("--audit")
    pilot_preflight = subparsers.add_parser(
        "pilot-preflight", help="check all frozen pilot conditions without model inference"
    )
    pilot_preflight.add_argument("config")
    pilot = subparsers.add_parser("agentdojo-pilot", help="run one frozen, audited pilot stage")
    pilot.add_argument("config")
    pilot.add_argument("--runtime-freeze", required=True)
    pilot.add_argument("--run-prefix", required=True)
    pilot.add_argument("--stage", choices=("lead", "expansion"), default="lead")
    pilot.add_argument("--artifact-root")
    pilot.add_argument("--audit")
    for name in ("pilot-report", "pilot-audit-template"):
        command = subparsers.add_parser(name, help="derive pilot gate report or blank audit form")
        command.add_argument("config")
        command.add_argument("--run-prefix", required=True)
        command.add_argument("--artifact-root", default="artifacts")
        command.add_argument("--audit")
    return parser


def _agentdojo_preflight(config_path: str) -> list[dict[str, object]]:
    from goal_takeover.environments.agentdojo import AgentDojoSession

    config = load_yaml(config_path)
    experiment = config["experiment"]
    fixtures = config.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 3:
        raise ConfigError("pre-gate shakedown must contain exactly three fixtures")
    results = []
    for fixture in fixtures:
        session = AgentDojoSession.create(
            benchmark_version=experiment["benchmark_version"],
            suite_name=experiment["suite"],
            user_task_id=fixture["user_task_id"],
            injection_task_id=fixture.get("injection_task_id"),
            injections=fixture.get("injections", {}),
        )
        legitimate, attack = session.ground_truth_calls()
        if not legitimate:
            raise ConfigError(f"{fixture['fixture_id']}: no legitimate ground truth")
        if fixture.get("primary_argument_slot"):
            if not attack:
                raise ConfigError(f"{fixture['fixture_id']}: no attack ground truth")
            legitimate_call = legitimate[int(fixture["legitimate_call_index"])]
            attack_call = attack[int(fixture["attack_call_index"])]
            if legitimate_call.function != attack_call.function:
                raise ConfigError(f"{fixture['fixture_id']}: calls do not use the same tool")
        results.append(
            {
                "fixture_id": fixture["fixture_id"],
                "tools": len(session.tool_schemas),
                "legitimate_calls": len(legitimate),
                "attack_calls": len(attack),
            }
        )
    return results


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
    from goal_takeover.datasets.pilot_sample import verify_freeze

    for path in sorted((root / "configs" / "experiments").glob("*.freeze.json")):
        verify_freeze(path)


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
    if args.command == "gpu-preflight":
        try:
            from goal_takeover.runtime import gpu_runtime_report

            report = gpu_runtime_report()
        except RuntimeError as exc:
            print(f"failed: {exc}")
            return 1
        if args.as_json:
            print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            for key, value in report.items():
                print(f"{key}: {value}")
        return 0
    if args.command == "agentdojo-preflight":
        try:
            results = _agentdojo_preflight(args.config)
        except (ConfigError, KeyError, OSError, RuntimeError, ValueError) as exc:
            print(f"failed: {exc}")
            return 1
        for result in results:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        print("valid: pinned AgentDojo shakedown fixtures")
        return 0
    if args.command == "agentdojo-shakedown":
        progress = None
        failure_writer = None
        try:
            from goal_takeover.shakedown import (
                ShakedownProgress,
                run_agentdojo_shakedown,
                write_shakedown_failure,
            )

            failure_writer = write_shakedown_failure
            progress = ShakedownProgress()
            result = run_agentdojo_shakedown(
                args.config, args.model_config, run_prefix=args.run_prefix, progress=progress
            )
        except (KeyError, OSError, RuntimeError, ValueError) as exc:
            print(f"failed: {exc}")
            if failure_writer is None:
                return 1
            try:
                failure_path = failure_writer(
                    args.config,
                    run_prefix=args.run_prefix,
                    stage=progress.stage if progress is not None else "initialization",
                    error=exc,
                    fixture_id=progress.fixture_id if progress is not None else None,
                )
            except (KeyError, OSError, RuntimeError, ValueError):
                pass
            else:
                print(f"recorded: {failure_path}")
            return 1
        print(f"model: {result.model_name}@{result.model_revision}")
        for path in result.run_paths:
            print(f"created: {path}")
        return 0
    if args.command == "selection-preflight":
        try:
            from goal_takeover.selection import load_selection_plan, preflight_selection

            plan = load_selection_plan(args.gate, require_frozen=False)
            reports = preflight_selection(plan)
        except (ConfigError, KeyError, OSError, RuntimeError, ValueError) as exc:
            print(f"failed: {exc}")
            return 1
        for report in reports:
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        print("valid: seven pinned AgentDojo selection conditions")
        return 0
    if args.command == "agentdojo-selection":
        try:
            from goal_takeover.selection import run_selection

            paths = run_selection(
                args.gate, run_prefix=args.run_prefix, artifact_root=args.artifact_root
            )
        except (ConfigError, KeyError, OSError, RuntimeError, ValueError) as exc:
            print(f"failed: {exc}")
            return 1
        for path in paths:
            print(f"created: {path}")
        return 0
    if args.command == "selection-report":
        try:
            from goal_takeover.selection import summarize_selection

            report = summarize_selection(
                args.gate,
                run_prefix=args.run_prefix,
                artifact_root=args.artifact_root,
                audit_path=args.audit,
            )
        except (ConfigError, KeyError, OSError, RuntimeError, ValueError) as exc:
            print(f"failed: {exc}")
            return 1
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if args.command in {
        "pilot-preflight",
        "agentdojo-pilot",
        "pilot-report",
        "pilot-audit-template",
    }:
        try:
            from goal_takeover.pilot.plan import load_pilot_plan
            from goal_takeover.pilot.preflight import preflight_pilot
            from goal_takeover.pilot.report import audit_template, load_records, summarize_pilot
            from goal_takeover.pilot.runner import run_pilot

            if args.command == "agentdojo-pilot":
                paths = run_pilot(
                    args.config,
                    args.runtime_freeze,
                    run_prefix=args.run_prefix,
                    stage=args.stage,
                    artifact_root=args.artifact_root,
                    audit_path=args.audit,
                )
                for path in paths:
                    print(f"created: {path}")
                return 0
            plan = load_pilot_plan(args.config)
            if args.command == "pilot-preflight":
                result = preflight_pilot(plan)
            else:
                records = load_records(plan, args.artifact_root, args.run_prefix)
                if args.command == "pilot-audit-template":
                    result = audit_template(plan, records)
                else:
                    audit = json.loads(Path(args.audit).read_text()) if args.audit else None
                    result = summarize_pilot(plan, records, audit=audit)
        except (ConfigError, KeyError, OSError, RuntimeError, ValueError) as exc:
            print(f"failed: {exc}")
            return 1
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
