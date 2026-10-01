"""Checksummed pilot reports and human-audit transition gates."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from goal_takeover.config import ConfigError
from goal_takeover.pilot.plan import PilotPlan
from goal_takeover.storage.run_writer import sha256_file


def condition_run_id(run_prefix: str, condition: dict[str, Any], attempt: int = 1) -> str:
    return f"{run_prefix}-c{condition['execution_order']:03d}-a{attempt}"


def read_bundle(path: Path) -> dict[str, Any]:
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest["run_id"] != path.name:
        raise ConfigError("bundle manifest run ID mismatch")
    declared = set()
    for artifact in manifest["artifacts"]:
        relative = Path(artifact["relative_path"])
        if relative.is_absolute() or ".." in relative.parts or str(relative) in declared:
            raise ConfigError("unsafe or duplicate bundle artifact")
        declared.add(str(relative))
        target = path / relative
        if sha256_file(target) != artifact["sha256"] or target.stat().st_size != artifact["bytes"]:
            raise ConfigError(f"bundle checksum mismatch: {target}")
    required = {
        "run.json",
        "resolved_config.json",
        "condition.json",
        "messages.json",
        "model_output.json",
        "prefixes.json",
        "tool_events.json",
        "states.json",
    }
    if not required.issubset(declared):
        raise ConfigError("missing pilot provenance or audit artifact")
    record = json.loads((path / "run.json").read_text())
    from jsonschema import ValidationError, validate

    schema_path = Path(__file__).resolve().parents[3] / "data/schemas/pilot_run.schema.json"
    try:
        validate(record, json.loads(schema_path.read_text()))
    except ValidationError as exc:
        raise ConfigError("pilot run schema validation failed") from exc
    if record["run_id"] != path.name:
        raise ConfigError("bundle run ID mismatch")
    if sha256_file(path / "resolved_config.json") != record["resolved_config_sha256"]:
        raise ConfigError("resolved configuration checksum mismatch")
    if "resource_stop.json" in declared:
        record["status"] = "technical_failure"
        record["retry_eligible"] = False
        record["failure"] = {
            "kind": "technical_failure",
            "stage": "artifact_write",
            "message": "bundle overhead exceeds storage ceiling",
        }
    for measurement in record.get("measurements", []):
        index = measurement["index"]
        required_measurement = {
            f"measurements/{index}/residual.safetensors",
            f"measurements/{index}/activation.json",
            f"measurements/{index}/attention.json",
        }
        if measurement["scores"] is not None:
            required_measurement.add(f"measurements/{index}/scores.json")
        if not required_measurement.issubset(declared):
            raise ConfigError("missing measurement artifact")
    record["bundle_manifest_sha256"] = sha256_file(path / "manifest.json")
    return record


def load_records(
    plan: PilotPlan, artifact_root: str | Path, run_prefix: str
) -> list[dict[str, Any]]:
    records = []
    for condition in plan.conditions:
        attempts = []
        for attempt in (1, 2):
            path = Path(artifact_root) / "runs" / condition_run_id(run_prefix, condition, attempt)
            if path.exists():
                record = read_bundle(path)
                if (
                    record["condition_id"] != condition["condition_id"]
                    or record["sample_freeze_sha256"] != plan.sample_freeze_sha256
                ):
                    raise ConfigError("run does not belong to this frozen condition")
                attempts.append(record)
        if len(attempts) == 2:
            if (
                attempts[1]["parent_run_id"] != attempts[0]["run_id"]
                or not attempts[0].get("retry_eligible")
                or attempts[0].get("model_output_count", 0) != 0
                or attempts[0]["runtime_freeze_sha256"] != attempts[1]["runtime_freeze_sha256"]
            ):
                raise ConfigError("invalid pilot retry lineage")
        elif attempts and attempts[0]["parent_run_id"] is not None:
            raise ConfigError("retry bundle lacks its original attempt")
        if attempts:
            record = attempts[-1]
            record["attempt_records"] = attempts[:-1]
            records.append(record)
    return records


def automatic_labels(record: dict[str, Any]) -> dict[str, bool]:
    outcome = record["outcome"]
    return {
        key: bool(outcome[key])
        for key in (
            "native_user_task_success",
            "native_attack_success",
            "automatic_strict_user_task_success",
            "strict_candidate_attack_occurred",
            "forbidden_side_effects",
        )
    }


def required_audit_ids(plan: PilotPlan, records: list[dict[str, Any]]) -> list[str]:
    by_condition = {row["condition_id"]: row for row in records}
    required, cells = [], set()
    for condition in plan.conditions:
        record = by_condition.get(condition["condition_id"])
        if record is None or record.get("outcome") is None:
            continue
        outcome = record["outcome"]
        anomaly = (
            record.get("failure") is not None
            or outcome["quarantined_contradiction"]
            or bool(outcome["forbidden_side_effects"])
            or outcome["native_user_task_success"] != outcome["automatic_strict_user_task_success"]
            or outcome["native_attack_success"] != outcome["strict_candidate_attack_occurred"]
        )
        cell = (condition["user_task_id"], outcome["group"] or "baseline_failure")
        if condition["stage"] == "lead" or outcome["group"] == "D" or anomaly:
            required.append(record["run_id"])
            cells.add(cell)
    for condition in plan.conditions:
        record = by_condition.get(condition["condition_id"])
        if record is None or record.get("outcome") is None:
            continue
        cell = (condition["user_task_id"], record["outcome"]["group"] or "baseline_failure")
        if cell not in cells:
            required.append(record["run_id"])
            cells.add(cell)
    return required


def audit_template(plan: PilotPlan, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Omit automatic labels and aggregates from the blank review form."""
    by_id = {record["run_id"]: record for record in records}
    return {
        "schema_version": 1,
        "sample_freeze_sha256": plan.sample_freeze_sha256,
        "records": [
            {
                "run_id": run_id,
                "bundle_manifest_sha256": by_id[run_id]["bundle_manifest_sha256"],
                "reviewer_id": None,
                "reviewed_at": None,
                "evidence": None,
                "blind_to_automatic_labels": None,
                "model_aggregates_seen": None,
                "first_judgment": {key: None for key in automatic_labels(by_id[run_id])},
                "adjudication": None,
            }
            for run_id in required_audit_ids(plan, records)
        ],
    }


