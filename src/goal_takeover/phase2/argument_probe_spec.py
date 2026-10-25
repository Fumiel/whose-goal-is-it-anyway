"""Build a checksummed development probe declaration from an audited collection."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from goal_takeover.phase2.argument_probe import _declaration_sha256, validate_spec


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(plan_path: Path, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = _read(plan_path)
    sources = {
        key: root / plan[key]
        for key in (
            "collection_manifest",
            "condition_spec",
            "split_manifest",
            "human_audit",
            "collection_design_freeze",
        )
    }
    collection, declaration, split, audit = (
        _read(sources[key])
        for key in ("collection_manifest", "condition_spec", "split_manifest", "human_audit")
    )
    if audit["unresolved_disagreements"] != 0 or len(audit["records"]) != 96:
        raise ValueError("the all-run human audit is incomplete")
    records = {row["run_id"]: row for row in audit["records"]}
    conditions = {row["condition_id"]: row for row in declaration["condition_specs"]}
    assignments = {row["condition_id"]: row for row in split["assignments"]}
    runs = collection["runs"]
    if not (len(records) == len(conditions) == len(assignments) == len(runs) == 96):
        raise ValueError("collection, audit, condition and split counts differ")
    if set(records) != {row["run_id"] for row in runs}:
        raise ValueError("audit does not cover exactly the collected runs")
    rows = []
    for run in runs:
        run_id, condition_id = run["run_id"], run["condition_id"]
        audited, condition, assignment = (
            records[run_id],
            conditions[condition_id],
            assignments[condition_id],
        )
        if (
            audited["condition_id"] != condition_id
            or audited["split"] != run["split"]
            or audited["bundle_manifest_sha256"] != run["manifest_sha256"]
            or audited["automatic_comparison"]["run_status"] != run["status"]
            or assignment["split"] != run["split"]
            or run["status"] not in {"completed", "model_failure"}
        ):
            raise ValueError(f"audit or split mismatch: {run_id}")
        bundle_manifest = root / "artifacts/runs" / run_id / "manifest.json"
        if _sha256(bundle_manifest) != run["manifest_sha256"]:
            raise ValueError(f"raw bundle manifest changed: {run_id}")
        rows.append(
            {
                "condition_id": condition_id,
                "run_id": run_id,
                "split": run["split"],
                "component_id": assignment["component_id"],
                "task_template_id": condition["task_template_id"],
                "pair_id": condition["pair_id"],
                "paraphrase_family_id": condition["paraphrase_family_id"],
                "user_instruction": condition["user_instruction"],
                "argument_present": condition["argument_present"],
            }
        )
    spec = {
        "status": "frozen_research",
        "candidate_values": declaration["account_value_ids"],
        "feature_specs": [
            {
                "feature_id": f"layer{layer}_tend_assistant",
                "layer": f"model.layers.{layer}",
                "boundary": plan["feature_boundary"],
                "position_name": plan["feature_position"],
                "position_rule_version": plan["position_rule_version"],
            }
            for layer in plan["layers"]
        ],
        "conditions": rows,
        "fit": plan["fit"],
        "missing_policy": plan["missing_policy"],
    }
    freeze = {
        "status": "development_probe_input_frozen",
        "probe_declaration_sha256": _declaration_sha256(spec),
        "source_sha256": {key: _sha256(path) for key, path in sources.items()},
        "plan_sha256": _sha256(plan_path),
        "run_status_counts": collection["execution_status_counts"],
        "condition_count": len(rows),
        "label_source": "condition_argument_present",
        "audit_role": "all_run_gate_only_not_probe_teacher",
        "test_set_status": "not_created_or_inspected",
    }
    return spec, freeze


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("spec_output", type=Path)
    parser.add_argument("freeze_output", type=Path)
    args = parser.parse_args()
    if args.spec_output.exists() or args.freeze_output.exists():
        raise FileExistsError("probe declaration and freeze outputs must be new")
    spec, freeze = build(args.plan, args.root)
    args.freeze_output.write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
    spec["design_freeze_path"] = str(Path("../../") / args.freeze_output.relative_to(args.root))
    spec["design_freeze_sha256"] = _sha256(args.freeze_output)
    validate_spec(spec)
    args.spec_output.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
