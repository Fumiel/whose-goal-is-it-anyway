"""Synthetic-only D-free controls, backward compatibility, provenance and execution gates."""

import copy
import importlib.util
import json
import tempfile
import unittest
from contextlib import ExitStack
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

from goal_takeover.phase2 import position_sweep_nod as nod
from goal_takeover.phase2.position_sweep_positions import (
    resolve_positions,
    verify_manifest,
)
from goal_takeover.storage.run_writer import canonical_json_bytes, sha256_file

NOD_CONFIG = json.loads(Path("configs/analysis/phase2_position_sweep_nod_v1.json").read_text())
NUMERICAL = importlib.util.find_spec("numpy") and importlib.util.find_spec("sklearn")
TORCH = importlib.util.find_spec("torch") and importlib.util.find_spec("safetensors")


class LayoutTest(unittest.TestCase):
    def test_remove_only_D_and_leave_reference_untouched(self):
        row = synthetic_pair()[0]
        original = resolve_positions(
            row, synthetic_prefix(row), ACCOUNTS, SyntheticTokenizer(), CONFIG
        )
        saved = copy.deepcopy(original)
        result = nod.nod_positions(original)
        self.assertEqual(original, saved)
        self.assertEqual(result["input_ids"], original["input_ids"][:-1])
        self.assertEqual(result["position_order"], list(nod.NOD_POSITIONS))
        self.assertNotIn("D", result["positions"])
        self.assertEqual(result["continuation_text"], CONFIG["capture"]["stem"] + "GB")
        for name in nod.NOD_POSITIONS:
            self.assertEqual(result["positions"][name], original["positions"][name])
        bad = copy.deepcopy(original)
        bad["positions"]["D"]["token_index"] -= 1
        with self.assertRaises(ValueError):
            nod.nod_positions(bad)
        for key in ("input_ids", "positions"):
            bad = copy.deepcopy(original)
            if key == "input_ids":
                bad[key][0] += 1
            else:
                bad[key]["A1"]["token_index"] += 1
            with self.assertRaises(ValueError):
                nod.require_matching_input(bad, original)

    def test_repeat_selection_is_five_complete_pairs_and_order_independent(self):
        rows = []
        for task in reversed(range(7)):
            rows += [
                {**r, "draft_task_id": str(task), "condition_id": f"{task}-{r['condition_id']}"}
                for r in synthetic_pair()
            ]
        ids = nod.repeat_condition_ids(rows)
        self.assertEqual(len(ids), 10)
        self.assertEqual(ids, nod.repeat_condition_ids(list(reversed(rows))))
        self.assertEqual({v.split("-")[0] for v in ids}, set("01234"))
        with self.assertRaises(ValueError):
            nod.repeat_condition_ids([r for r in rows if r["condition_id"] != "0-0"])
        with self.assertRaises(ValueError):
            nod.repeat_condition_ids([{**rows[0], "split_candidate": "validation"}, *rows[1:]])

    def test_configuration_and_changed_reanalysis_settings(self):
        self.assertEqual(
            NOD_CONFIG["reference"]["gpu_preflight_report"],
            "artifacts/phase2-position-sweep-gpu-preflight-67c5492.json",
        )
        settings = nod.reanalysis_settings(CONFIG["analysis"], "new-output")
        expected = copy.deepcopy(CONFIG["analysis"])
        expected.update(report_only_positions=[], output_id="new-output")
        self.assertEqual(settings, expected)
        bad = {**settings, "seed": 1}
        with self.assertRaises(ValueError):
            nod.reanalysis_settings(CONFIG["analysis"], "new-output", bad)

    def test_classification_changes_only_use_five_classes_and_mapping_rule(self):
        old = {
            "position_classifications": {p: {"class": "R1"} for p in nod.NOD_POSITIONS},
            "hypothesis_mapping": {"mapping": "H1_consistent", "rule": 3},
        }
        self.assertEqual(
            nod.classify_reanalysis(old, copy.deepcopy(old))["d_effect"], "2_numeric_only"
        )
        for field in ("position", "rule", "mapping"):
            new = copy.deepcopy(old)
            if field == "position":
                new["position_classifications"]["T"]["class"] = "R2"
            else:
                new["hypothesis_mapping"][field] = 99
            self.assertEqual(
                nod.classify_reanalysis(old, new)["d_effect"], "3_classification_changed"
            )

    def test_noise_never_licenses_skipping_reanalysis(self):
        cell = {"count": 10, "bit_exact_count": 10, "relative_l2": {"maximum": 0.0}}
        repeat = {"A1/model.layers.0": copy.deepcopy(cell)}
        values = {"A1/model.layers.0": {**cell, "count": 240, "bit_exact_count": 240}}
        self.assertFalse(nod.comparison_gate(repeat, values)["reanalysis_required"])
        values["A1/model.layers.0"]["bit_exact_count"] = 239
        self.assertTrue(nod.comparison_gate(repeat, values)["reanalysis_required"])
        repeat["A1/model.layers.0"].update(bit_exact_count=9, relative_l2={"maximum": 0.01})
        for width in (0.001, 0.01, 0.1):
            values["A1/model.layers.0"]["relative_l2"]["maximum"] = width
            result = nod.comparison_gate(repeat, values)
            self.assertEqual(result["reproducibility"], "R-NOISE")
            self.assertTrue(result["reanalysis_required"])


