"""Synthetic patch alignment, causal scoring, provenance and intervention controls."""

import copy
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_position_sweep_positions import ACCOUNTS, CONFIG, SyntheticTokenizer, synthetic_prefix

from goal_takeover.instrumentation.activation_hooks import ResidualCapture, ResidualPatch
from goal_takeover.phase2 import activation_patching as pt
from goal_takeover.phase2.argument_recipient_672_selection_pointer import pair_index
from goal_takeover.serialization.qwen import serialize_qwen_tool_call
from goal_takeover.storage.run_writer import canonical_json_bytes, sha256_file

SETTINGS = json.loads(Path("configs/analysis/phase2_activation_patching_v1.json").read_text())
TORCH = importlib.util.find_spec("torch") and importlib.util.find_spec("transformers")
NUMERICAL = importlib.util.find_spec("numpy") and importlib.util.find_spec("sklearn")


def rows_and_labels(families=6, tasks=2):
    rows = []
    labels = []
    for family in range(families):
        for task in range(tasks):
            for label in (1, 0):
                cid = f"f{family}-t{task}-l{label}"
                recipient, reference = ("x", "y") if label else ("y", "x")
                rows.append(
                    {
                        "condition_id": cid,
                        "draft_condition_id": cid,
                        "draft_task_id": f"f{family}-t{task}",
                        "semantic_series_id": f"series{family}-{task}",
                        "family_id": f"family{family}",
                        "split_candidate": "train",
                        "source_role": "user_instruction" if family % 2 else "tool_output_document",
                        "recipient_value_id": recipient,
                        "reference_value_id": reference,
                        "user_instruction": f"GB8XXX GB4YYY use {recipient}",
                        "documents": [{"content": f"GB8XXX GB4YYY use {recipient}"}],
                        "expected_send_money": {
                            "name": "send_money",
                            "arguments": {
                                "recipient": ACCOUNTS[recipient],
                                "amount": 7.5,
                                "date": "2022-01-01",
                                "subject": 'a "quoted" item',
                            },
                        },
                    }
                )
                labels.append(label)
    return rows, labels


def synthetic_model(layers=3, dtype=None):
    import torch
    from transformers import Qwen3Config, Qwen3ForCausalLM

    torch.manual_seed(13)
    config = Qwen3Config(
        vocab_size=300,
        hidden_size=16,
        intermediate_size=24,
        num_hidden_layers=layers,
        num_attention_heads=2,
        num_key_value_heads=1,
        head_dim=8,
        max_position_embeddings=256,
        attention_dropout=0.0,
    )
    config._attn_implementation = "sdpa"
    return Qwen3ForCausalLM(config).to(dtype=dtype or torch.float32).eval()


