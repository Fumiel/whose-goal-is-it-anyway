import math
import unittest

from goal_takeover.evaluation.tool_logprob import (
    CandidateSequenceScore,
    compare_candidate_sequences,
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

    def test_same_tool_different_argument_is_scored_over_full_sequences(self) -> None:
        legitimate = CandidateSequenceScore(
            text="legitimate",
            token_ids=(1, 2, 3, 4),
            token_log_probabilities=(-0.1, -0.4, -0.6, -0.2),
            argument_token_indices=(2, 3),
            tool_name_token_indices=(0, 1),
        )
        attack = CandidateSequenceScore(
            text="attack",
            token_ids=(1, 2, 8),
            token_log_probabilities=(-0.1, -0.4, -0.2),
            argument_token_indices=(2,),
            tool_name_token_indices=(0, 1),
        )

        margins = compare_candidate_sequences(attack, legitimate)

        self.assertAlmostEqual(margins.argument_slot_margin_total, 0.6)
        self.assertAlmostEqual(margins.argument_slot_margin_normalized, 0.2)
        self.assertAlmostEqual(margins.whole_call_margin_total, 0.6)
        self.assertAlmostEqual(
            margins.whole_call_margin_normalized,
            (-0.7 / 3) - (-1.3 / 4),
        )
        self.assertAlmostEqual(margins.first_discriminating_token_margin, 0.4)
        self.assertIsNone(margins.tool_name_margin)
        self.assertEqual(legitimate.as_dict()["argument_token_indices"], [2, 3])
        self.assertEqual(attack.as_dict()["tool_name_token_indices"], [0, 1])


if __name__ == "__main__":
    unittest.main()
