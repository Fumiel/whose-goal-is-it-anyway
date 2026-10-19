"""Synthetic-fixture checks for the Phase 2 outcome report; not research data."""

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from goal_takeover.phase2.outcome_report import build_outcome_report, write_outcome_report

COMMIT = "a" * 40
ROLES = ("user_instruction", "tool_output", "quotation")


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _automatic(group, *, user=False, candidate=False) -> dict:
    return {
        "native_user_task_success": user,
        "native_attack_success": False,
        "automatic_strict_user_task_success": user,
        "strict_candidate_attack_occurred": candidate,
        "candidate_action_occurred": candidate,
        "group": group,
    }


def _build_fixture(root: Path, *, human_user=(False, True, False)) -> tuple[Path, Path]:
    runs, records = [], []
    for index, role in enumerate(ROLES, start=1):
        run_id = f"synthetic-c00{index}-a1"
        bundle = root / "artifacts" / "runs" / run_id
        group = "C" if role == "tool_output" else None
        automatic = _automatic(group)
        _write(bundle / "condition.json", {
            "condition_id": f"cond{index}", "source_role": role,
            "has_attack": role == "tool_output",
        })
        _write(bundle / "run.json", {
            "status": "completed", "split": "train", "git_commit": COMMIT,
            "git_dirty": False, "condition_id": f"cond{index}",
            "actual_exposed_scored": True,
            "outcome": {**automatic, "baseline_failure": False},
        })
        artifacts = []
        for name in ("condition.json", "run.json"):
            target = bundle / name
            artifacts.append({
                "relative_path": name, "bytes": target.stat().st_size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            })
        manifest_sha = _write(bundle / "manifest.json", {"artifacts": artifacts})
        runs.append({"run_id": run_id, "manifest_sha256": manifest_sha})
        final = {
            "ordered_document_reads": True,
            "authorized_recipient_transfer": human_user[index - 1],
            "user_task_success": human_user[index - 1],
            "candidate_action_occurred": False,
            "forbidden_side_effects": not human_user[index - 1],
        }
        records.append({
            "run_id": run_id, "condition_id": f"cond{index}",
            "bundle_manifest_sha256": manifest_sha,
            "adjudication": {
                "status": "resolved", "final_judgment": final,
                "first_to_final_changes": {},
                "automatic_comparison": automatic,
                "automatic_disagreement_explanation": "synthetic",
            },
        })
    collection = root / "collection.json"
    collection.write_text(json.dumps({
        "experiment_id": "synthetic", "decision_id": "RDR-S-02",
        "execution_git_commit": COMMIT, "runs": runs,
    }), encoding="utf-8")
    audit = root / "audit.json"
    audit.write_text(json.dumps({
        "experiment_id": "synthetic",
        "audit_provenance": {
            "decision_id": "RDR-S-03", "confirmatory_test_status": "not_created_or_inspected",
        },
        "records": records,
    }), encoding="utf-8")
    return collection, audit


class OutcomeReportTest(unittest.TestCase):
    def build(self, root: Path, **kwargs) -> dict:
        collection, audit = _build_fixture(root, **kwargs)
        return build_outcome_report(collection, audit, artifact_root=root / "artifacts")

    def test_groups_apply_only_to_ipi_and_keep_labels_separate(self):
        with TemporaryDirectory() as tmp:
            rows = {r["source_role"]: r for r in self.build(Path(tmp))["conditions"]}
        self.assertEqual(rows["tool_output"]["frozen_automatic_group_reported"], "C")
        self.assertEqual(rows["tool_output"]["group_applicability"], "ipi_frozen_automatic_only")
        for role in ("user_instruction", "quotation"):
            self.assertIsNone(rows[role]["frozen_automatic_group_reported"])
            self.assertEqual(rows[role]["group_applicability"], "not_applicable")
        self.assertEqual(rows["user_instruction"]["role_class"], "authorized_alternative_control")
        self.assertTrue(rows["tool_output"]["human_post_run"]["user_task_success"])
        self.assertFalse(rows["tool_output"]["frozen_automatic"]["automatic_strict_user_task_success"])

    def test_difference_counts_and_no_rates(self):
        with TemporaryDirectory() as tmp:
            report = self.build(Path(tmp))
        self.assertEqual(report["counts"]["human_automatic_difference_conditions"], 1)
        self.assertEqual(report["human_post_run_counts"]["user_task_success"], 1)
        self.assertEqual(report["frozen_automatic_counts"]["automatic_strict_user_task_success"], 0)
        self.assertFalse(report["rates_reported"])
        self.assertFalse(report["independent_validation"])
        self.assertFalse(report["confirmatory_test_authorized"])
        self.assertFalse(any("rate" in key and key != "rates_reported" for key in report))

    def test_deterministic(self):
        with TemporaryDirectory() as tmp:
            collection, audit = _build_fixture(Path(tmp))
            args = (collection, audit)
            first = build_outcome_report(*args, artifact_root=Path(tmp) / "artifacts")
            second = build_outcome_report(*args, artifact_root=Path(tmp) / "artifacts")
        self.assertEqual(first, second)

    def test_changed_artifact_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            collection, audit = _build_fixture(root)
            run_json = root / "artifacts/runs/synthetic-c001-a1/run.json"
            run_json.write_text(run_json.read_text() + " ", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_outcome_report(collection, audit, artifact_root=root / "artifacts")

    def test_audit_must_match_run_labels(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            collection, audit = _build_fixture(root)
            data = json.loads(audit.read_text())
            data["records"][1]["adjudication"]["automatic_comparison"]["group"] = "D"
            audit.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_outcome_report(collection, audit, artifact_root=root / "artifacts")

    def test_unresolved_or_missing_records_are_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            collection, audit = _build_fixture(root)
            data = json.loads(audit.read_text())
            data["records"][0]["adjudication"]["status"] = "open"
            audit.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_outcome_report(collection, audit, artifact_root=root / "artifacts")
            data["records"][0]["adjudication"]["status"] = "resolved"
            data["records"].pop()
            audit.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_outcome_report(collection, audit, artifact_root=root / "artifacts")

    def test_writer_never_overwrites(self):
        with TemporaryDirectory() as tmp:
            report = self.build(Path(tmp))
            target = Path(tmp) / "report.json"
            write_outcome_report(report, target)
            with self.assertRaises(FileExistsError):
                write_outcome_report(report, target)


if __name__ == "__main__":
    unittest.main()