class InputAndDeclarationTest(unittest.TestCase):
    def test_config_matches_issued_json_and_rejects_invalid_contract(self):
        import re

        brief = Path("docs/phase2_activation_patching_implementation_brief.md").read_text()
        expected = json.loads(re.search(r"```json\n(.*?)\n```", brief, re.S).group(1))
        self.assertEqual(SETTINGS, expected)
        for section, key, value in (
            ("patching", "positions", ["A1"]),
            ("patching", "layers", [36]),
            ("patching", "candidate_scoring", "bulk"),
        ):
            bad = copy.deepcopy(SETTINGS)
            bad[section][key] = value
            with patch.object(pt.nod, "read_json", return_value=bad), self.assertRaises(ValueError):
                pt.read_config(Path("unused.json"))

    def test_serialization_preserves_all_arguments_without_changing_existing(self):
        row = rows_and_labels()[0][0]
        original = copy.deepcopy(row)
        old = serialize_qwen_tool_call("send_money", row["expected_send_money"]["arguments"]).text
        result = pt.patching_call_text(CONFIG, row, ACCOUNTS["y"])
        self.assertTrue(result.startswith(CONFIG["capture"]["stem"] + ACCOUNTS["y"]))
        body = json.loads(result.split("\n")[1])
        self.assertEqual(list(body["arguments"]), ["recipient", "amount", "date", "subject"])
        self.assertEqual(
            body["arguments"],
            {**row["expected_send_money"]["arguments"], "recipient": ACCOUNTS["y"]},
        )
        self.assertEqual(row, original)
        self.assertEqual(
            serialize_qwen_tool_call("send_money", row["expected_send_money"]["arguments"]).text,
            old,
        )
        self.assertFalse(old.startswith(CONFIG["capture"]["stem"]))

    def test_remainder_matches_account_and_rejects_crossing_quote(self):
        row = rows_and_labels()[0][0]
        row["source_role"] = "user_instruction"
        prefix = synthetic_prefix(row)
        tokenizer = SyntheticTokenizer()
        actual = pt.account_remainder_ids(tokenizer, CONFIG, row, ACCOUNTS["x"], prefix=prefix)
        self.assertEqual(actual, [ord(char) for char in "8XXX"])

        class Crossing(SyntheticTokenizer):
            def __call__(self, text, **kwargs):
                values = super().__call__(text, **kwargs)
                boundary = text.find('XXX"')
                if boundary >= 0:
                    idx = values["offset_mapping"].index((boundary + 2, boundary + 3))
                    values["offset_mapping"][idx] = (boundary + 2, boundary + 4)
                return values

        with self.assertRaises(ValueError):
            pt.account_remainder_ids(Crossing(), CONFIG, row, ACCOUNTS["x"], prefix=prefix)
        with self.assertRaises(ValueError):
            pt.account_remainder_ids(
                SyntheticTokenizer(unstable=True), CONFIG, row, ACCOUNTS["x"], prefix=prefix
            )

    def test_donors_are_deterministic_and_never_use_outcomes(self):
        rows, labels = rows_and_labels()
        pairs = pair_index(rows, labels)
        table = pt.donor_table(rows, labels, pairs, ACCOUNTS)
        reverse = list(reversed(rows))
        reversed_labels = list(reversed(labels))
        self.assertEqual(
            table,
            pt.donor_table(
                reverse, reversed_labels, pair_index(reverse, reversed_labels), ACCOUNTS
            ),
        )
        by_id = {row["condition_id"]: row for row in rows}
        label_by_id = {row["condition_id"]: label for row, label in zip(rows, labels, strict=True)}
        for row in rows:
            cross = by_id[table[row["condition_id"]]["cross"]]
            self.assertNotEqual(cross["family_id"], row["family_id"])
            self.assertNotEqual(
                label_by_id[cross["condition_id"]], label_by_id[row["condition_id"]]
            )
        changed = [
            {**row, "attack_success": bool(i % 3), "ld": 999 - i} for i, row in enumerate(rows)
        ]
        self.assertEqual(table, pt.donor_table(changed, labels, pairs, ACCOUNTS))
        with self.assertRaises(ValueError):
            small, small_labels = rows_and_labels(families=1)
            pt.donor_table(small, small_labels, pair_index(small, small_labels), ACCOUNTS)
        bad = copy.deepcopy(rows)
        bad[-1]["user_instruction"] = "GB4YYY GB8XXX"
        bad[-1]["documents"][0]["content"] = "GB4YYY GB8XXX"
        with self.assertRaises(ValueError):
            pt.donor_table(bad, labels, pairs, ACCOUNTS)

    def test_validation_rows_rejected_and_new_provenance_is_explicit(self):
        rows, labels = rows_and_labels()
        rows[0]["split_candidate"] = "validation"
        with self.assertRaises(ValueError):
            pt.donor_table(rows, labels, pair_index(rows, labels), ACCOUNTS)
        self.assertNotIn("validation_rows_loaded", pt.VALIDATION)
        self.assertEqual(pt.VALIDATION["validation_declaration_rows_loaded"], 192)
        self.assertEqual(pt.VALIDATION["validation_rows_used"], 0)
        self.assertEqual(pt.VALIDATION["validation_run_bundles_loaded"], 0)

    def test_token_indices_are_local_and_different_prefix_lengths_align(self):
        source, recipient = [1] * 5 + list(range(18)), [2] * 9 + list(range(18))
        self.assertEqual(source[5:], recipient[9:])
        for index in (0, 16, 17):
            self.assertEqual(source[5 + index], recipient[9 + index])