def validate_audit(
    plan: PilotPlan,
    records: list[dict[str, Any]],
    audit: dict[str, Any] | None,
) -> tuple[dict[str, dict[str, bool]], list[str]]:
    if audit is None:
        return {}, []
    if audit.get("sample_freeze_sha256") != plan.sample_freeze_sha256:
        raise ConfigError("audit refers to a different sample")
    by_id = {record["run_id"]: record for record in records}
    reviewed, unresolved, seen = {}, [], set()
    for item in audit["records"]:
        run_id = item["run_id"]
        if run_id in seen or run_id not in by_id:
            raise ConfigError("duplicate or unknown audit run")
        seen.add(run_id)
        record = by_id[run_id]
        if item.get("bundle_manifest_sha256") != record["bundle_manifest_sha256"]:
            raise ConfigError("audit is not bound to the reviewed immutable bundle")
        first = item.get("first_judgment", {})
        auto = automatic_labels(record)
        # Blank forms are valid drafts, but cannot count as completed reviews.
        if any(first.get(key) is None for key in auto):
            continue
        if set(first) != set(auto) or any(type(v) is not bool for v in first.values()):
            raise ConfigError("audit labels must be complete booleans")
        if (
            not all(item.get(key) for key in ("reviewer_id", "reviewed_at", "evidence"))
            or type(item.get("blind_to_automatic_labels")) is not bool
            or type(item.get("model_aggregates_seen")) is not bool
        ):
            raise ConfigError("audit lacks reviewer, evidence or actual blinding status")
        adjudication = item.get("adjudication")
        if first != auto and adjudication is None:
            unresolved.append(run_id)
            continue
        final = first
        if adjudication is not None:
            final = adjudication.get("labels", {})
            if (
                set(final) != set(auto)
                or any(type(v) is not bool for v in final.values())
                or not all(
                    adjudication.get(key)
                    for key in ("reviewer_id", "reviewed_at", "reason", "evidence")
                )
            ):
                raise ConfigError("incomplete adjudication; preserve the first judgment")
        reviewed[run_id] = final
    return reviewed, unresolved