@unittest.skipUnless(NUMERICAL, "numerical extras unavailable")
class AnalysisTest(unittest.TestCase):
    def test_legacy_json_and_five_position_results_match(self):
        from test_position_sweep_analysis import NumericalTest

        from goal_takeover.phase2.position_sweep_analysis import analyze

        args = NumericalTest.data()
        original = analyze(*args)
        self.assertEqual(
            canonical_json_bytes(original),
            Path("tests/fixtures/position_sweep_nod_legacy_analysis.json").read_bytes(),
        )
        result = analyze(*args, position_names=nod.NOD_POSITIONS)
        expected = copy.deepcopy(original)
        for section in ("cells", "series_held_out"):
            expected[section] = {
                k: v for k, v in expected[section].items() if not k.startswith("D/")
            }
        for section in ("positive_control_auroc", "specificity_control"):
            expected[section].pop("D")
        self.assertEqual(result, expected)
        self.assertEqual(result["null_maxima"], original["null_maxima"])

    def test_delta_zero_exclusion_and_label_recovery(self):
        import numpy as np
        from test_position_sweep_analysis import NumericalTest

        rows, features, *_, accounts, spec = NumericalTest.data()
        # A zero cell and a signal cell; the null must include only the nonzero probes.
        features["A1"][24][:] = 0
        spec = {**spec, "judged_layers": {"A1": [24], "T": [24]}}
        comparison = {"delta_probe_seed": spec["seed"], "permutation_repeats": 26}
        result = nod.delta_label_readout(rows, features, accounts, spec, comparison)
        self.assertTrue(result["reported_only"])
        self.assertEqual(result["computed_cell_count"], 2)
        self.assertEqual(result["cells"]["A1/layer24/logistic"]["status"], "no_difference")
        self.assertEqual(result["cells"]["T/layer24/logistic"]["paired_accuracy"], 1.0)
        self.assertLess(result["cells"]["T/layer24/logistic"]["family_wise_p"], 0.05)
        self.assertEqual(
            result, nod.delta_label_readout(rows, features, accounts, spec, comparison)
        )
        for p in features:
            features[p][24] = np.zeros_like(features[p][24])
        result = nod.delta_label_readout(rows, features, accounts, spec, comparison)
        self.assertEqual(result["computed_cell_count"], 0)
        self.assertEqual(result["null_maxima"], [])


