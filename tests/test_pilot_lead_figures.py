import unittest

import numpy as np

from goal_takeover.analysis.pilot_lead_figures import capture_row, cosine_distance_matrix


class PilotLeadFiguresTests(unittest.TestCase):
    def test_capture_row_keeps_actual_and_fixed_prefix_separate(self):
        run = {
            "measurements": [
                {
                    "index": 0,
                    "scope": "actual",
                    "positions": {
                        "exposed": False,
                        "positions": [{"name": "Tend_assistant"}],
                    },
                },
                {
                    "index": 1,
                    "scope": "actual",
                    "positions": {
                        "exposed": True,
                        "positions": [
                            {"name": name}
                            for name in ("Tpre", "Tpost", "Tend_tool", "Tend_assistant")
                        ],
                        "intervention_token_indices": [4, 5],
                    },
                    "activation": {"positions": [3, 4, 5, 6]},
                },
                {
                    "index": 2,
                    "scope": "fixed_prefix_diagnostic",
                    "positions": {"exposed": True, "positions": []},
                },
            ]
        }
        paths = {
            "measurements/0/residual.safetensors",
            "measurements/1/residual.safetensors",
            "measurements/1/attention.json",
            "measurements/1/scores.json",
            "measurements/2/scores.json",
        }
        np.testing.assert_array_equal(capture_row(run, paths), [1, 1, 1, 1, 1, 1, 2, 3, 4])

    def test_cosine_distance_has_expected_shape_alignment_and_value(self):
        states = np.array(
            [
                [[9, 9], [1, 0], [0, 1], [-1, 0]],
                [[9, 9], [0, 1], [0, 1], [1, 0]],
            ],
            dtype=float,
        )
        distances, offsets = cosine_distance_matrix(states, [4, 5, 6, 7], 5)
        self.assertEqual(offsets, [0, 1, 2])
        np.testing.assert_allclose(distances, [[0, 1, 2], [0, 0, 1]])
        np.testing.assert_array_equal(distances, cosine_distance_matrix(states, [4, 5, 6, 7], 5)[0])

    def test_cosine_distance_rejects_missing_or_unaligned_positions(self):
        states = np.ones((2, 3, 4))
        with self.assertRaises(ValueError):
            cosine_distance_matrix(states, [1, 3, 4], 1)
        with self.assertRaises(ValueError):
            cosine_distance_matrix(states, [1, 2], 1)
        with self.assertRaises(ValueError):
            cosine_distance_matrix(states, [1, 2, 3], 0)
        states[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            cosine_distance_matrix(states, [1, 2, 3], 1)


if __name__ == "__main__":
    unittest.main()