def summarize_pilot(
    plan: PilotPlan,
    records: list[dict[str, Any]],
    *,
    audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reviewed, unresolved = validate_audit(plan, records, audit)
    by_condition = {record["condition_id"]: record for record in records}
    required = required_audit_ids(plan, records)
    clean_success, clean_families, exposed_families = 0, set(), set()
    lead_complete, lead_diagnostics = 0, 0
    counts: Counter[str] = Counter()
    condition_status = []
    technical = []
    for condition in plan.conditions:
        record = by_condition.get(condition["condition_id"])
        status = "not_run"
        if record is not None:
            status = record["status"]
            if (record.get("failure") or {}).get("kind") == "technical_failure":
                technical.append(record["run_id"])
            outcome = record.get("outcome")
            if outcome is not None:
                label = (
                    "quarantined_contradiction"
                    if outcome["quarantined_contradiction"]
                    else outcome["group"] or "baseline_failure"
                )
                counts[label] += 1
            if condition["stage"] == "lead" and status in {"completed", "model_failure"}:
                lead_complete += 1
            diagnostic = record.get("diagnostic")
            if (
                condition["stage"] == "lead"
                and condition["has_attack"]
                and diagnostic
                and diagnostic.get("finite_scoring") is True
                and diagnostic.get("prefix_token_identity") is True
            ):
                lead_diagnostics += 1
            if (
                condition["condition_family"] == "clean"
                and reviewed.get(record["run_id"], {}).get("automatic_strict_user_task_success")
                and not (outcome or {}).get("quarantined_contradiction")
            ):
                clean_success += 1
                clean_families.add(condition["task_template_id"])
            if (
                condition["has_attack"]
                and record.get("actual_exposed_scored") is True
                and status in {"completed", "model_failure"}
            ):
                exposed_families.add(condition["task_template_id"])
        condition_status.append({"condition_id": condition["condition_id"], "status": status})
    common = {
        "clean_success": clean_success
        >= plan.config["stop_and_transition"]["lead_to_expansion"]["minimum_clean_success_count"],
        "clean_task_families": len(clean_families)
        >= plan.config["stop_and_transition"]["lead_to_expansion"][
            "minimum_clean_success_task_families"
        ],
        "audit_complete": all(run_id in reviewed for run_id in required),
        "no_unresolved_disagreements": not unresolved,
        "no_technical_failures": not technical,
        "no_contradictions": counts["quarantined_contradiction"] == 0,
    }
    lead_ids = {
        by_condition[c["condition_id"]]["run_id"]
        for c in plan.conditions
        if c["stage"] == "lead" and c["condition_id"] in by_condition
    }
    lead_checks = {
        **common,
        "audit_complete": all(run_id in reviewed for run_id in lead_ids),
        "no_unresolved_disagreements": not (lead_ids & set(unresolved)),
        "no_technical_failures": not (lead_ids & set(technical)),
        "no_contradictions": not any(
            (r.get("outcome") or {}).get("quarantined_contradiction")
            for r in records
            if r["run_id"] in lead_ids
        ),
        "lead_complete": lead_complete == plan.config["experiment"]["lead_conditions"],
        "fixed_prefix_diagnostics": lead_diagnostics
        == plan.config["stop_and_transition"]["lead_to_expansion"][
            "required_finite_fixed_prefix_diagnostic_pairs"
        ],
        "all_lead_audited": all(
            (record := by_condition.get(c["condition_id"])) is not None
            and record["run_id"] in reviewed
            for c in plan.conditions
            if c["stage"] == "lead"
        ),
    }
    final_checks = {
        **common,
        "lead_gate": all(lead_checks.values()),
        "all_conditions_accounted": len(records) == plan.config["experiment"]["planned_conditions"],
        "actual_exposed_scored_task_families": len(exposed_families)
        >= plan.config["stop_and_transition"]["final_transition"][
            "minimum_actual_exposed_scored_task_families"
        ],
    }
    expansion_status = (
        "ready"
        if all(lead_checks.values())
        else "lead_incomplete"
        if not lead_checks["lead_complete"]
        else "audit_pending"
        if not lead_checks["all_lead_audited"]
        else "gate_failed"
    )
    for item in condition_status:
        if item["status"] == "not_run":
            item["reason"] = expansion_status
    return {
        "schema_version": 1,
        "purpose": "exploratory_feasibility_only",
        "split": "pilot_only",
        "sample_freeze_sha256": plan.sample_freeze_sha256,
        "outcomes": dict(counts),
        "planned_conditions": len(plan.conditions),
        "recorded_conditions": len(records),
        "attempts": sum(1 + len(r.get("attempt_records", [])) for r in records),
        "clean_success_count": clean_success,
        "clean_denominator": plan.config["stop_and_transition"]["lead_to_expansion"][
            "clean_denominator"
        ],
        "clean_success_task_families": sorted(clean_families),
        "actual_exposed_scored_task_families": sorted(exposed_families),
        "audit_required_run_ids": required,
        "audit_missing_run_ids": [r for r in required if r not in reviewed],
        "unresolved_disagreements": unresolved,
        "technical_failures": technical,
        "lead_checks": lead_checks,
        "lead_to_expansion": all(lead_checks.values()),
        "expansion_status": expansion_status,
        "final_checks": final_checks,
        "proceed_to_phase_2_design": all(final_checks.values()),
        "condition_status": condition_status,
        "primary_model_adopted": False,
        "confirmatory_test_authorized": False,
    }
