"""Frozen design/runtime identity checks before 672 model loading."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from goal_takeover.phase2.argument_recipient_672_runner import load_frozen_plan
from goal_takeover.storage.run_writer import sha256_file

ROOT = Path(__file__).resolve().parents[1]
FREEZE = "data/manifests/phase2_argument_recipient_672_v1.freeze.json"


@unittest.skipUnless(importlib.util.find_spec("yaml"), "YAML dependency is unavailable")
class FrozenRunnerPlanTest(unittest.TestCase):
    def test_accepts_matching_temp_copy_and_rejects_checksum_drift(self) -> None:
        freeze = json.loads((ROOT / FREEZE).read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in [*freeze["files_sha256"], FREEZE]:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            runtime = root / "artifacts/phase2-argument-recipient-672-runtime.freeze.json"
            runtime.parent.mkdir(parents=True, exist_ok=True)
            runtime_checked_file = "artifacts/synthetic-environment.lock"
            (root / runtime_checked_file).write_text("synthetic environment\n")
            runtime.write_text(
                json.dumps(
                    {
                        "status": "frozen",
                        "git_commit": "synthetic-commit",
                        "design_freeze_sha256": sha256_file(root / FREEZE),
                        "files_sha256": {
                            runtime_checked_file: sha256_file(root / runtime_checked_file)
                        },
                    }
                )
            )
            config = root / "configs/experiments/phase2_argument_recipient_672_v1.yaml"
            with patch(
                "goal_takeover.phase2.argument_recipient_672_runner._git_metadata",
                return_value=("synthetic-commit", False),
            ):
                _, declaration, split = load_frozen_plan(config)
                self.assertEqual(len(declaration["condition_specs"]), 672)
                self.assertEqual(len(split["assignments"]), 672)
                alternate = root / "artifacts/alternate-runtime.freeze.json"
                shutil.copyfile(runtime, alternate)
                overridden, _, _ = load_frozen_plan(
                    config,
                    runtime_freeze_override=Path("artifacts/alternate-runtime.freeze.json"),
                )
                self.assertEqual(
                    overridden["_resolved_runtime_freeze_path"],
                    "artifacts/alternate-runtime.freeze.json",
                )
                (root / runtime_checked_file).write_text("tampered")
                with self.assertRaisesRegex(ValueError, "runtime checksum differs"):
                    load_frozen_plan(config)
                (root / runtime_checked_file).write_text("synthetic environment\n")
                with (root / "data/splits/phase2_argument_recipient_672_v1.json").open(
                    "a"
                ) as stream:
                    stream.write(" ")
                with self.assertRaisesRegex(ValueError, "design checksum differs"):
                    load_frozen_plan(config)


if __name__ == "__main__":
    unittest.main()
