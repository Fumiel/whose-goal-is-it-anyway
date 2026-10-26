"""Selection rules for saved-position recipient diagnostics."""

import unittest

try:
    import numpy as np
    import sklearn  # noqa: F401
except ModuleNotFoundError:
    np = None

from goal_takeover.phase2.argument_position_diagnostic import fit_positions, select_saved_position


class PositionSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.positions = {
            "positions": [
                {"name": "Tpre", "token_index": 4},
                {"name": "Tpost", "token_index": 8},
                {"name": "Tend_assistant", "token_index": 50},
            ]
        }
        self.saved = list(range(4, 25)) + [50]

    def test_selects_exact_indices_and_mean_window(self) -> None:
        self.assertEqual(select_saved_position("tpre", self.positions, self.saved).indices, (4,))
        self.assertEqual(select_saved_position("post16", self.positions, self.saved).indices, (24,))
        self.assertEqual(
            select_saved_position("post_mean_0_8", self.positions, self.saved).indices,
            tuple(range(8, 17)),
        )

    def test_missing_saved_position_is_not_substituted(self) -> None:
        self.assertIsNone(select_saved_position("post16", self.positions, self.saved[:-2] + [50]))

    def test_unknown_position_fails(self) -> None:
        with self.assertRaises(ValueError):
            select_saved_position("unregistered", self.positions, self.saved)


@unittest.skipUnless(np is not None, "research extras are not installed")
class FitPositionTests(unittest.TestCase):
    def test_shape_alignment_and_deterministic_scores(self) -> None:
        source = {
            "candidate_values": {"a": "ACCOUNT-A", "b": "ACCOUNT-B"},
            "fit": {"regularization_c": [0.1], "max_iter": 100, "seed": 17},
        }
        rows = {}
        for index in range(96):
            label = index % 2
            value = "ACCOUNT-A" if label else "ACCOUNT-B"
            other = "ACCOUNT-B" if label else "ACCOUNT-A"
            rows[str(index)] = {
                "condition": {
                    "condition_id": str(index),
                    "split": "train" if index < 64 else "validation",
                    "component_id": "train" if index < 64 else "held_out",
                    "argument_present": {"a": label, "b": 1 - label},
                    "user_instruction": f"Send to {value}; receipt copy {other}.",
                },
                "vectors": {"tpost": {"layer0": np.asarray([float(label), float(1 - label)])}},
            }
        first = fit_positions(source, rows, ["tpost"], ["layer0"])
        second = fit_positions(source, rows, ["tpost"], ["layer0"])
        self.assertEqual(first, second)
        self.assertEqual(first["tpost"]["train"], 64)
        self.assertEqual(first["tpost"]["validation"], 32)
        self.assertEqual(
            first["tpost"]["settings"]["layer0/C=0.1"]["mean_auc_lexical_present"], 1.0
        )
        self.assertEqual(
            fit_positions(source, dict(list(rows.items())[:-1]), ["tpost"], ["layer0"])["tpost"][
                "status"
            ],
            "skipped_incomplete_96",
        )
