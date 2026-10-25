"""Synthetic checks for scoring a saved probe on its training rows."""

from __future__ import annotations

import unittest

try:
    import numpy as np
    from sklearn.metrics import roc_auc_score
except ModuleNotFoundError:
    np = None

from goal_takeover.phase2.argument_probe_train_diagnostic import (
    lexical_present_auc,
    score_matrix,
)


@unittest.skipUnless(np is not None, "research extras are not installed")
class TrainDiagnosticTests(unittest.TestCase):
    def test_saved_scaler_and_probe_score(self) -> None:
        vectors = np.array([[1.0, 2.0], [3.0, 6.0]])
        scores = score_matrix(
            vectors,
            np.array([1.0, 2.0]),
            np.array([2.0, 4.0]),
            np.array([[2.0, -1.0]]),
            np.array([0.25]),
        )
        np.testing.assert_allclose(scores, [0.25, 1.25])
        with self.assertRaises(ValueError):
            score_matrix(vectors, [1.0], [2.0], [[2.0]], [0.0])

    def test_auc_uses_reference_negatives_only(self) -> None:
        labels = [1, 1, 0, 0, 0]
        scores = [0.7, 0.8, 0.9, 0.1, 1.0]
        lexical = [1, 1, 1, 1, 0]
        result = lexical_present_auc(labels, scores, lexical)
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["recipient_positives"], 2)
        self.assertEqual(result["reference_negatives"], 2)
        self.assertEqual(result["auc"], roc_auc_score(labels[:4], scores[:4]))
        with self.assertRaises(ValueError):
            lexical_present_auc([1, 0], [0.2, 0.3], [0, 1])


if __name__ == "__main__":
    unittest.main()