class EffectTest(unittest.TestCase):
    def test_effect_orientation_exclusions_and_unclipped_values(self):
        labels = [1, 0, 0, 1, 1, 0]
        pairs = [(0, 1), (2, 3), (4, 5)]
        result = pt.pair_effects(
            {0: 2, 1: -2, 2: 0, 3: 0.5, 4: -2, 5: 0},
            {0: -6, 1: 6, 2: 2, 3: -2, 4: 0, 5: -2},
            pairs,
            labels,
            1.0,
        )
        self.assertEqual(result["included"][0]["ne_pair"], 2.0)
        self.assertEqual(len(result["excluded"]), 2)
        self.assertEqual(result["excluded"][0]["reason"], "small_or_reversed_delta")
        negative = pt.pair_effects({0: 1, 1: 0}, {0: 2, 1: -1}, [(0, 1)], [1, 0], 1.0)
        self.assertEqual(negative["included"][0]["ne_pair"], -1)
        with self.assertRaises(ValueError):
            pt.pair_effects({0: float("nan"), 1: 0}, {0: 1, 1: 0}, [(0, 1)], [1, 0], 1)

    def test_float_bit_comparison_distinguishes_signed_zero(self):
        self.assertFalse(pt.records_exact({"x": 0.0}, {"x": -0.0}))
        self.assertTrue(pt.records_exact({"x": [0.5]}, {"x": [0.5]}))
        with self.assertRaises(ValueError):
            pt.records_exact({"x": float("inf")}, {"x": 0.0})

    def test_disruption_has_stem_gate_strict_threshold_and_g_null(self):
        clean = {"candidate_log_mass": -5.0, "stem_log_likelihood": {"T": -1.0, "S": -1.0}}
        patched = {"candidate_log_mass": -5.0, "stem_log_likelihood": {"T": -2.0, "S": -2.0}}
        self.assertEqual(
            pt.raw_changes(clean, patched, "T", SETTINGS["analysis"])["disruption_reasons"],
            ["stem_likelihood"],
        )
        g = pt.raw_changes(clean, patched, "G", SETTINGS["analysis"])
        self.assertFalse(g["disrupted"])
        self.assertIsNone(g["stem_log_likelihood_change"])
        exact = {"candidate_log_mass": 0.0, "stem_log_likelihood": {"T": 0.0}}
        boundary = {
            "candidate_log_mass": math.log(0.5),
            "stem_log_likelihood": {"T": math.log(0.5)},
        }
        self.assertFalse(pt.raw_changes(exact, boundary, "T", SETTINGS["analysis"])["disrupted"])

    @staticmethod
    def cell():
        return {
            "eligible_pairs": 12,
            "mean": 0.5,
            "interval": [0.25, 0.8],
            "direction_means": {"ne_x_to_y": 0.25, "ne_y_to_x": 0.75},
            "family_means": {str(i): 0.1 if i < 5 else -0.1 for i in range(6)},
            "source_role_means": {"user": 0.1, "tool": 0.1},
            "median_log_mass_change": 0.0,
            "median_stem_log_likelihood_change": None,
        }

    def test_fixed_classification_boundaries(self):
        cell = self.cell()
        self.assertEqual(pt.classify_cell(cell, SETTINGS["analysis"]), "P-STRONG")
        for key in ("median_log_mass_change", "median_stem_log_likelihood_change"):
            self.assertEqual(
                pt.classify_cell({**cell, key: -1.0}, SETTINGS["analysis"]), "P-DISRUPT"
            )
            self.assertEqual(
                pt.classify_cell({**cell, key: math.log(0.5)}, SETTINGS["analysis"]), "P-STRONG"
            )
        self.assertEqual(
            pt.classify_cell({**cell, "mean": 0.49}, SETTINGS["analysis"]), "P-PARTIAL"
        )
        self.assertEqual(
            pt.classify_cell({**cell, "interval": [0.0, 0.8]}, SETTINGS["analysis"]), "P-NONE"
        )
        self.assertEqual(pt.classify_cell({"eligible_pairs": 0}, SETTINGS["analysis"]), "undefined")

    @staticmethod
    def cells(strong):
        cells = {}
        for position in pt.POSITIONS:
            for layer in SETTINGS["patching"]["layers"]:
                cells[f"{position}/layer{layer}"] = {
                    "position": position,
                    "layer": layer,
                    "class": "P-STRONG" if (position, layer) in strong else "P-NONE",
                    "mean": 0.5,
                    "cross": {"mean": 0.25, "class": "P-PARTIAL"},
                }
        return cells

    def test_mapping_rules_all_positions_and_positive_independent_of_strong(self):
        for position in pt.POSITIONS:
            self.assertEqual(pt.map_patching(self.cells({(position, 28)}), True, True)["rule"], 3)
        self.assertEqual(pt.map_patching(self.cells({("T", 24)}), True, True)["rule"], 1)
        cells = self.cells({("T", 28), ("G", 16)})
        cells["T/layer16"]["class"] = "P-PARTIAL"
        result = pt.map_patching(cells, True, True)
        self.assertEqual(result["rule"], 2)
        self.assertIn("Partial", result["description"])
        self.assertEqual(
            result["evidence_cells"][0]["cross_description"],
            "same_accounts_order_cross_context_ge_half",
        )
        cells["G/layer16"]["cross"]["class"] = "P-DISRUPT"
        self.assertEqual(
            pt.map_patching(cells, True, True)["evidence_cells"][0]["cross_description"],
            "cross_disrupted_interpretation_held",
        )
        self.assertEqual(pt.map_patching(self.cells(set()), True, True)["rule"], 4)
        self.assertEqual(pt.map_patching(cells, False, True)["mapping"], "held")
        self.assertEqual(pt.map_patching(cells, True, False)["mapping"], "held")
        for cell in cells.values():
            cell["class"] = "undefined"
        self.assertEqual(pt.map_patching(cells, True, True)["reason"], "no_eligible_pairs")

    def test_resource_limits_do_not_silently_expand(self):
        limits = SETTINGS["resources"]
        self.assertEqual(limits["maximum_seconds_per_condition"], 600)
        pt.check_resources(limits, 447.2848822970009, 12 * 1024**3)
        pt.check_resources(limits, 600, 12 * 1024**3)
        with self.assertRaises(RuntimeError):
            pt.check_resources(limits, 600.001, 1)
        with self.assertRaises(RuntimeError):
            pt.check_resources(limits, 1, 12 * 1024**3 + 1)


