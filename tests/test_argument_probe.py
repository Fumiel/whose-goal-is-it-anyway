"""Synthetic-only checks for aligned recipient feature and probe processing."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np
    from safetensors.numpy import save
except ModuleNotFoundError:  # Research extras are optional for the fast system-Python suite.
    np = None
    save = None

from goal_takeover.phase2.argument_probe import (
    extract_features,
    fit_and_evaluate,
    run,
    score_saved_probe,
)
from goal_takeover.storage.run_writer import ImmutableRunWriter


@unittest.skipUnless(np is not None and save is not None, "research extras are not installed")
class ArgumentProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.spec = {
            "status": "synthetic_fixture",
            "missing_policy": "exclude_with_reason",
            "candidate_values": {"v1": "ACCOUNT-A", "v2": "ACCOUNT-B"},
            "feature_specs": [
                {
                    "feature_id": "last_l0",
                    "layer": "layer0",
                    "boundary": "user_to_assistant",
                    "position_name": "Tend_assistant",
                    "position_rule_version": "synthetic_v1",
                }
            ],
            "fit": {
                "regularization_c": [1.0],
                "max_iter": 500,
                "seed": 3,
                "calibration_bins": 5,
                "random_label_repeats": 5,
                "cluster_bootstrap_repeats": 20,
            },
            "conditions": [],
        }

    def _bundle(
        self,
        index: int,
        *,
        split: str,
        label: int,
        reference: bool = True,
        exposure: bool = True,
        wrong_token: bool = False,
        wrong_shape: bool = False,
    ) -> None:
        condition_id = f"condition-{index}"
        run_id = f"run-{index}"
        account = "ACCOUNT-A" if label else "ACCOUNT-B"
        prompt = f"Pay {account}."
        if reference:
            prompt += " Receipt copy ACCOUNT-B." if label else " Receipt copy ACCOUNT-A."
        captured_text = prompt if exposure else f"Read the document. {prompt}"
        token_ids = [31, 32] if exposure else [31, 32, 33]
        labels = {"v1": label, "v2": 1 - label}
        condition = {
            "condition_id": condition_id,
            "run_id": run_id,
            "split": split,
            "component_id": f"{split}-component",
            "task_template_id": f"{split}-task",
            "user_instruction": prompt,
            "argument_present": labels,
        }
        self.spec["conditions"].append(condition)
        positions = {
            "position_rule_version": "synthetic_v1",
            "positions": [
                {"name": "Tend_assistant", "token_index": 1, "token_id": 99 if wrong_token else 32}
            ],
        }
        prefix = {
            "prefix_id": f"prefix-{index}",
            "boundary": "user_to_assistant",
            "text": captured_text,
            "token_ids": token_ids,
            "offsets": [
                {"token_index": 0, "token_id": 31, "start": 0, "end": 4},
                {
                    "token_index": 1,
                    "token_id": 32,
                    "start": 4,
                    "end": len(captured_text) if exposure else 18,
                },
                *(
                    []
                    if exposure
                    else [
                        {"token_index": 2, "token_id": 33, "start": 18, "end": len(captured_text)}
                    ]
                ),
            ],
        }
        tensor = np.asarray([[[0.0, 0.0], [float(label * 2 - 1), float(index)]]], dtype=np.float32)
        if wrong_shape:
            tensor = tensor[:, :1, :]
        activation = {
            "prefix_id": prefix["prefix_id"],
            "token_ids": token_ids,
            "positions": [0, 1],
            "layers": {"layer0": {"shape": [1, 2, 2], "dtype": "torch.float32"}},
        }
        measurement = {"scope": "actual", "prefix_id": prefix["prefix_id"], "positions": positions}
        with ImmutableRunWriter(self.root, run_id) as writer:
            writer.write_json(
                "run.json",
                {
                    "run_id": run_id,
                    "condition_id": condition_id,
                    "status": "completed",
                    "split": split,
                    "group_id": condition["component_id"],
                    "measurements": [measurement],
                },
                kind="run_record",
            )
            writer.write_json("condition.json", condition, kind="condition")
            writer.write_json("prefixes.json", [prefix], kind="prefix_records")
            writer.write_json(
                "measurements/0/activation.json", activation, kind="activation_metadata"
            )
            writer.write_bytes(
                "measurements/0/residual.safetensors",
                save({"layer0": tensor}),
                kind="residual_activation",
            )
            writer.commit()

    def _complete(self) -> None:
        for index in range(8):
            self._bundle(index, split="train" if index < 4 else "validation", label=index % 2)

    def test_aligned_extraction_and_train_only_fit(self) -> None:
        self._complete()
        rows, missing, manifests = extract_features(self.spec, self.root / "runs")
        self.assertEqual(missing, [])
        self.assertEqual(len(manifests), 8)
        self.assertEqual(len(rows["last_l0"]), 8)
        self.assertEqual(rows["last_l0"][0].lexical_presence, {"v1": 1, "v2": 1})
        report, models = fit_and_evaluate(self.spec, rows)
        self.assertEqual(report["features"]["last_l0"]["train_count"], 4)
        self.assertEqual(models["last_l0"][("v1", "1.0")]["standardscaler"].mean_[1], 1.5)
        metric = report["features"]["last_l0"]["candidates"]["v1"]["by_c"]["1.0"]["validation"]
        self.assertEqual(metric["auc_lexical_present"], 1.0)
        spec_path = self.root / "spec.json"
        spec_path.write_text(json.dumps(self.spec), encoding="utf-8")
        output = self.root / "processed"
        result = run(spec_path, self.root / "runs", output)
        self.assertFalse(result["research_result"])
        self.assertTrue((output / "probe_parameters.npz").is_file())
        saved_score = score_saved_probe(
            output / "probe_parameters.npz",
            feature_id="last_l0",
            candidate="v1",
            c="1.0",
            vector=rows["last_l0"][4].vector,
        )
        expected_score = models["last_l0"][("v1", "1.0")].decision_function(
            rows["last_l0"][4].vector.reshape(1, -1)
        )[0]
        self.assertAlmostEqual(saved_score, expected_score)
        self.assertTrue(
            result["features"]["last_l0"]["candidates"]["v1"]["by_c"]["1.0"]["validation"][
                "calibration_bins"
            ]
        )
        with self.assertRaises(FileExistsError):
            run(spec_path, self.root / "runs", output)

    def test_missing_exposure_is_recorded(self) -> None:
        self._bundle(0, split="train", label=1, exposure=False)
        self._bundle(1, split="validation", label=0)
        rows, missing, _ = extract_features(self.spec, self.root / "runs")
        self.assertEqual(len(rows["last_l0"]), 1)
        self.assertEqual(missing[0]["reason"], "positive_argument_not_yet_exposed")

    def test_token_shape_and_condition_alignment_fail(self) -> None:
        self._bundle(0, split="train", label=1, wrong_token=True)
        self._bundle(1, split="validation", label=0)
        with self.assertRaisesRegex(ValueError, "selected token identity"):
            extract_features(self.spec, self.root / "runs")

        # A separate temporary fixture tests the tensor shape check.
        self.spec["conditions"].clear()
        self._bundle(2, split="train", label=1, wrong_shape=True)
        self._bundle(3, split="validation", label=0)
        with self.assertRaisesRegex(ValueError, "residual shape"):
            extract_features(self.spec, self.root / "runs")
        self.spec["conditions"][0]["argument_present"]["v1"] = 0
        with self.assertRaisesRegex(ValueError, "condition label or prompt"):
            extract_features(self.spec, self.root / "runs")

    def test_split_leakage_rejected(self) -> None:
        self._complete()
        self.spec["conditions"][4]["component_id"] = "train-component"
        with self.assertRaisesRegex(ValueError, "component_id crosses"):
            extract_features(self.spec, self.root / "runs")

    def test_checksum_and_deterministic_controls(self) -> None:
        self._complete()
        rows, _, _ = extract_features(self.spec, self.root / "runs")
        first, _ = fit_and_evaluate(self.spec, rows)
        second, _ = fit_and_evaluate(self.spec, rows)
        self.assertEqual(first, second)
        path = self.root / "runs/run-0/condition.json"
        path.write_text(
            path.read_text(encoding="utf-8").replace("condition-0", "condition-X"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            extract_features(self.spec, self.root / "runs")


if __name__ == "__main__":
    unittest.main()
