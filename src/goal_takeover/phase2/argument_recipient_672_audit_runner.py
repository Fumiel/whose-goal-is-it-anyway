"""Run the declared Codex audit over completed actual recipient runs."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from goal_takeover.phase2.argument_recipient_672_audit_packet import build_audit_packet
from goal_takeover.phase2.argument_recipient_672_audit_triage import human_review_reasons

AUDIT_RUNNER_VERSION = "argument_recipient_672_codex_audit_runner_v1"
LABELS = ("user_task_success", "recipient_correct", "required_reads_complete")

Invoke = Callable[[str, Path, Path, Path, float], dict[str, Any]]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def _load(path: Path) -> Any:
    return json.loads(path.read_text())


def discover_actual_runs(runs_dir: Path, run_prefix: str, expected_count: int) -> list[Path]:
    """Order by run ID so the audit never depends on an outcome."""
    runs = sorted(
        path
        for path in runs_dir.glob(f"{run_prefix}-a[0-9][0-9][0-9]")
        if path.is_dir()
    )
    if len(runs) != expected_count:
        raise ValueError(f"expected {expected_count} actual runs, found {len(runs)}")
    return runs


def verify_run_bundle(run_dir: Path) -> dict[str, Any]:
    """Check manifest checksums and completion before any model call."""
    manifest = _load(run_dir / "manifest.json")
    for artifact in manifest["artifacts"]:
        path = run_dir / artifact["relative_path"]
        if not path.is_file() or path.stat().st_size != artifact["bytes"]:
            raise ValueError(f"{run_dir.name}: missing or resized {artifact['relative_path']}")
        if _sha256_file(path) != artifact["sha256"]:
            raise ValueError(f"{run_dir.name}: checksum mismatch {artifact['relative_path']}")
    run = _load(run_dir / "run.json")
    if run.get("status") != "completed" or run.get("run_id") != run_dir.name:
        raise ValueError(f"{run_dir.name}: run is not a completed matching bundle")
    return run


def packet_for_run(run_dir: Path, run: dict[str, Any]) -> dict[str, Any]:
    return build_audit_packet(
        run,
        _load(run_dir / "condition.json"),
        messages=_load(run_dir / "messages.json"),
        generations=_load(run_dir / "generations.json"),
        tool_events=_load(run_dir / "tool_events.json"),
        initial_state=_load(run_dir / "initial_state.json"),
        final_state=_load(run_dir / "final_state.json"),
    )


def codex_invoke(
    model: str, schema_path: Path, workdir: Path, stdin_path: Path, timeout: float
) -> dict[str, Any]:
    """Call `codex exec` read-only in an empty directory; the prompt arrives on stdin."""
    output_path = workdir / "last_message.json"
    command = [
        "codex",
        "exec",
        "--model",
        model,
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--ephemeral",
        "--ignore-rules",
        "--color",
        "never",
        "--cd",
        str(workdir),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
        "-",
    ]
    with stdin_path.open("rb") as stdin:
        completed = subprocess.run(  # noqa: S603
            command, stdin=stdin, capture_output=True, timeout=timeout, check=False
        )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stderr": completed.stderr.decode("utf-8", errors="replace"),
        "output": output_path.read_text() if output_path.is_file() else None,
    }


def codex_cli_version() -> str:
    return subprocess.run(  # noqa: S603
        ["codex", "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()


def _validate_judgment(judgment: Any, schema: dict[str, Any], run_id: str, condition_id: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(judgment), key=str)
    if errors:
        raise ValueError(f"schema violation: {errors[0].message}")
    if judgment["run_id"] != run_id or judgment["condition_id"] != condition_id:
        raise ValueError("judgment IDs differ from packet")


def audit_actual_runs(
    *,
    runs_dir: Path,
    run_prefix: str,
    expected_count: int,
    prompt_path: Path,
    schema_path: Path,
    out_dir: Path,
    model: str,
    expected_cli_version: str,
    git_commit: str,
    timeout_seconds: float = 300.0,
    cli_version: str | None = None,
    invoke: Invoke = codex_invoke,
) -> dict[str, Any]:
    """Judge each run once, in run-ID order; stop after recording a technical failure."""
    if out_dir.exists():
        raise FileExistsError(f"audit output already exists: {out_dir}")
    runs = discover_actual_runs(runs_dir, run_prefix, expected_count)
    verified = [(run_dir, verify_run_bundle(run_dir)) for run_dir in runs]
    version = cli_version if cli_version is not None else codex_cli_version()
    if version != expected_cli_version:
        raise ValueError(f"Codex CLI version {version!r} differs from {expected_cli_version!r}")
    prompt = prompt_path.read_text()
    schema = _load(schema_path)
    out_dir.mkdir(parents=True)
    spec = {
        "audit_runner_version": AUDIT_RUNNER_VERSION,
        "git_commit": git_commit,
        "model": model,
        "cli_version": version,
        "sandbox": "read-only",
        "run_prefix": run_prefix,
        "expected_count": expected_count,
        "order": "run_id",
        "timeout_seconds": timeout_seconds,
        "retry_policy": "none; a technical failure is recorded and the audit stops",
        "judges": 1,
        "sha256": {"prompt": _sha256_file(prompt_path), "schema": _sha256_file(schema_path)},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(out_dir / "spec.json", spec)
    cases: list[dict[str, Any]] = []
    status = "complete"
    for run_dir, run in verified:
        run_id = run_dir.name
        case_dir = out_dir / "cases" / run_id
        packet = packet_for_run(run_dir, run)
        packet_text = json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False)
        stdin_path = case_dir / "input.txt"
        case_dir.mkdir(parents=True)
        stdin_path.write_text(prompt + "\n" + packet_text + "\n")
        workdir = case_dir / "workdir"
        workdir.mkdir()
        started = time.monotonic()
        record: dict[str, Any] = {
            "run_id": run_id,
            "condition_id": packet["condition_id"],
            "input_sha256": _sha256_file(stdin_path),
        }
        try:
            result = invoke(model, schema_path, workdir, stdin_path, timeout_seconds)
            record["returncode"] = result["returncode"]
            record["stderr"] = result["stderr"]
            if result["returncode"] != 0 or result["output"] is None:
                raise RuntimeError(f"codex exited with {result['returncode']} or wrote no output")
            record["output_sha256"] = _sha256_bytes(result["output"].encode())
            judgment = json.loads(result["output"])
            _validate_judgment(judgment, schema, run_id, packet["condition_id"])
        except Exception as error:  # noqa: BLE001 - every failure kind is retained
            record["elapsed_seconds"] = time.monotonic() - started
            record["failure"] = f"{type(error).__name__}: {error}"
            _write_json(case_dir / "record.json", record)
            cases.append({"run_id": run_id, "failure": record["failure"]})
            status = "stopped_technical_failure"
            break
        record["elapsed_seconds"] = time.monotonic() - started
        record["judgment"] = judgment
        _write_json(case_dir / "record.json", record)
        cases.append(
            {
                "run_id": run_id,
                "condition_id": packet["condition_id"],
                "judgment": {label: judgment[label] for label in LABELS},
                "automatic_user_task_success": (run.get("strict_evaluation") or {}).get(
                    "user_task_success"
                ),
                "human_review_reasons": human_review_reasons(run, [judgment]),
            }
        )
    report = summarize(cases, expected_count, status)
    _write_json(out_dir / "report.json", report)
    return report


def summarize(cases: list[dict[str, Any]], expected_count: int, status: str) -> dict[str, Any]:
    """Count agreement over judged cases only; unjudged and failed cases stay visible."""
    judged = [case for case in cases if "judgment" in case]
    comparable = [case for case in judged if type(case["automatic_user_task_success"]) is bool]
    agree = sum(
        case["judgment"]["user_task_success"] == case["automatic_user_task_success"]
        for case in comparable
    )
    return {
        "audit_runner_version": AUDIT_RUNNER_VERSION,
        "status": status,
        "expected_count": expected_count,
        "judged_count": len(judged),
        "unjudged_count": expected_count - len(judged),
        "llm_vs_automatic_user_task_success": {
            "denominator": len(comparable),
            "agree": agree,
            "disagree": len(comparable) - agree,
        },
        "llm_label_counts": {
            label: sum(case["judgment"][label] for case in judged) for label in LABELS
        },
        "human_review_candidates": [
            {"run_id": case["run_id"], "reasons": case["human_review_reasons"]}
            for case in judged
            if case["human_review_reasons"]
        ],
        "failures": [case for case in cases if "failure" in case],
        "research_result": "llm_audit_not_human_audit",
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=Path("artifacts/runs"))
    parser.add_argument("--run-prefix", default="argrec672-v1-act-003")
    parser.add_argument("--expected-count", type=int, default=112)
    parser.add_argument(
        "--prompt",
        type=Path,
        default=Path("configs/audits/phase2_argument_recipient_672_codex_prompt_v1.md"),
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("data/schemas/phase2_argument_recipient_672_codex_audit.schema.json"),
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model", default="gpt-6-sol")
    parser.add_argument("--expected-cli-version", default="codex-cli 0.164.0")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args(argv)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if dirty:
        raise SystemExit("refusing to audit from a dirty working tree")
    report = audit_actual_runs(
        runs_dir=args.runs_dir,
        run_prefix=args.run_prefix,
        expected_count=args.expected_count,
        prompt_path=args.prompt,
        schema_path=args.schema,
        out_dir=args.out_dir,
        model=args.model,
        expected_cli_version=args.expected_cli_version,
        git_commit=commit,
        timeout_seconds=args.timeout,
    )
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