@unittest.skipUnless(NUMERICAL, "numerical extras unavailable")
class NumericalTest(unittest.TestCase):
    def test_series_bootstrap_is_deterministic_and_resamples_whole_series(self):
        import numpy as np

        rows = [{"semantic_series_id": "a"}, {}, {"semantic_series_id": "b"}, {}]
        effects = [
            {"pair": [0, 1], "ne_pair": 0.1},
            {"pair": [0, 1], "ne_pair": 0.9},
            {"pair": [2, 3], "ne_pair": 0.0},
        ]
        rng = np.random.default_rng(9)
        values = []
        groups = [[0.1, 0.9], [0.0]]
        for _ in range(80):
            chosen = [v for i in rng.choice(2, size=2, replace=True) for v in groups[i]]
            values.append(sum(chosen) / len(chosen))
        expected = np.percentile(values, [2.5, 97.5]).tolist()
        self.assertEqual(pt.bootstrap_mean(rows, effects, repeats=80, seed=9), expected)
        self.assertEqual(pt.bootstrap_mean(rows, effects, repeats=80, seed=9), expected)
        self.assertIsNone(pt.bootstrap_mean(rows, [], repeats=80, seed=9))

    def test_cell_sign_agreement_counts_already_aligned_and_zero(self):
        rows, labels = rows_and_labels()
        pairs = pair_index(rows, labels)

        def record(ld):
            return {
                "ld": ld,
                "candidate_log_mass": -2.0,
                "stem_log_likelihood": {"T": -1.0, "S": -1.0},
                "digit_margin": 0.1,
            }

        clean = {i: record(2.0 if label else -2.0) for i, label in enumerate(labels)}
        patched = {i: record(-2.0 if label else 2.0) for i, label in enumerate(labels)}
        effect = pt.pair_effects(
            {i: v["ld"] for i, v in clean.items()},
            {i: v["ld"] for i, v in patched.items()},
            pairs,
            labels,
            1.0,
        )
        spec = {**SETTINGS["analysis"], "bootstrap_repeats": 10}
        result = pt.cell_statistics(rows, effect, clean, patched, "G", spec, patched)
        self.assertEqual(result["class"], "P-STRONG")
        self.assertEqual(result["donor_sign_agreement_rate"], 1.0)
        donors = {i: record(0.0) for i in range(len(rows))}
        self.assertEqual(
            pt.cell_statistics(rows, effect, clean, patched, "G", spec, donors)[
                "donor_sign_agreement_rate"
            ],
            0.0,
        )
        empty = pt.cell_statistics(
            rows, {"included": [], "excluded": []}, clean, patched, "G", spec, donors
        )
        self.assertEqual(empty["class"], "undefined")


