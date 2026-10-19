"""Outcome report for an audited Phase 2 two-document train collection.

Human post-run labels and frozen automatic labels are kept in separate fields.
No rate is reported and no A-D group is derived from the human labels.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
HUMAN_FIELDS = (
    "ordered_document_reads",
    "authorized_recipient_transfer",
    "user_task_success",
    "candidate_action_occurred",
    "forbidden_side_effects",
)
AUTOMATIC_FIELDS = (
    "native_user_task_success",
    "native_attack_success",
    "automatic_strict_user_task_success",
    "strict_candidate_attack_occurred",
    "candidate_action_occurred",
    "group",
)
# Human field -> automatic field that measures the same event.
COMPARED_FIELDS = {
    "user_task_success": "automatic_strict_user_task_success",
    "candidate_action_occurred": "candidate_action_occurred",
}
ROLE_CLASS = {
    "tool_output": "ipi_condition",
    "user_instruction": "authorized_alternative_control",
}
LIMITS = (
    "All conditions belong to one conservatively connected component and the train split; "
    "this is not independent validation and supports no success-rate estimate.",
    "Human labels follow the post-run rubric of RDR-2026-10-19-03 and are not a pre-frozen "
    "success rate; frozen automatic labels are retained unchanged.",
    "A-D groups apply only to the IPI condition and use the frozen automatic label; "
    "no A-D group is derived from the human labels.",
    "The confirmatory test set is not created or inspected.",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_bundle(bundle: Path, expected_manifest_sha256: str) -> None:
    manifest_path = bundle / "manifest.json"
    if _sha256(manifest_path) != expected_manifest_sha256:
        raise ValueError(f"{bundle.name}: bundle manifest checksum mismatch")
    for artifact in _load(manifest_path)["artifacts"]:
        target = bundle / artifact["relative_path"]
        if not target.is_file():
            raise ValueError(f"{bundle.name}: missing artifact {artifact['relative_path']}")
        if target.stat().st_size != artifact["bytes"] or _sha256(target) != artifact["sha256"]:
            raise ValueError(f"{bundle.name}: artifact mismatch {artifact['relative_path']}")


def _condition_row(
    run_id: str, record: dict[str, Any], run: dict[str, Any], condition: dict[str, Any]
) -> dict[str, Any]:
    adjudication = record["adjudication"]
    if adjudication["status"] != "resolved":
        raise ValueError(f"{run_id}: unresolved adjudication")
    human = {name: bool(adjudication["final_judgment"][name]) for name in HUMAN_FIELDS}
    audit_auto = adjudication["automatic_comparison"]
    outcome = run["outcome"]
    # The audit's frozen-label copy must agree with the immutable run.json.
    pairs = {
        "native_user_task_success": "native_user_task_success",
        "native_attack_success": "native_attack_success",
        "automatic_strict_user_task_success": "automatic_strict_user_task_success",
        "strict_candidate_attack_occurred": "strict_candidate_attack_occurred",
        "candidate_action_occurred": "candidate_action_occurred",
        "group": "group",
    }
    for audit_name, run_name in pairs.items():
        if audit_auto[audit_name] != outcome[run_name]:
            raise ValueError(f"{run_id}: audit and run.json disagree on {audit_name}")
    automatic = {name: audit_auto[name] for name in AUTOMATIC_FIELDS}
    automatic["baseline_failure"] = bool(outcome["baseline_failure"])
    role = condition["source_role"]
    role_class = ROLE_CLASS.get(role, "role_control")
    ipi = role_class == "ipi_condition"
    differences = [
        {
            "human_field": human_name,
            "automatic_field": auto_name,
            "human": human[human_name],
            "automatic": bool(automatic[auto_name]),
        }
        for human_name, auto_name in COMPARED_FIELDS.items()
        if human[human_name] != bool(automatic[auto_name])
    ]
    return {
        "run_id": run_id,
        "condition_id": condition["condition_id"],
        "source_role": role,
        "role_class": role_class,
        "has_attack": bool(condition["has_attack"]),
        "actual_exposed_scored": bool(run["actual_exposed_scored"]),
        "human_post_run": human,
        "frozen_automatic": automatic,
        "frozen_automatic_group_reported": automatic["group"] if ipi else None,
        "group_applicability": "ipi_frozen_automatic_only" if ipi else "not_applicable",
        "human_automatic_differences": differences,
        "automatic_disagreement_explanation": adjudication.get(
            "automatic_disagreement_explanation"
        ),
        "first_to_final_changes": adjudication.get("first_to_final_changes", {}),
    }


def build_outcome_report(
    collection_path: str | Path,
    audit_path: str | Path,
    *,
    artifact_root: str | Path = "artifacts",
) -> dict[str, Any]:
    collection_path, audit_path = Path(collection_path), Path(audit_path)
    collection, audit = _load(collection_path), _load(audit_path)
    if collection["experiment_id"] != audit["experiment_id"]:
        raise ValueError("collection and audit belong to different experiments")
    records = {record["run_id"]: record for record in audit["records"]}
    runs = collection["runs"]
    if set(records) != {row["run_id"] for row in runs} or len(records) != len(runs):
        raise ValueError("audit records do not match the collection runs one to one")
    rows = []
    for entry in runs:
        run_id = entry["run_id"]
        record = records[run_id]
        if record["bundle_manifest_sha256"] != entry["manifest_sha256"]:
            raise ValueError(f"{run_id}: audit and collection manifest checksums differ")
        bundle = Path(artifact_root) / "runs" / run_id
        _verify_bundle(bundle, entry["manifest_sha256"])
        run, condition = _load(bundle / "run.json"), _load(bundle / "condition.json")
        if run["status"] != "completed" or run["split"] != "train":
            raise ValueError(f"{run_id}: expected a completed train run")
        if run["git_commit"] != collection["execution_git_commit"] or run["git_dirty"]:
            raise ValueError(f"{run_id}: run commit differs from the collection or is dirty")
        if run["condition_id"] != record["condition_id"]:
            raise ValueError(f"{run_id}: audit condition ID differs from run.json")
        rows.append(_condition_row(run_id, record, run, condition))

    def count(section: str, field: str) -> int:
        return sum(1 for row in rows if row[section][field])

    return {
        "schema_version": SCHEMA_VERSION,
        "report_kind": "phase2_two_document_outcome_report",
        "experiment_id": collection["experiment_id"],
        "decision_ids": sorted({collection["decision_id"], audit["audit_provenance"]["decision_id"]}),
        "execution_git_commit": collection["execution_git_commit"],
        "collection_manifest": {"path": str(collection_path), "sha256": _sha256(collection_path)},
        "human_audit": {"path": str(audit_path), "sha256": _sha256(audit_path)},
        "counts": {
            "planned": len(runs),
            "completed": len(rows),
            "technical_failures": 0,
            "audited": len(rows),
            "unresolved_disagreements": 0,
            "actual_exposed_scored": sum(row["actual_exposed_scored"] for row in rows),
            "human_automatic_difference_conditions": sum(
                1 for row in rows if row["human_automatic_differences"]
            ),
        },
        "human_post_run_counts": {name: count("human_post_run", name) for name in HUMAN_FIELDS},
        "frozen_automatic_counts": {
            name: count("frozen_automatic", name)
            for name in (
                "native_user_task_success",
                "native_attack_success",
                "automatic_strict_user_task_success",
                "strict_candidate_attack_occurred",
                "baseline_failure",
            )
        },
        "conditions": rows,
        "rates_reported": False,
        "independent_validation": False,
        "primary_model_adopted": False,
        "confirmatory_test_authorized": False,
        "confirmatory_test_status": audit["audit_provenance"]["confirmatory_test_status"],
        "limits": list(LIMITS),
    }


def write_outcome_report(report: dict[str, Any], output: str | Path) -> Path:
    """Write a new report; an existing file is never overwritten."""
    path = Path(output)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return path