@unittest.skipUnless(TORCH, "torch extras unavailable")
class ForwardAndComparisonTest(unittest.TestCase):
    def test_forward_wrapper_matches_legacy_and_supports_two_positions(self):
        import torch
        from test_position_sweep_capture import synthetic_model

        from goal_takeover.phase2.position_sweep_capture import capture_condition

        torch.manual_seed(71)
        model = synthetic_model()
        row = synthetic_pair()[0]
        result = capture_condition(
            model, SyntheticTokenizer(), row, synthetic_prefix(row), ACCOUNTS, CONFIG
        )
        serial = {
            **result,
            "residuals": {k: v.float().tolist() for k, v in result["residuals"].items()},
        }
        self.assertEqual(
            canonical_json_bytes(serial),
            Path("tests/fixtures/position_sweep_nod_legacy_capture.json").read_bytes(),
        )
        two = nod.capture_resolved(model, nod.nod_positions(result["positions"]), CONFIG)
        self.assertEqual(tuple(two["residuals"]["model.layers.0"].shape), (1, 5, 4))
        self.assertEqual(set(two["logprobs"]), {"S", "G"})
        self.assertIn("gb_log_probability", two["logprobs"]["S"])
        bad = copy.deepcopy(two["positions"])
        bad["positions"]["S"]["token_index"] -= 1
        with self.assertRaises(ValueError):
            nod.capture_resolved(model, bad, CONFIG)

    def test_bit_exact_signed_zero_metrics_and_name_alignment(self):
        import torch

        a = torch.tensor([3.0, 4.0], dtype=torch.bfloat16)
        b = torch.tensor([0.0, 4.0], dtype=torch.bfloat16)
        self.assertEqual(nod.compare_vectors(a, a)["relative_l2"], 0.0)
        diff = nod.compare_vectors(a, b)
        self.assertEqual(diff["relative_l2"], 0.75)
        self.assertEqual(diff["max_absolute"], 3.0)
        self.assertFalse(
            nod.compare_vectors(
                torch.tensor([0.0], dtype=torch.bfloat16),
                torch.tensor([-0.0], dtype=torch.bfloat16),
            )["bit_exact"]
        )
        ta = {"layer": a[None, :, None]}
        tb = {"layer": a.flip(0)[None, :, None]}
        self.assertTrue(
            nod.compare_position(ta, ["A1", "A2"], tb, ["A2", "A1"], "A1", "layer")["bit_exact"]
        )
        for invalid in (torch.tensor([float("nan"), 1.0], dtype=torch.bfloat16), a.float(), a[:1]):
            with self.assertRaises(ValueError):
                nod.compare_vectors(invalid, a)


