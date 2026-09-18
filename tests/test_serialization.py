import unittest

from goal_takeover.datasets.generation import stable_condition_id
from goal_takeover.schemas import AgentBoundary
from goal_takeover.serialization.canonical import serialize_tool_call
from goal_takeover.serialization.prefix import build_serialized_prefix


class SerializationTest(unittest.TestCase):
    def test_condition_id_is_independent_of_mapping_order(self) -> None:
        left = {"task": "transfer", "arguments": {"recipient": "alice", "amount": 100}}
        right = {"arguments": {"amount": 100, "recipient": "alice"}, "task": "transfer"}
        self.assertEqual(stable_condition_id(left), stable_condition_id(right))

    def test_canonical_call_is_stable_and_tracks_argument_spans(self) -> None:
        first = serialize_tool_call("transfer", {"recipient": "alice", "amount": 100})
        second = serialize_tool_call("transfer", {"amount": 100, "recipient": "alice"})

        self.assertEqual(first, second)
        self.assertEqual(
            first.text,
            '{"name":"transfer","arguments":{"amount":100,"recipient":"alice"}}',
        )
        recipient = first.argument_spans["recipient"]
        self.assertEqual(first.text[recipient.start : recipient.end], '"alice"')
        name = first.tool_name_span
        self.assertEqual(first.text[name.start : name.end], '"transfer"')

    def test_prefix_id_is_stable_and_sensitive_to_serialization_metadata(self) -> None:
        kwargs = {
            "boundary": AgentBoundary.FIRST_TOOL_TO_ASSISTANT,
            "text": "abc",
            "token_ids": [10, 20, 30],
            "offset_mapping": [(0, 1), (1, 2), (2, 3)],
        }
        first = build_serialized_prefix(**kwargs, metadata={"revision": "v1"})
        second = build_serialized_prefix(**kwargs, metadata={"revision": "v1"})
        changed = build_serialized_prefix(**kwargs, metadata={"revision": "v2"})

        self.assertEqual(first.prefix_id, second.prefix_id)
        self.assertNotEqual(first.prefix_id, changed.prefix_id)
        with self.assertRaises(ValueError):
            first.assert_same_tokens([10, 99, 30], consumer="test")


if __name__ == "__main__":
    unittest.main()
