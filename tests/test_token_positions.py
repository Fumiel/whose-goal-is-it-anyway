import unittest

from goal_takeover.instrumentation.token_positions import (
    last_token_position,
    trailing_window_indices,
)
from goal_takeover.schemas import ProcessingStage


class TokenPositionTest(unittest.TestCase):
    def test_last_token_is_recorded_explicitly(self) -> None:
        position = last_token_position(
            [101, 202, 303],
            ProcessingStage.AFTER_TOOL_OUTPUT,
        )
        self.assertEqual(position.token_index, 2)
        self.assertEqual(position.token_id, 303)
        self.assertEqual(position.sequence_length, 3)

    def test_empty_sequence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            last_token_position([], ProcessingStage.BEFORE_NEXT_ACTION)

    def test_trailing_window_is_clipped_to_sequence(self) -> None:
        self.assertEqual(trailing_window_indices(3, 5), (0, 1, 2))
        self.assertEqual(trailing_window_indices(5, 2), (3, 4))


if __name__ == "__main__":
    unittest.main()
