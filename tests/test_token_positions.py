import unittest

from goal_takeover.instrumentation.token_positions import (
    select_protocol_positions,
    trailing_window_indices,
)
from goal_takeover.schemas import AgentBoundary, TokenPositionName
from goal_takeover.serialization.prefix import build_serialized_prefix


class TokenPositionTest(unittest.TestCase):
    def _prefix(self, text: str):
        return build_serialized_prefix(
            boundary=AgentBoundary.FIRST_TOOL_TO_ASSISTANT,
            text=text,
            token_ids=[ord(character) for character in text],
            offset_mapping=[(index, index + 1) for index in range(len(text))],
            metadata={"serializer": "character-test"},
        )

    def test_all_protocol_positions_are_reproducible(self) -> None:
        text = "tool: benign ATTACK tail <assistant>"
        prefix = self._prefix(text)
        first = select_protocol_positions(
            prefix,
            injection_span=(13, 19),
            tool_content_span=(6, 24),
        )
        second = select_protocol_positions(
            prefix,
            injection_span=(13, 19),
            tool_content_span=(6, 24),
        )

        self.assertEqual(first, second)
        self.assertEqual(first[TokenPositionName.TPRE].token_index, 12)
        self.assertEqual(first[TokenPositionName.TPOST].token_index, 18)
        self.assertEqual(first[TokenPositionName.TEND_TOOL].token_index, 23)
        self.assertEqual(first[TokenPositionName.TEND_ASSISTANT].token_index, len(text) - 1)
        for position in first.values():
            self.assertEqual(position.token_id, prefix.token_ids[position.token_index])

    def test_injection_must_be_inside_tool_content(self) -> None:
        with self.assertRaises(ValueError):
            select_protocol_positions(
                self._prefix("prefix ATTACK tool"),
                injection_span=(7, 13),
                tool_content_span=(14, 18),
            )

    def test_trailing_window_is_clipped_to_sequence(self) -> None:
        self.assertEqual(trailing_window_indices(3, 5), (0, 1, 2))
        self.assertEqual(trailing_window_indices(5, 2), (3, 4))


if __name__ == "__main__":
    unittest.main()