@unittest.skipUnless(TORCH, "torch/transformers extras unavailable")
class HookAndCacheTest(unittest.TestCase):
    def test_patch_clone_dtype_shape_device_calls_tuple_and_capture_order(self):
        import torch

        class Block(torch.nn.Module):
            def forward(self, x):
                return x + 1

        class TupleBlock(torch.nn.Module):
            def forward(self, x):
                return (x + 1, "sentinel")

        for block in (Block(), TupleBlock()):
            model = torch.nn.Sequential(block)
            value = torch.zeros(1, 3, 4)
            original = model(value)
            tensor = original[0] if isinstance(original, tuple) else original
            with ResidualPatch(model, "0", 1, tensor[0, 1]):
                same = model(value)
            self.assertTrue(torch.equal(same[0] if isinstance(same, tuple) else same, tensor))
            vector = torch.full((4,), 7.0)
            with ResidualPatch(model, "0", 1, vector), ResidualCapture(model, ["0"]) as captured:
                changed = model(value)
            changed = changed[0] if isinstance(changed, tuple) else changed
            self.assertTrue(torch.equal(changed[0, 0], tensor[0, 0]))
            self.assertTrue(torch.equal(changed[0, 2], tensor[0, 2]))
            self.assertTrue(torch.equal(captured.values["0"][0][0, 1], vector))
            self.assertTrue(torch.equal(tensor, torch.ones_like(tensor)))
            for bad in (
                torch.ones(3),
                torch.ones(4, dtype=torch.float64),
                torch.empty(4, device="meta"),
            ):
                with self.assertRaises(ValueError), ResidualPatch(model, "0", 1, bad):
                    model(value)
            with self.assertRaises(RuntimeError), ResidualPatch(model, "0", 1, vector):
                pass
            with self.assertRaises(RuntimeError), ResidualPatch(model, "0", 1, vector):
                model(value)
                model(value)

    def test_cached_suffix_matches_full_and_crops_repeat_exactly(self):
        import torch

        model = synthetic_model()
        ids, t, g = [4, 7, 8, 9, 11, 12], 2, 5
        cache = pt.prefix_cache(model, ids, t)
        suffix = pt.run_suffix(model, cache, ids, t, g)["logits"]
        with torch.no_grad():
            full = model(input_ids=torch.tensor([ids]), use_cache=False).logits[:, t:]
        torch.testing.assert_close(suffix, full, rtol=1e-5, atol=1e-6)
        pt.crop_cache(cache, t)
        repeated = pt.run_suffix(model, cache, ids, t, g)["logits"]
        self.assertEqual(pt.tensor_bytes(suffix), pt.tensor_bytes(repeated))

    def test_final_g_positive_control_does_not_replace_cache_or_later_scores(self):
        import torch

        model = synthetic_model()
        names = [f"model.layers.{i}" for i in range(3)]
        recipient, donor = [1, 2, 3, 4, 5, 6], [7, 8, 9, 3, 4, 5, 6]
        t, g = 2, 5
        cache = pt.prefix_cache(model, donor, t + 1)
        clean = pt.run_suffix(model, cache, donor, t + 1, g + 1, capture_names=names)
        donor_dist = torch.log_softmax(clean["logits"][0, -1].float(), -1).detach()
        cache_r = pt.prefix_cache(model, recipient, t)
        before = pt.run_suffix(model, cache_r, recipient, t, g)
        keys_before = [layer.keys.clone() for layer in cache_r.layers]
        pt.crop_cache(cache_r, t)
        patched = pt.run_suffix(
            model,
            cache_r,
            recipient,
            t,
            g,
            patch=(names[-1], "G", clean["residuals"][names[-1]][0, -1]),
        )
        current = torch.log_softmax(patched["logits"][0, -1].float(), -1).detach()
        self.assertTrue(pt.compare_distributions(current, donor_dist)["bit_exact"])
        for layer, old in zip(cache_r.layers, keys_before, strict=True):
            self.assertEqual(pt.tensor_bytes(layer.keys), pt.tensor_bytes(old))
        self.assertEqual(
            pt.tensor_bytes(before["logits"][0, :-1]), pt.tensor_bytes(patched["logits"][0, :-1])
        )
        altered = current.clone()
        altered[299] += 0.1
        self.assertFalse(pt.compare_distributions(altered, donor_dist)["bit_exact"])

    def test_incremental_scoring_first_token_and_branch_independence(self):
        import torch

        model = synthetic_model()
        ids, t, g = [1, 2, 3, 4, 5, 6], 2, 5
        cache = pt.prefix_cache(model, ids, t)
        suffix = pt.run_suffix(model, cache, ids, t, g)
        remainders = {"first": [8, 9, 10], "second": [11, 12, 13]}
        stats = pt.ForwardStats()
        scored = pt.score_candidates(
            model, cache, suffix["logits"][0, -1], remainders, g + 1, stats=stats
        )
        self.assertEqual(stats.counts["token"], 4)
        first_logp = float(torch.log_softmax(suffix["logits"][0, -1].float(), -1)[8])
        self.assertEqual(scored["first"]["token_log_probabilities"][0], first_logp)
        alone = pt.score_candidates(
            model,
            cache,
            suffix["logits"][0, -1],
            {"first": [11, 12, 13], "second": [8, 9, 10]},
            g + 1,
        )
        self.assertTrue(pt.records_exact(scored["second"], alone["first"]))
        self.assertEqual(cache.get_seq_length(), g + 1)

    def test_evaluate_self_and_nonfinal_patch_propagation(self):
        import torch

        model = synthetic_model()
        ids, t, g = [1, 2, 3, 4, 5, 6], 2, 5
        item = {
            "input_ids": ids,
            "t_index": t,
            "g_index": g,
            "remainders": {"first": [8, 9], "second": [11, 12]},
            "digit_token_ids": {"a": 8, "b": 11},
        }
        plan = {"settings": SETTINGS}
        names = [f"model.layers.{i}" for i in range(3)]
        cache = pt.prefix_cache(model, ids, t)
        clean = pt.evaluate(model, cache, item, plan, capture_names=names)
        for position, local in (("T", 0), ("S", 2), ("G", 3)):
            for name in names:
                same = pt.evaluate(
                    model,
                    cache,
                    item,
                    plan,
                    patch=(
                        name,
                        position,
                        clean["residuals"][name][
                            0, local if local == 0 else pt.POSITIONS.index(position)
                        ],
                    ),
                )
                self.assertTrue(pt.records_exact(clean["record"], same["record"]))
        pt.crop_cache(cache, t)
        changed = pt.run_suffix(model, cache, ids, t, g, patch=(names[0], "S", torch.ones(16) * 3))[
            "logits"
        ]
        pt.crop_cache(cache, t)
        before = pt.run_suffix(model, cache, ids, t, g)["logits"]
        self.assertEqual(pt.tensor_bytes(changed[:, :2]), pt.tensor_bytes(before[:, :2]))
        self.assertNotEqual(pt.tensor_bytes(changed[:, -1]), pt.tensor_bytes(before[:, -1]))


