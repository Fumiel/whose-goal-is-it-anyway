"""Synthetic checks for the audited collection to probe declaration transform."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from goal_takeover.phase2.argument_probe_spec import build


def write_json(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ArgumentProbeSpecTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.plan_path = self.root / "plan.json"
        self.paths = {
            key: f"inputs/{key}.json"
            for key in (
                "collection_manifest",
                "condition_spec",
                "split_manifest",
                "human_audit",
                "collection_design_freeze",
            )
        }
        write_json(
            self.plan_path,
            {
                **self.paths,
                "feature_boundary": "user_to_assistant",
                "feature_position": "Tend_assistant",
                "position_rule_version": "protocol_offsets_v1",
                "layers": [8],
                "fit": {
                    "regularization_c": [0.1],
                    "max_iter": 100,
                    "seed": 1,
                    "calibration_bins": 5,
                    "random_label_repeats": 2,
                    "cluster_bootstrap_repeats": 2,
                },
                "missing_policy": "exclude_with_reason",
            },
        )
        runs, records, conditions, assignments = [], [], [], []
        for index in range(96):
            run_id, condition_id = f"run-{index}", f"condition-{index}"
            split = "train" if index < 64 else "validation"
            status = "model_failure" if index in (47, 55) else "completed"
            digest = write_json(
                self.root / "artifacts/runs" / run_id / "manifest.json", {"run_id": run_id}
            )
            runs.append(
                {
                    "run_id": run_id,
                    "condition_id": condition_id,
                    "split": split,
                    "status": status,
                    "manifest_sha256": digest,
                }
            )
            records.append(
                {
                    "run_id": run_id,
                    "condition_id": condition_id,
                    "split": split,
                    "bundle_manifest_sha256": digest,
                    "automatic_comparison": {"run_status": status},
                }
            )
            conditions.append(
                {
                    "condition_id": condition_id,
                    "task_template_id": f"task-{index // 4}",
                    "pair_id": f"pair-{index // 4}",
                    "paraphrase_family_id": split,
                    "user_instruction": "Pay ACCOUNT-A.",
                    "argument_present": {"v1": index % 2, "v2": 1 - index % 2},
                }
            )
            assignments.append(
                {"condition_id": condition_id, "component_id": split, "split": split}
            )
        self.collection = {
            "runs": runs,
            "execution_status_counts": {"completed": 94, "model_failure": 2},
        }
        self.audit = {"records": records, "unresolved_disagreements": 0}
        write_json(self.root / self.paths["collection_manifest"], self.collection)
        write_json(
            self.root / self.paths["condition_spec"],
            {
                "account_value_ids": {"v1": "ACCOUNT-A", "v2": "ACCOUNT-B"},
                "condition_specs": conditions,
            },
        )
        write_json(self.root / self.paths["split_manifest"], {"assignments": assignments})
        write_json(self.root / self.paths["human_audit"], self.audit)
        write_json(self.root / self.paths["collection_design_freeze"], {})

    def test_includes_valid_model_failures_with_condition_labels(self) -> None:
        spec, freeze = build(self.plan_path, self.root)
        self.assertEqual(len(spec["conditions"]), 96)
        self.assertEqual(spec["conditions"][47]["argument_present"], {"v1": 1, "v2": 0})
        self.assertEqual(freeze["run_status_counts"]["model_failure"], 2)
        self.assertEqual(freeze["label_source"], "condition_argument_present")

    def test_rejects_audit_manifest_disagreement(self) -> None:
        self.audit["records"][0]["bundle_manifest_sha256"] = "wrong"
        write_json(self.root / self.paths["human_audit"], self.audit)
        with self.assertRaisesRegex(ValueError, "audit or split mismatch"):
            build(self.plan_path, self.root)


if __name__ == "__main__":
    unittest.main()
