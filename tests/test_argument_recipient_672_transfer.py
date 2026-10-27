import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional research dependency
    np = None


@unittest.skipIf(np is None, "numpy is required")
class TransferTest(unittest.TestCase):
    def setUp(self) -> None:
        from goal_takeover.phase2 import argument_recipient_672_transfer as transfer

        self.transfer = transfer
        self.rng = np.random.default_rng(0)
        self.candidates = ["v1", "v2"]
        self.probes = {
            c: {
                "mean": np.zeros(6),
                "scale": np.ones(6),
                "coef": self.rng.normal(size=6),
                "intercept": 0.1,
            }
            for c in self.candidates
        }
        specs = []
        for index in range(8):
            recipient, reference = ("v1", "v2") if index % 2 == 0 else ("v2", "v1")
            specs.append(
                {
                    "condition_id": f"c{index}",
                    "split_candidate": "validation" if index < 4 else "train",
                    "family_id": "G" if index < 2 else "I" if index < 4 else "A",
                    "recipient_value_id": recipient,
                    "reference_value_id": reference,
                    "argument_present": {recipient: 1, reference: 0},
                }
            )
        self.declaration = {"condition_specs": specs}
        self.canonical = {
            spec["condition_id"]: {
                "run_id": "can-" + spec["condition_id"],
                "vector": self.rng.normal(size=6),
                "token_ids": [1, 2, 3],
                "boundary": "user_to_assistant",
            }
            for spec in specs
        }

    def actual_copy(self, noise: float = 0.0, changed: set[str] = frozenset()):
        return {
            cid: {
                "run_id": "act-" + cid,
                "vector": row["vector"] + noise,
                "token_ids": [1, 2, 4] if cid in changed else row["token_ids"],
                "boundary": row["boundary"],
            }
            for cid, row in self.canonical.items()
        }

    def test_identical_residuals_transfer_exactly(self) -> None:
        report = self.transfer.compute_transfer(
            self.declaration, self.canonical, self.actual_copy(), self.probes
        )
        everything = report["all"]
        self.assertEqual(everything["condition_count"], 8)
        self.assertEqual(everything["prefix_identical_count"], 8)
        self.assertAlmostEqual(everything["max_relative_l2_when_prefix_identical"], 0.0)
        self.assertAlmostEqual(everything["decision_pearson"], 1.0)
        self.assertEqual(everything["argmax_candidate_agreement"], 8)
        self.assertEqual(report["validation_split"]["condition_count"], 4)
        self.assertEqual(report["validation_gh"]["condition_count"], 2)
        self.assertEqual(report["train_split_in_sample_consistency"]["condition_count"], 4)

    def test_prefix_difference_is_stratified_not_dropped(self) -> None:
        report = self.transfer.compute_transfer(
            self.declaration, self.canonical, self.actual_copy(0.5, {"c1", "c5"}), self.probes
        )
        self.assertEqual(report["by_prefix_identity"]["different"]["condition_count"], 2)
        self.assertEqual(report["by_prefix_identity"]["identical"]["condition_count"], 6)
        self.assertEqual(report["all"]["condition_count"], 8)
        self.assertGreater(report["all"]["median_relative_l2"], 0.0)

    def test_role_swap_auc_is_descriptive_and_undefined_without_both_classes(self) -> None:
        report = self.transfer.compute_transfer(
            self.declaration, self.canonical, self.actual_copy(), self.probes
        )
        auc = report["validation_gh"]["descriptive_role_swap_auc"]["actual"]
        self.assertTrue(auc["descriptive_only"])
        # G conditions c0 (v1 recipient) and c1 (v2 recipient): each candidate has both classes.
        self.assertIsNotNone(auc["mean_auc"])
        only_one = {"condition_specs": self.declaration["condition_specs"][:1]}
        small = self.transfer.compute_transfer(
            only_one,
            {"c0": self.canonical["c0"]},
            {"c0": self.actual_copy()["c0"]},
            self.probes,
        )
        self.assertIsNone(small["all"]["descriptive_role_swap_auc"]["actual"]["mean_auc"])

    def test_mismatched_condition_sets_are_rejected(self) -> None:
        actual = self.actual_copy()
        del actual["c0"]
        with self.assertRaises(ValueError):
            self.transfer.compute_transfer(self.declaration, self.canonical, actual, self.probes)

    def test_probe_parameters_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p.npz"
            arrays = {}
            for c, probe in self.probes.items():
                arrays[f"{c}__mean"] = probe["mean"]
                arrays[f"{c}__scale"] = probe["scale"]
                arrays[f"{c}__coef"] = probe["coef"][None, :]
                arrays[f"{c}__intercept"] = np.asarray([probe["intercept"]])
            np.savez_compressed(path, **arrays)
            loaded = self.transfer.load_probes(path, self.candidates)
        vector = self.canonical["c0"]["vector"]
        for c in self.candidates:
            self.assertAlmostEqual(
                self.transfer.decision_values(vector, loaded[c]),
                self.transfer.decision_values(vector, self.probes[c]),
            )


if __name__ == "__main__":
    unittest.main()
