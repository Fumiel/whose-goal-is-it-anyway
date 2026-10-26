"""Immutable canonical capture bundle identity and checksum controls."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from goal_takeover.datasets.argument_recipient_672_collection import build_review_collection
from goal_takeover.instrumentation.capture import ActivationRecord
from goal_takeover.phase2.argument_recipient_672_bundle import write_canonical_capture_bundle
from goal_takeover.phase2.argument_recipient_672_capture import POSITION_RULE_VERSION
from goal_takeover.phase2.argument_recipient_672_features import load_canonical_features
from goal_takeover.schemas import AgentBoundary
from goal_takeover.serialization.prefix import build_serialized_prefix
from goal_takeover.storage.run_writer import sha256_file

DRAFT = json.loads(Path("data/templates/phase2_argument_recipient_672_draft.json").read_text())


@unittest.skipUnless(
    importlib.util.find_spec("torch") and importlib.util.find_spec("safetensors"),
    "capture dependencies are unavailable",
)
class CanonicalBundleTest(unittest.TestCase):
    def test_writes_once_with_exact_position_and_checksums(self) -> None:
        import torch

        declaration, split, _ = build_review_collection(DRAFT)
        condition = next(
            row
            for row in declaration["condition_specs"]
            if row["exposure"]["source_role"] == "user_instruction"
        )
        assignment = next(
            row for row in split["assignments"] if row["condition_id"] == condition["condition_id"]
        )
        prompt = condition["user_instruction"]
        prefix = build_serialized_prefix(
            boundary=AgentBoundary.USER_TO_ASSISTANT,
            text=prompt,
            token_ids=[11, 12],
            offset_mapping=[(0, 1), (1, len(prompt))],
            metadata={"serializer": "synthetic_fixture"},
        )
        position = {
            "position_rule_version": POSITION_RULE_VERSION,
            "name": "Tend_assistant",
            "source_role": condition["exposure"]["source_role"],
            "prefix_id": prefix.prefix_id,
            "boundary": prefix.boundary.value,
            "token_index": 1,
            "token_id": 12,
        }
        activation = ActivationRecord(
            prefix_id=prefix.prefix_id,
            token_ids=prefix.token_ids,
            positions=(1,),
            values={"model.layers.0": torch.tensor([[[1.0, 2.0]]])},
        )
        arguments = {
            "run_id": "synthetic-canonical-001",
            "condition": condition,
            "split": assignment["split"],
            "component_id": assignment["component_id"],
            "messages": ({"role": "user", "content": condition["user_instruction"]},),
            "prefix": prefix,
            "position": position,
            "activation": activation,
            "resolved_config": {
                "seed": 1,
                "decoding": {"do_sample": False, "temperature": 0.0, "top_p": 1.0},
                "model": {
                    "name": "synthetic",
                    "revision": "synthetic-model",
                    "tokenizer_revision": "synthetic-tokenizer",
                },
            },
            "provenance": {
                "git_commit": "synthetic-commit",
                "git_dirty": False,
                "design_freeze_sha256": "synthetic-design",
                "runtime_freeze_sha256": "synthetic-runtime",
                "model_revision": "synthetic-model",
                "tokenizer_revision": "synthetic-tokenizer",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = write_canonical_capture_bundle(artifact_root=root, **arguments)
            manifest = json.loads((path / "manifest.json").read_text())
            self.assertEqual(manifest["run_id"], arguments["run_id"])
            for artifact in manifest["artifacts"]:
                self.assertEqual(sha256_file(path / artifact["relative_path"]), artifact["sha256"])
            self.assertEqual(
                json.loads((path / "run.json").read_text())["outcome_flags"]["user_task_success"],
                None,
            )
            features, hashes = load_canonical_features(
                declaration,
                split,
                root / "runs",
                {condition["condition_id"]: arguments["run_id"]},
                layers=["model.layers.0"],
                design_freeze_sha256="synthetic-design",
                runtime_freeze_sha256="synthetic-runtime",
            )
            self.assertEqual(features["model.layers.0"][0].vector.tolist(), [1.0, 2.0])
            self.assertEqual(hashes[arguments["run_id"]], sha256_file(path / "manifest.json"))
            with self.assertRaises(FileExistsError):
                write_canonical_capture_bundle(artifact_root=root, **arguments)

    def test_rejects_unfrozen_or_wrong_position_before_writing(self) -> None:
        # The complete write path is covered above; this case verifies the
        # provenance gate directly without allocating a tensor.
        with self.assertRaises(ValueError):
            write_canonical_capture_bundle(
                artifact_root=Path("/tmp"),
                run_id="should-not-be-written",
                condition={
                    "split_candidate": "train",
                    "condition_id": "synthetic",
                    "user_instruction": "synthetic prompt",
                },
                split="train",
                component_id="component",
                messages=({"role": "user", "content": "synthetic prompt"},),
                prefix=None,
                position={},
                activation=None,
                resolved_config={},
                provenance={"git_dirty": True},
            )


if __name__ == "__main__":
    unittest.main()
