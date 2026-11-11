"""Synthetic CPU capture, immutable publication, resume and freeze tests (spec 9/10)."""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_position_sweep_positions import (
    ACCOUNTS,
    CONFIG,
    SyntheticTokenizer,
    synthetic_pair,
    synthetic_prefix,
)

from goal_takeover.phase2.argument_recipient_672_runner import verify_runtime_freeze
from goal_takeover.phase2.position_sweep_capture import (
    capture_condition,
    capture_files,
    completed_bundle,
    create_runtime_freeze,
    write_bundle,
)
from goal_takeover.phase2.position_sweep_positions import verify_manifest
from goal_takeover.storage.run_writer import canonical_json_bytes, sha256_file


def synthetic_model():
    import torch

    class Backbone(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = torch.nn.Embedding(257, 4)
            self.layers = torch.nn.ModuleList([torch.nn.Identity(), torch.nn.Identity()])
            with torch.no_grad():
                self.embedding.weight.copy_(torch.arange(257)[:, None].expand(-1, 4))

        def forward(self, input_ids, **kwargs):
            hidden = self.embedding(input_ids)
            for layer in self.layers:
                hidden = layer(hidden)
            return SimpleNamespace(last_hidden_state=hidden)

    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.model = Backbone()
            self.lm_head = torch.nn.Linear(4, 257)
            self.calls = 0

        def forward(self, input_ids, use_cache=False, logits_to_keep=0):
            self.calls += 1
            assert not use_cache
            hidden = self.model(input_ids).last_hidden_state
            return SimpleNamespace(logits=self.lm_head(hidden[:, -logits_to_keep:]))

    return Model()


@unittest.skipUnless(
    importlib.util.find_spec("torch") and importlib.util.find_spec("safetensors"),
    "research extras unavailable",
)
class CaptureTest(unittest.TestCase):
    def test_single_pass_shape_order_and_probabilities(self):
        import torch

        model = synthetic_model()
        row = synthetic_pair()[0]
        spec = copy.deepcopy(CONFIG)
        spec["capture"]["top_k"] = 300
        result = capture_condition(
            model, SyntheticTokenizer(), row, synthetic_prefix(row), ACCOUNTS, spec
        )
        self.assertEqual(model.calls, 1)
        self.assertEqual(result["logit_method"], "logits_to_keep=3")
        for tensor in result["residuals"].values():
            self.assertEqual(tuple(tensor.shape), (1, 6, 4))
            self.assertEqual(tensor.dtype, torch.bfloat16)
            for index, p in enumerate(spec["capture"]["positions"]):
                self.assertEqual(
                    float(tensor[0, index, 0]), result["positions"]["positions"][p]["token_id"]
                )
        for p in ("S", "G", "D"):
            values = torch.tensor(result["logprobs"][p]["top_log_probabilities"])
            self.assertTrue(torch.isfinite(values).all())
            self.assertAlmostEqual(float(values.exp().sum()), 1.0, places=5)
        files = capture_files(row, result, {"status": "completed"}, spec, "prefix-sha")
        self.assertIn("residual.safetensors", files)
        self.assertEqual(json.loads(files["input.json"])["canonical_prefix_sha256"], "prefix-sha")

    def test_fallback_and_nonfinite_fail_closed(self):
        import torch

        model = synthetic_model()

        def fallback_forward(input_ids, use_cache=False):
            raise AssertionError("full vocabulary forward must be bypassed")

        model.forward = fallback_forward
        row = synthetic_pair()[0]
        result = capture_condition(
            model, SyntheticTokenizer(), row, synthetic_prefix(row), ACCOUNTS, CONFIG
        )
        self.assertEqual(result["logit_method"], "lm_head_last_three")
        with torch.no_grad():
            model.lm_head.weight.fill_(float("nan"))
        with self.assertRaisesRegex(ValueError, "logits"):
            capture_condition(
                model, SyntheticTokenizer(), row, synthetic_prefix(row), ACCOUNTS, CONFIG
            )
        # All hooks are removed even when forward raises.
        self.assertFalse(any(layer._forward_hooks for layer in model.model.layers))


class PublicationTest(unittest.TestCase):
    def test_manifest_resume_corruption_failure_and_atomicity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {"run.json": canonical_json_bytes({"status": "completed", "condition_id": "a"})}
            bundle = write_bundle(root, "synthetic", files)
            verify_manifest(bundle)
            self.assertTrue(completed_bundle(bundle, {"condition_id": "a"}))
            self.assertFalse(completed_bundle(root / "absent", {}))
            with self.assertRaises(FileExistsError):
                write_bundle(root, "synthetic", files)
            with self.assertRaises(ValueError):
                completed_bundle(bundle, {"condition_id": "b"})
            (bundle / "run.json").write_text("tampered")
            with self.assertRaises(ValueError):
                completed_bundle(bundle, {})
            with self.assertRaises(ValueError):
                write_bundle(root, "interrupted", {"../escape": b"x"})
            self.assertFalse((root / "runs/interrupted").exists())
            self.assertFalse(list((root / "runs").glob(".interrupted.tmp-*")))
            failure = write_bundle(
                root, "failed", {"run.json": canonical_json_bytes({"status": "technical_failure"})}
            )
            with self.assertRaisesRegex(ValueError, "new run ID"):
                completed_bundle(failure, {})

    def test_freeze_identity_and_existing_loader_compatibility(self):
        import goal_takeover.phase2.position_sweep_capture as capture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "artifacts").mkdir()
            for name in ("config.json", "spec.md", "design.json", "environment.lock"):
                (root / name).write_text("synthetic")
            sha = sha256_file(root / "config.json")
            report = {
                "git_commit": "synthetic-commit",
                "status": "passed",
                "analysis_config_sha256": sha,
                "spec_sha256": sha,
                "environment": {"synthetic": True},
            }
            reports = [Path(name) for name in ("tokenizer.json", "stem.json", "gpu.json")]
            for name in reports:
                (root / name).write_bytes(canonical_json_bytes(report))
            spec = {**CONFIG, "spec": "spec.md"}
            config = {
                "references": {"design_freeze": "design.json"},
                "model": {"name": "synthetic"},
            }
            with (
                patch.object(capture, "context", return_value=(root, spec, config)),
                patch.object(capture, "clean_commit", return_value="synthetic-commit"),
            ):
                output = create_runtime_freeze(
                    Path("config.json"), *reports, Path("environment.lock")
                )
                freeze = json.loads(output.read_text())
                with patch(
                    "goal_takeover.phase2.argument_recipient_672_runner._git_metadata",
                    return_value=("synthetic-commit", False),
                ):
                    verify_runtime_freeze(root, freeze, root / "design.json")
                with self.assertRaises(FileExistsError):
                    create_runtime_freeze(Path("config.json"), *reports, Path("environment.lock"))
                (root / reports[0]).write_bytes(
                    canonical_json_bytes({**report, "git_commit": "other"})
                )
                with self.assertRaisesRegex(ValueError, "commit/config/spec"):
                    create_runtime_freeze(Path("config.json"), *reports, Path("environment.lock"))
                with patch.object(capture, "clean_commit", side_effect=ValueError("dirty")):
                    with self.assertRaisesRegex(ValueError, "dirty"):
                        create_runtime_freeze(
                            Path("config.json"), *reports, Path("environment.lock")
                        )
            for metadata in (("other", False), ("synthetic-commit", True)):
                with patch(
                    "goal_takeover.phase2.argument_recipient_672_runner._git_metadata",
                    return_value=metadata,
                ):
                    with self.assertRaises(ValueError):
                        verify_runtime_freeze(root, freeze, root / "design.json")


