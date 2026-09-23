import unittest

from goal_takeover.models.qwen import QwenToolCallParseError, parse_qwen_action
from goal_takeover.serialization.qwen import serialize_qwen_tool_call


class QwenAdapterTest(unittest.TestCase):
    def test_native_tool_call_tracks_name_and_argument_spans(self) -> None:
        call = serialize_qwen_tool_call("send_money", {"recipient": "GB00", "amount": 4.0})

        self.assertTrue(call.text.startswith("<tool_call>\n"))
        self.assertTrue(call.text.endswith("</tool_call><|im_end|>"))
        name = call.tool_name_span
        recipient = call.argument_spans["recipient"]
        self.assertEqual(call.text[name.start : name.end], '"send_money"')
        self.assertEqual(call.text[recipient.start : recipient.end], '"GB00"')

    def test_tool_call_parser_preserves_raw_message(self) -> None:
        text = (
            "<think>\n\n</think>\n\n<tool_call>\n"
            '{"name":"send_money","arguments":{"amount":4}}\n</tool_call>'
        )
        action = parse_qwen_action(text, call_id="call_0000")

        self.assertEqual(action.kind, "tool")
        self.assertEqual(action.tool_name, "send_money")
        self.assertEqual(action.tool_arguments, {"amount": 4})
        self.assertEqual(action.tool_call_id, "call_0000")
        self.assertEqual(action.raw_text, text)
        self.assertEqual(action.assistant_message["tool_calls"][0]["id"], "call_0000")

    def test_parser_preserves_multiple_calls_in_order(self) -> None:
        text = (
            '<tool_call>{"name":"read","arguments":{"account":"A"}}</tool_call>'
            '<tool_call>{"name":"refund","arguments":{"amount":4}}</tool_call>'
        )
        action = parse_qwen_action(text, call_id="call_0000")

        self.assertEqual([call.name for call in action.tool_calls], ["read", "refund"])
        self.assertEqual([call.call_id for call in action.tool_calls], ["call_0000", "call_0000_1"])
        self.assertEqual(action.tool_calls[1].arguments, {"amount": 4})
        self.assertEqual(
            [call["function"]["name"] for call in action.assistant_message["tool_calls"]],
            ["read", "refund"],
        )
        self.assertEqual(action.raw_text, text)

    def test_parser_rejects_malformed_call_without_dropping_valid_sibling(self) -> None:
        with self.assertRaises(QwenToolCallParseError):
            parse_qwen_action("<tool_call>{bad json}</tool_call>", call_id="call_0000")
        with self.assertRaises(QwenToolCallParseError) as raised:
            parse_qwen_action(
                '<tool_call>{"name":"a","arguments":{}}</tool_call>'
                '<tool_call>{"name":"b","arguments":{bad}}</tool_call>',
                call_id="call_0000",
            )
        self.assertIn('"name":"b"', raised.exception.raw_text)
        with self.assertRaises(QwenToolCallParseError):
            parse_qwen_action("<tool_call>{}", call_id="call_0000")

    def test_plain_completion_is_a_final_answer(self) -> None:
        action = parse_qwen_action("<think>ignored</think>answer", call_id="call_0000")
        self.assertEqual(action.kind, "final")
        self.assertEqual(action.content, "answer")


if __name__ == "__main__":
    unittest.main()
