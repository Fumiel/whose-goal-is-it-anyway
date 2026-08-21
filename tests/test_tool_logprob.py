import math
import unittest

from goal_takeover.evaluation.tool_logprob import (
    selected_token_log_probability,
    sequence_log_probability,
    tool_margin,
)


class ToolLogProbabilityTest(unittest.TestCase):
    def test_sequence_score_sums_all_tokens(self) -> None:
        self.assertAlmostEqual(sequence_log_probability([-0.2, -0.5, -0.3]), -1.0)

    def test_margin_uses_whole_sequences(self) -> None:
        self.assertAlmostEqual(tool_margin([-0.1, -0.2], [-0.5, -0.6]), 0.8)

    def test_empty_sequence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            sequence_log_probability([])

    def test_selected_token_log_probability_is_stable(self) -> None:
        score = selected_token_log_probability([1000.0, 1001.0], 1)
        self.assertAlmostEqual(score, -math.log1p(math.exp(-1.0)))


if __name__ == "__main__":
    unittest.main()