def synthetic_plan(root: Path) -> dict:
    """Test-only, two-layer model and five task pairs; no research inputs."""
    import torch
    from test_position_sweep_capture import synthetic_model

    model = synthetic_model()
    model.config = SimpleNamespace(num_hidden_layers=2, hidden_size=4)
    tokenizer = SyntheticTokenizer()
    sweep = copy.deepcopy(CONFIG)
    sweep["analysis"]["report_layers"] = [0, 1]
    config = {
        "model": {
            "name": "synthetic",
            "tokenizer_revision": "synthetic",
            "max_context_tokens": 9999,
        },
        "seed": 1,
        "references": {"design_freeze": "design.json"},
    }
    spec = copy.deepcopy(NOD_CONFIG)
    spec["spec"] = "spec.md"
    spec["sweep_config"] = "sweep.json"
    (root / "design.json").write_text("{}")
    (root / "runtime.json").write_text("{}")
    (root / "cfg.json").write_text("{}")
    (root / "spec.md").write_text("synthetic")
    (root / "sweep.json").write_text("{}")
    identity = {
        "git_commit": "new-commit",
        "analysis_config_sha256": sha256_file(root / "cfg.json"),
        "spec_sha256": sha256_file(root / "spec.md"),
        "sweep_config_sha256": sha256_file(root / "sweep.json"),
        "reference_sha256": {key: "synthetic" for key in nod.REFERENCE_FILES},
    }
    plan = {
        "root": root,
        "nod": spec,
        "sweep": sweep,
        "config": config,
        "config_path": Path("cfg.json"),
        "config_sha256": identity["analysis_config_sha256"],
        "spec_sha256": identity["spec_sha256"],
        "sweep_config_sha256": identity["sweep_config_sha256"],
        "accounts": ACCOUNTS,
        "runtime": "runtime.json",
        "runtime_sha256": sha256_file(root / "runtime.json"),
        "rows": [],
        "run_ids": {},
        "reference_rows": {},
        "reference": {
            "sha256": identity["reference_sha256"],
            "runtime": {
                "git_commit": "old-commit",
                "analysis_config_sha256": "old-config",
                "spec_sha256": "old-spec",
            },
        },
        "freeze": {
            **identity,
            "files_sha256": {"synthetic-lock": "synthetic"},
            "decoding": {"do_sample": False, "temperature": 0.0, "top_p": 1.0},
        },
    }
    for task in range(5):
        for base in synthetic_pair():
            index = len(plan["rows"]) + 1
            row = {
                **base,
                "draft_task_id": str(task),
                "condition_id": str(index),
                "pair_id": str(task),
            }
            plan["rows"].append(row)
            cid = f"canonical-c{index:03d}"
            plan["run_ids"][row["condition_id"]] = cid
            prefix = synthetic_prefix(row)
            canonical = nod.write_bundle(
                root / "artifacts",
                cid,
                {
                    "prefix.json": canonical_json_bytes(prefix),
                    "run.json": b"{}",
                    "residual.safetensors": __import__("safetensors.torch", fromlist=["save"]).save(
                        {
                            f"model.layers.{layer}": torch.zeros(1, 1, 4, dtype=torch.bfloat16)
                            for layer in range(2)
                        }
                    ),
                },
            )
            resolved = resolve_positions(row, prefix, ACCOUNTS, tokenizer, sweep)
            result = nod.capture_resolved(model, resolved, sweep)
            rid = nod.run_id(spec["reference"]["capture_run_id_prefix"], cid)
            run = {
                "run_id": rid,
                "condition_id": row["condition_id"],
                "pair_id": row["pair_id"],
                "status": "completed",
                "split": "train",
                "git_dirty": False,
                "git_commit": "old-commit",
                "runtime_freeze_sha256": "synthetic",
                "analysis_config_sha256": "old-config",
                "spec_sha256": "old-spec",
                "canonical_run_id": cid,
                "canonical_manifest_sha256": sha256_file(canonical / "manifest.json"),
                "model": config["model"],
                "tokenizer_revision": "synthetic",
                "model_dimensions": {"num_hidden_layers": 2, "hidden_size": 4},
            }
            reference = nod.write_bundle(
                root / "artifacts",
                rid,
                nod.capture_files(row, result, run, {}, sha256_file(canonical / "prefix.json")),
            )
            plan["reference_rows"][rid] = {
                "manifest_sha256": sha256_file(reference / "manifest.json")
            }
    plan["repeat_ids"] = nod.repeat_condition_ids(plan["rows"])
    return plan