@unittest.skipUnless(
    importlib.util.find_spec("torch") and importlib.util.find_spec("safetensors"),
    "research extras unavailable",
)
class CaptureLoopTest(unittest.TestCase):
    def test_resume_and_preserve_resource_or_model_failures(self):
        from contextlib import ExitStack

        import goal_takeover.phase2.position_sweep_capture as module

        for mode in ("completed", "time", "storage", "model"):
            with (
                self.subTest(mode=mode),
                tempfile.TemporaryDirectory() as directory,
                ExitStack() as stack,
            ):
                root = Path(directory)
                original = root / "artifacts/runs/original-c001"
                original.mkdir(parents=True)
                (original / "manifest.json").write_text("{}")
                (original / "prefix.json").write_text("{}")
                (root / "runtime.json").write_text("{}")
                spec = copy.deepcopy(CONFIG)
                if mode == "time":
                    spec["resources"]["maximum_seconds_per_condition"] = -1
                if mode == "storage":
                    spec["resources"]["maximum_total_storage_gib"] = 0
                row = {**synthetic_pair()[0], "pair_id": "pair"}
                config = {
                    "model": {
                        "name": "synthetic",
                        "max_context_tokens": 9999,
                        "tokenizer_revision": "synthetic",
                    },
                    "seed": 1,
                }
                freeze = {
                    "analysis_config_sha256": "cfg",
                    "spec_sha256": "spec",
                    "decoding": {"do_sample": False, "temperature": 0.0, "top_p": 1.0},
                }
                model = synthetic_model()
                model.config = SimpleNamespace(num_hidden_layers=2, hidden_size=4)
                stack.enter_context(
                    patch.object(
                        module,
                        "context",
                        return_value=(
                            root,
                            spec,
                            config,
                            [row],
                            {row["condition_id"]: "original-c001"},
                            ACCOUNTS,
                        ),
                    )
                )
                stack.enter_context(
                    patch.object(module, "verify_sweep_freeze", return_value=freeze)
                )
                stack.enter_context(
                    patch.object(module, "clean_commit", return_value="synthetic-commit")
                )
                loader = stack.enter_context(
                    patch.object(module, "load_model", return_value=(model, SyntheticTokenizer()))
                )
                stack.enter_context(
                    patch.object(
                        module, "canonical_prefix", return_value=(synthetic_prefix(row), row, {})
                    )
                )
                for name in ("reset_peak_memory_stats", "synchronize"):
                    stack.enter_context(patch("torch.cuda." + name))
                stack.enter_context(patch("torch.cuda.max_memory_allocated", return_value=0))
                if mode == "model":
                    loader.side_effect = RuntimeError("synthetic model load failure")
                if mode == "completed":
                    paths = module.capture(Path("config.json"), Path("runtime.json"))
                    self.assertEqual(len(paths), 1)
                    module.capture(Path("config.json"), Path("runtime.json"))
                    self.assertEqual(loader.call_count, 1)
                    self.assertEqual(model.calls, 1)
                else:
                    with self.assertRaisesRegex(RuntimeError, "retained technical failure"):
                        module.capture(Path("config.json"), Path("runtime.json"))
                    bundle = root / "artifacts/runs" / (spec["capture"]["run_id_prefix"] + "-c001")
                    verify_manifest(bundle)
                    self.assertEqual(
                        json.loads((bundle / "run.json").read_text())["status"], "technical_failure"
                    )
                    with self.assertRaisesRegex(ValueError, "new run ID"):
                        module.capture(Path("config.json"), Path("runtime.json"))

    def test_storage_ceiling_includes_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "including manifest"):
                write_bundle(root, "sized", {"run.json": b"{}"}, maximum_bytes=2)
            self.assertFalse((root / "runs/sized").exists())
