"""Read the immutable sample and a separately frozen execution configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from goal_takeover.config import ConfigError, load_yaml
from goal_takeover.datasets.pilot_sample import verify_freeze
from goal_takeover.shakedown import _git_metadata
from goal_takeover.storage.run_writer import sha256_file

POSITION_RULE_VERSION = "protocol_offsets_v1"


@dataclass(frozen=True)
class PilotPlan:
    config_path: Path
    config: dict[str, Any]
    conditions: tuple[dict[str, Any], ...]
    evaluator: dict[str, Any]
    model_config: dict[str, Any]
    domain_config: dict[str, Any]
    sample_freeze_path: Path
    sample_freeze_sha256: str


def load_pilot_plan(config_path: str | Path) -> PilotPlan:
    path = Path(config_path).resolve()
    config = load_yaml(path)
    freeze = path.parent / config["references"]["sample_freeze"]
    verify_freeze(freeze)
    declaration = json.loads(freeze.read_text())
    if sha256_file(path) != declaration["files_sha256"][declaration["config"]]:
        raise ConfigError("pilot config must be the unchanged frozen sample configuration")
    manifest = path.parent / config["references"]["sample_manifest"]
    return PilotPlan(
        path,
        config,
        tuple(json.loads(line) for line in manifest.read_text().splitlines()),
        json.loads((path.parent / config["references"]["evaluator_spec"]).read_text()),
        load_yaml(path.parent / config["references"]["model_config"]),
        load_yaml(path.parent / config["references"]["domain_config"]),
        freeze.resolve(),
        sha256_file(freeze),
    )


def validate_capture(plan: PilotPlan, capture: dict[str, Any]) -> None:
    """Do not resolve scientific choices by silently supplying defaults."""
    fixed = plan.config["capture"]
    if not isinstance(capture, dict):
        raise ConfigError("runtime capture must be an object")
    for key in (
        "residual_stream",
        "layers",
        "residual_hook_point",
        "attention_mode",
        "activation_mode",
        "boundaries",
        "token_positions",
        "record_token_index",
        "record_token_id",
    ):
        if capture.get(key) != fixed[key]:
            raise ConfigError(f"runtime capture conflicts with sample: {key}")
    if capture.get("position_rule_version") != POSITION_RULE_VERSION:
        raise ConfigError("runtime must freeze the implemented position rule version")
    window = capture.get("ipi_window", {})
    if not isinstance(window, dict):
        raise ConfigError("freeze the IPI window widths before execution")
    if any(type(window.get(key)) is not int or window[key] < 0 for key in ("left", "right")):
        raise ConfigError("freeze nonnegative integer IPI window widths before execution")
    ids = {row["condition_id"] for row in plan.conditions}
    for key in ("full_sequence_condition_ids", "full_sequence_attention_condition_ids"):
        values = capture.get(key)
        if (
            not isinstance(values, list)
            or len(values) != len(set(values))
            or not set(values).issubset(ids)
        ):
            raise ConfigError(f"freeze an explicit condition subset (possibly empty): {key}")
    attention = capture.get("attention", {})
    if not isinstance(attention, dict):
        raise ConfigError("freeze attention range/query/aggregation rules")
    if (
        attention.get("query_position") != "Tend_assistant"
        or attention.get("aggregation") != "sum_and_mean"
        or attention.get("key_ranges") != ["user_goal", "intervention", "tool_metadata"]
    ):
        raise ConfigError("unsupported or missing attention range/query/aggregation rules")


def load_runtime_freeze(plan: PilotPlan, path: str | Path) -> dict[str, Any]:
    """Fail closed before importing torch or loading weights."""
    path = Path(path).resolve()
    runtime = load_yaml(path)
    if runtime.get("status") != "frozen" or runtime.get("schema_version") != 1:
        raise ConfigError("a separate frozen pilot runtime configuration is required")
    if runtime.get("sample_freeze_sha256") != plan.sample_freeze_sha256:
        raise ConfigError("runtime refers to a different sample freeze")
    validate_capture(plan, runtime.get("capture", {}))
    root = plan.config_path.parents[2]
    files = runtime.get("files_sha256", {})
    required = {str(p.relative_to(root)) for p in (root / "src/goal_takeover").rglob("*.py")}
    required.update(
        str(p.relative_to(root)) for p in (root / "configs").rglob("*.yaml") if p.resolve() != path
    )
    required.update(str(p.relative_to(root)) for p in (root / "data/schemas").glob("*.json"))
    if not required.issubset(files):
        raise ConfigError("runtime freeze must pin all source modules and config files")
    for relative, checksum in files.items():
        target = Path(relative)
        if target.is_absolute() or ".." in target.parts:
            raise ConfigError("runtime checksums must use repository-relative paths")
        if sha256_file(root / target) != checksum:
            raise ConfigError(f"runtime checksum mismatch: {relative}")
    commit, dirty = _git_metadata()
    if dirty or not commit or runtime.get("git_commit") != commit:
        raise ConfigError("runtime requires its frozen commit and a clean working tree")
    for key in ("chat_template_sha256", "tool_schema_sha256"):
        digest = runtime.get(key)
        if not isinstance(digest, str) or len(digest) != 64:
            raise ConfigError(f"runtime must pin {key}")
    review = runtime.get("password_suspicion_review", {})
    if (
        review.get("approved") is not True
        or not review.get("reviewer_id")
        or not review.get("evidence")
        or not review.get("rubric")
    ):
        raise ConfigError("task 14 requires a justified, frozen suspicion review and rubric")
    if runtime.get("capture_resource_preflight_passed") is not True:
        raise ConfigError("capture subset/resource preflight must pass before collection")
    return runtime