@unittest.skipUnless(TORCH, "torch extras unavailable")
class PipelineTest(unittest.TestCase):
    def setup_patches(self, stack, plan):
        from test_position_sweep_capture import synthetic_model

        model = synthetic_model()
        model.config = SimpleNamespace(num_hidden_layers=2, hidden_size=4)
        stack.enter_context(patch.object(nod, "load_plan", return_value=plan))
        stack.enter_context(patch.object(nod, "clean_commit", return_value="new-commit"))
        stack.enter_context(
            patch.object(
                nod,
                "canonical_prefix",
                side_effect=lambda root, cid, row, spec: (
                    synthetic_prefix(row),
                    row,
                    verify_manifest(root / "artifacts/runs" / cid),
                ),
            )
        )
        loader = stack.enter_context(
            patch.object(nod, "load_model", return_value=(model, SyntheticTokenizer()))
        )
        for name in ("synchronize", "reset_peak_memory_stats"):
            stack.enter_context(patch("torch.cuda." + name))
        stack.enter_context(patch("torch.cuda.max_memory_allocated", return_value=0))
        return loader

    def test_capture_repeat_first_resume_and_verified_collection(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            plan = synthetic_plan(Path(directory))
            loader = self.setup_patches(stack, plan)
            paths = nod.capture_nod(Path("cfg.json"), Path("runtime.json"))
            kinds = [json.loads((p / "run.json").read_text())["capture_kind"] for p in paths]
            self.assertEqual(kinds, ["repeat"] * 10 + ["nod"] * 10)
            self.assertEqual(len(paths), 20)
            self.assertEqual(loader.call_count, 1)
            self.assertEqual(paths, nod.capture_nod(Path("cfg.json"), Path("runtime.json")))
            self.assertEqual(loader.call_count, 1)
            records = nod.load_records(plan)
            self.assertEqual(records[0]["nod"]["tensors"]["model.layers.0"].shape[1], 5)
            self.assertEqual(records[0]["repeat"]["tensors"]["model.layers.0"].shape[1], 6)
            manifest = nod.write_collection_manifest(
                Path("cfg.json"), Path("runtime.json"), Path("collection.json")
            )
            self.assertEqual(len(json.loads(manifest.read_text())["runs"]), 20)
            (paths[0] / "input.json").write_text("{}")
            with self.assertRaises(ValueError):
                nod.capture_nod(Path("cfg.json"), Path("runtime.json"))

    def test_failure_bundle_and_input_drift_stop(self):
        for mode in ("memory", "model", "positions"):
            with (
                self.subTest(mode=mode),
                tempfile.TemporaryDirectory() as directory,
                ExitStack() as stack,
            ):
                plan = synthetic_plan(Path(directory))
                loader = self.setup_patches(stack, plan)
                if mode == "memory":
                    plan["nod"]["resources"]["maximum_gpu_memory_gib"] = -1
                elif mode == "model":
                    loader.side_effect = RuntimeError("synthetic model failure")
                else:
                    stack.enter_context(
                        patch.object(
                            nod,
                            "resolve_positions",
                            side_effect=ValueError("synthetic input drift"),
                        )
                    )
                with self.assertRaisesRegex(RuntimeError, "retained technical failure"):
                    nod.capture_nod(Path("cfg.json"), Path("runtime.json"))
                failures = list(
                    (Path(directory) / "artifacts/runs").glob("argrec672-v1-ps-003-*/run.json")
                )
                self.assertEqual(len(failures), 1)
                self.assertEqual(json.loads(failures[0].read_text())["status"], "technical_failure")
                with self.assertRaises(ValueError):
                    nod.capture_nod(Path("cfg.json"), Path("runtime.json"))

    def test_freeze_status_commit_reference_and_no_overwrite(self):
        from goal_takeover.phase2.argument_recipient_672_runner import verify_runtime_freeze

        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            plan = synthetic_plan(Path(directory))
            self.setup_patches(stack, plan)
            root = plan["root"]
            identity = nod.report_identity(plan)
            for filename in ("tokenizer.json", "gpu.json"):
                (root / filename).write_bytes(
                    canonical_json_bytes(
                        {**identity, "status": "passed", "environment": {"synthetic": True}}
                    )
                )
            (root / "environment.lock").write_text("synthetic")
            args = (
                Path("cfg.json"),
                Path("tokenizer.json"),
                Path("gpu.json"),
                Path("environment.lock"),
            )
            path = nod.create_nod_runtime_freeze(*args, Path("freeze.json"))
            with patch(
                "goal_takeover.phase2.argument_recipient_672_runner._git_metadata",
                return_value=("new-commit", False),
            ):
                verify_runtime_freeze(root, json.loads(path.read_text()), root / "design.json")
            with self.assertRaises(FileExistsError):
                nod.create_nod_runtime_freeze(*args, Path("freeze.json"))
            for field in ("git_commit", "reference_sha256", "status"):
                bad = {**identity, "status": "passed", "environment": {}}
                bad[field] = "wrong"
                (root / "gpu.json").write_bytes(canonical_json_bytes(bad))
                with self.assertRaises(ValueError):
                    nod.create_nod_runtime_freeze(*args, Path("other.json"))
            with patch.object(nod, "clean_commit", side_effect=ValueError("dirty")):
                with self.assertRaises(ValueError):
                    nod.create_nod_runtime_freeze(*args, Path("other.json"))

    def test_reanalysis_gate_and_existing_output_stop_before_fit(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            plan = synthetic_plan(Path(directory))
            self.setup_patches(stack, plan)
            stack.enter_context(
                patch.object(
                    nod,
                    "load_comparison",
                    return_value=({"report": {"reanalysis_required": False}}, Path("comparison")),
                )
            )
            fit = stack.enter_context(
                patch.object(nod, "analyze", side_effect=AssertionError("must not fit"))
            )
            with self.assertRaisesRegex(ValueError, "not required"):
                nod.run_reanalysis(Path("cfg.json"), Path("runtime.json"))
            output = plan["root"] / "artifacts/processed" / plan["nod"]["reanalysis"]["output_id"]
            output.mkdir(parents=True)
            with self.assertRaises(FileExistsError):
                nod.run_reanalysis(Path("cfg.json"), Path("runtime.json"))
            self.assertEqual(fit.call_count, 0)

    def test_read_bundle_rejects_freeze_condition_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = synthetic_plan(Path(directory))
            row = plan["rows"][0]
            cid = plan["run_ids"][row["condition_id"]]
            prefix = synthetic_prefix(row)
            nod.read_bundle(plan, row, prefix, cid, "reference")
            plan["reference"]["sha256"]["runtime_freeze"] = "wrong"
            with self.assertRaises(ValueError):
                nod.read_bundle(plan, row, prefix, cid, "reference")
            with self.assertRaises(ValueError):
                nod.read_bundle(
                    plan, {**row, "split_candidate": "validation"}, prefix, cid, "reference"
                )


class ReferenceTest(unittest.TestCase):
    def test_four_reference_files_and_old_GPU_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sweep.json").write_text("{}")
            (root / "sweep-spec.md").write_text("synthetic")
            (root / "gpu.json").write_text("{}")
            model = {"name": "synthetic"}
            runtime = {
                "status": "frozen",
                "git_commit": "old",
                "model": model,
                "analysis_config_sha256": sha256_file(root / "sweep.json"),
                "spec_sha256": sha256_file(root / "sweep-spec.md"),
                "files_sha256": {"gpu.json": sha256_file(root / "gpu.json")},
            }
            (root / "runtime.json").write_bytes(canonical_json_bytes(runtime))
            sha = sha256_file(root / "runtime.json")
            (root / "collection.json").write_bytes(
                canonical_json_bytes({"git_commit": "old", "runtime_freeze_sha256": sha})
            )
            from goal_takeover.phase2.argument_recipient_672_train_readout import publish

            publish(
                root / "derived",
                {
                    "report.json": canonical_json_bytes(
                        {"provenance": {"runtime_freeze_sha256": sha}}
                    )
                },
                kind="position_sweep",
            )
            spec = {
                "sweep_config": "sweep.json",
                "reference": {
                    "runtime_freeze": "runtime.json",
                    "collection_manifest": "collection.json",
                    "analysis_report": "derived/report.json",
                    "gpu_preflight_report": "gpu.json",
                },
            }
            result = nod.verify_reference_files(
                root, spec, {"spec": "sweep-spec.md"}, {"model": model}
            )
            self.assertEqual(len(result["sha256"]), 4)
            (root / "gpu.json").write_text("changed")
            with self.assertRaisesRegex(ValueError, "reference"):
                nod.verify_reference_files(root, spec, {"spec": "sweep-spec.md"}, {"model": model})