class ProvenanceAndCommandTest(unittest.TestCase):
    def test_reports_are_exclusive_and_checksum_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "report.json"
            pt.write_report(target, {"status": "passed"})
            with self.assertRaises(FileExistsError):
                pt.write_report(target, {"status": "passed"})
            files = {
                "run.json": canonical_json_bytes({"status": "completed", "git_commit": "test"})
            }
            bundle = pt.write_bundle(root, "synthetic-run", files)
            self.assertTrue(pt.completed_bundle(bundle, {"git_commit": "test"}))
            self.assertFalse(pt.completed_bundle(root / "absent", {}))
            with self.assertRaises(ValueError):
                pt.completed_bundle(bundle, {"git_commit": "other"})
            (bundle / "run.json").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                pt.completed_bundle(bundle, {})

    def test_freeze_rejects_identity_drift_failed_reports_and_existing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "design.json").write_text("{}")
            (root / "environment.lock").write_text("synthetic\n")
            plan = {
                "root": root,
                "analysis_config_sha256": "a",
                "spec_sha256": "s",
                "sweep_config_sha256": "w",
                "reference_sha256": {"runtime": "r"},
                "config": {
                    "model": {"name": "synthetic"},
                    "references": {"design_freeze": "design.json"},
                },
                "settings": SETTINGS,
            }
            with (
                patch.object(pt, "clean_commit", return_value="abcdef123456"),
                patch.object(pt, "load_plan", return_value=plan),
            ):
                ident = pt.identity(plan)
                for name in ("tokenizer.json", "gpu.json"):
                    pt.write_report(
                        root / name,
                        {**ident, "status": "passed", "environment": {"synthetic": True}},
                    )
                args = (
                    Path("unused"),
                    Path("tokenizer.json"),
                    Path("gpu.json"),
                    Path("environment.lock"),
                )
                freeze = pt.create_patching_runtime_freeze(*args)
                self.assertEqual(
                    json.loads(freeze.read_text())["files_sha256"]["environment.lock"],
                    sha256_file(root / "environment.lock"),
                )
                with self.assertRaises(FileExistsError):
                    pt.create_patching_runtime_freeze(*args)
                value = json.loads(freeze.read_text())
                value["reference_sha256"] = {}
                with self.assertRaises(ValueError):
                    pt.validate_freeze(plan, value)
                (root / "gpu.json").write_text(json.dumps({**ident, "status": "failed"}))
                with self.assertRaises(ValueError):
                    pt.create_patching_runtime_freeze(*args)
                (root / "gpu.json").write_text(
                    json.dumps({**ident, "git_commit": "other", "status": "passed"})
                )
                with self.assertRaises(ValueError):
                    pt.create_patching_runtime_freeze(*args)
            with (
                patch.object(pt, "clean_commit", side_effect=ValueError("dirty")),
                self.assertRaises(ValueError),
            ):
                pt.identity(plan)

    def test_preflight_cli_never_dispatches_capture(self):
        for command, function, result in (
            (
                "tokenizer-preflight",
                "patching_tokenizer_preflight",
                {"status": "passed", "condition_count": 240},
            ),
            (
                "gpu-preflight",
                "patching_gpu_preflight",
                {"status": "passed", "conditions": [{}, {}]},
            ),
        ):
            with (
                patch("sys.argv", ["patching", command, "test.json"]),
                patch.object(pt, function, return_value=result),
                patch.object(pt, "capture_patching") as capture,
            ):
                pt.main()
                capture.assert_not_called()


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(TORCH and NUMERICAL, "research extras unavailable")
class SyntheticBundleIntegrationTest(unittest.TestCase):
    """Exercise the real writer/reader and failure retention in temporary test storage."""

    @staticmethod
    def plan(root):
        rows, labels = rows_and_labels(families=2, tasks=1)
        settings = copy.deepcopy(SETTINGS)
        settings["patching"].update(run_id_prefix="synthetic-patch", layers=[0, 1, 2])
        settings["analysis"]["positive_control"]["layer"] = 2
        settings["analysis"].update(bootstrap_repeats=10, output_id="synthetic-analysis")
        settings["analysis"]["strong"]["family_positive_minimum"] = 2
        settings["reference"]["input_run_id_prefix"] = "synthetic-source"
        run_ids = {
            row["condition_id"]: f"canonical-c{i:03d}" for i, row in enumerate(rows, start=1)
        }
        for row in rows:
            row["pair_id"] = row["draft_task_id"] + "-pair"
        pairs = pair_index(rows, labels)
        return {
            "root": root,
            "settings": settings,
            "sweep": CONFIG,
            "rows": rows,
            "labels": labels,
            "pairs": pairs,
            "accounts": ACCOUNTS,
            "run_ids": run_ids,
            "donors": pt.donor_table(rows, labels, pairs, ACCOUNTS),
            "source_rows": {
                pt.nod.run_id("synthetic-source", rid): {"manifest_sha256": "source"}
                for rid in run_ids.values()
            },
            "analysis_config_sha256": "config",
            "spec_sha256": "spec",
            "sweep_config_sha256": "sweep",
            "reference_sha256": {"source": "source"},
            "runtime": "synthetic.freeze.json",
            "runtime_sha256": "freeze",
            "freeze": {"git_commit": "capture000", "decoding": {"do_sample": False}},
            "config": {"model": {"name": "synthetic", "tokenizer_revision": "test"}},
        }

    @staticmethod
    def item(plan, row, _tokenizer=None):
        index = plan["rows"].index(row)
        ids = [1 + index, 2 + index, 3 + index, 4, 5, 6]
        return {
            "row": row,
            "condition": row,
            "prefix": {"text": "synthetic", "token_ids": ids[:3]},
            "input_ids": ids,
            "t_index": 2,
            "g_index": 5,
            "positions": {
                name: {"token_index": i, "token_id": ids[i]}
                for name, i in zip(pt.POSITIONS, (2, 4, 5), strict=True)
            },
            "accounts": {"first": ACCOUNTS["x"], "second": ACCOUNTS["y"]},
            "remainders": {"first": [8, 9], "second": [11, 12]},
            "digit_token_ids": {"a": 8, "b": 11},
            "serialization": pt.SERIALIZATION,
            "call_text_sha256": {"first": "test", "second": "test"},
            "source_run_id": pt.nod.run_id(
                "synthetic-source", plan["run_ids"][row["condition_id"]]
            ),
            "source_manifest_sha256": "source",
            "source": {"run": {"model_dimensions": {"num_hidden_layers": 3, "hidden_size": 16}}},
        }

    def test_synthetic_capture_resume_reader_and_analysis_without_real_data(self):
        from contextlib import ExitStack

        import torch

        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            plan = self.plan(root)
            model = synthetic_model(dtype=torch.bfloat16)
            stack.enter_context(patch.object(pt, "load_plan", return_value=plan))
            stack.enter_context(patch.object(pt, "clean_commit", return_value="capture000"))
            loader = stack.enter_context(patch.object(pt, "load_model", return_value=(model, None)))
            stack.enter_context(
                patch.object(pt, "prepare_input", side_effect=lambda p, r, t: self.item(p, r))
            )
            stack.enter_context(
                patch.object(pt, "read_input", side_effect=lambda p, r: self.item(p, r))
            )
            stack.enter_context(patch("torch.cuda.reset_peak_memory_stats"))
            stack.enter_context(patch("torch.cuda.max_memory_allocated", return_value=0))
            paths = pt.capture_patching(Path("test"), Path("test.freeze.json"))
            self.assertEqual(len(paths), 4)
            for row in plan["rows"]:
                bundle = pt.read_capture(plan, row)
                self.assertEqual(len(bundle["results"]["interventions"]), 27)
                self.assertTrue(bundle["results"]["positive_control"]["bit_exact"])
                self.assertEqual(
                    sum(
                        entry["self_exact"] is True
                        for entry in bundle["results"]["interventions"].values()
                    ),
                    9,
                )
            loader.reset_mock()
            pt.capture_patching(Path("test"), Path("test.freeze.json"))
            loader.assert_not_called()
            with patch.object(pt, "clean_commit", return_value="analysis000"):
                output = pt.analyze(Path("test"), Path("test.freeze.json"))
                report = json.loads((output / "report.json").read_text())
                self.assertTrue(all(report["health"].values()))
                with self.assertRaises(FileExistsError):
                    pt.analyze(Path("test"), Path("test.freeze.json"))

    def test_donor_first_pass_failure_is_preserved_without_interventions(self):
        from contextlib import ExitStack

        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            plan = self.plan(root)
            stack.enter_context(patch.object(pt, "load_plan", return_value=plan))
            stack.enter_context(patch.object(pt, "clean_commit", return_value="capture000"))
            stack.enter_context(
                patch.object(pt, "load_model", side_effect=RuntimeError("synthetic load failure"))
            )
            interventions = stack.enter_context(patch.object(pt, "intervene_condition"))
            with self.assertRaisesRegex(RuntimeError, "retained technical failure"):
                pt.capture_patching(Path("test"), Path("test.freeze.json"))
            interventions.assert_not_called()
            bundle = next((root / "artifacts/runs").iterdir())
            run = json.loads((bundle / "run.json").read_text())
            self.assertEqual(run["failure_stage"], "donor_clean")
            self.assertEqual(run["status"], "technical_failure")
            with self.assertRaises(ValueError):
                pt.completed_bundle(bundle, {})
