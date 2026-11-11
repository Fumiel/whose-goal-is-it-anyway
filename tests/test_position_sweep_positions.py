"""Synthetic position alignment and tokenizer contract tests (spec sections 3/9/12)."""

import copy
import json
import unittest
from pathlib import Path

from goal_takeover.phase2.position_sweep_positions import (
    call_continuation_ids,
    first_digit,
    presentation_order,
    resolve_positions,
    safe_path,
    span_last_token,
    stem_statistics,
    validate_tokenizations,
)

CONFIG = json.loads(Path("configs/analysis/phase2_position_sweep_v1.json").read_text())
ACCOUNTS = {"x": "GB8XXX", "y": "GB4YYY", "z": "GB6ZZZ", "w": "GB1WWW"}


class SyntheticTokenizer:
    """Test-only character tokenizer, treating GB as one token."""

    def __init__(self, *, split_gb=False, split_digit=False, unstable=False):
        self.split_gb, self.split_digit, self.unstable = split_gb, split_digit, unstable

    def __call__(self, text, **kwargs):
        ids, offsets, i = [], [], 0
        while i < len(text):
            if text[i : i + 2] == "GB" and not self.split_gb:
                ids.append(256)
                offsets.append((i, i + 2))
                i += 2
            else:
                ids.append(ord(text[i]))
                offsets.append((i, i + 1))
                if self.split_digit and text[i].isdigit():
                    ids.append(ord(text[i]))
                    offsets.append((i, i + 1))
                i += 1
        if self.unstable and "<tool_call>" in text:
            ids[0] += 1
        return {"input_ids": ids, "offset_mapping": offsets}

    def decode(self, ids):
        return "".join("GB" if i == 256 else chr(i) for i in ids)


def synthetic_pair():
    base = {"source_role": "user_instruction", "draft_task_id": "task", "split_candidate": "train"}
    rows = [
        {
            **base,
            "condition_id": str(i),
            "recipient_value_id": r,
            "reference_value_id": ref,
            "user_instruction": "GB8XXX GB4YYY: " + r,
        }
        for i, (r, ref) in enumerate((("x", "y"), ("y", "x")))
    ]
    return rows


def synthetic_prefix(row, tokenizer=None):
    tokenizer = tokenizer or SyntheticTokenizer()
    text = row["user_instruction"]
    value = tokenizer(text)
    return {
        "text": text,
        "token_ids": value["input_ids"],
        "offsets": [
            {"token_index": i, "token_id": token, "start": start, "end": end}
            for i, (token, (start, end)) in enumerate(
                zip(value["input_ids"], value["offset_mapping"], strict=True)
            )
        ],
    }


class PositionTest(unittest.TestCase):
    def setUp(self):
        self.rows = synthetic_pair()
        self.tokenizer = SyntheticTokenizer()
        self.prefix = synthetic_prefix(self.rows[0])

    def test_presentation_order_and_duplicate_or_absent(self):
        for row in self.rows:
            self.assertEqual(presentation_order(row, ACCOUNTS), (ACCOUNTS["x"], ACCOUNTS["y"]))
        for text in ("GB8XXX", "GB8XXX GB8XXX GB4YYY"):
            with self.assertRaises(ValueError):
                presentation_order({**self.rows[0], "user_instruction": text}, ACCOUNTS)

    def test_overlap_uses_last_nonempty_token(self):
        value = copy.deepcopy(self.prefix)
        expected = span_last_token(value, ACCOUNTS["x"])
        value["offsets"].append({"token_index": 999, "start": 3, "end": 3})
        self.assertEqual(span_last_token(value, ACCOUNTS["x"]), expected)
        for text in ("no accounts", value["text"] + ACCOUNTS["x"]):
            with self.assertRaises(ValueError):
                span_last_token({**value, "text": text}, ACCOUNTS["x"])
        with self.assertRaises(ValueError):
            span_last_token({**value, "offsets": []}, ACCOUNTS["x"])

    def test_continuation_contract(self):
        capture = CONFIG["capture"]
        result = call_continuation_ids(self.tokenizer, self.prefix, capture["stem"], "GB", "8")
        self.assertEqual(
            [result[p] for p in ("S", "G", "D")],
            list(range(len(result["input_ids"]) - 3, len(result["input_ids"]))),
        )
        for tokenizer in (
            SyntheticTokenizer(unstable=True),
            SyntheticTokenizer(split_gb=True),
            SyntheticTokenizer(split_digit=True),
        ):
            # Prefix must be saved using the same tokenizer to isolate continuation failures.
            with self.assertRaises(ValueError):
                call_continuation_ids(
                    tokenizer, synthetic_prefix(self.rows[0], tokenizer), capture["stem"], "GB", "8"
                )

    def test_label_swap_changes_only_digit_input(self):
        values = [
            resolve_positions(row, synthetic_prefix(row), ACCOUNTS, self.tokenizer, CONFIG)
            for row in self.rows
        ]
        for p in ("A1", "A2"):
            self.assertEqual(
                values[0]["positions"][p]["account"], values[1]["positions"][p]["account"]
            )
        self.assertNotEqual(
            values[0]["positions"]["D"]["token_id"], values[1]["positions"]["D"]["token_id"]
        )
        self.assertTrue(all(validate_tokenizations(self.rows, values, ACCOUNTS).values()))
        for mutate in ("common", "digits", "pair"):
            broken = copy.deepcopy(values)
            if mutate == "common":
                broken[1]["positions"]["S"]["token_id"] += 1
            elif mutate == "digits":
                broken[1]["digit_token_ids"]["x"] = broken[1]["digit_token_ids"]["y"]
            else:
                broken[1]["positions"]["A1"]["account"] = "different"
            with self.assertRaises(ValueError):
                validate_tokenizations(self.rows, broken, ACCOUNTS)
        reversed_prefix = synthetic_prefix({**self.rows[0], "user_instruction": "GB4YYY GB8XXX"})
        with self.assertRaises(ValueError):
            resolve_positions(self.rows[0], reversed_prefix, ACCOUNTS, self.tokenizer, CONFIG)

    def test_stem_and_grid_match_fixed_configuration(self):
        old = json.loads(
            Path(
                "configs/analysis/phase2_argument_recipient_672_train_readout_diagnostic_v1.json"
            ).read_text()
        )
        self.assertEqual(CONFIG["capture"]["stem"], old["recipient_logprob"]["stem"])
        self.assertEqual(sum(map(len, CONFIG["analysis"]["judged_layers"].values())) * 2, 42)

    def test_digit_and_paths_fail_closed(self):
        for value in ("GB", "US8", "GBx", "GB８"):
            with self.assertRaises(ValueError):
                first_digit(value)
        for value in ("/tmp/test", "../test", ""):
            with self.assertRaises(ValueError):
                safe_path(Path.cwd(), value)

    def test_stem_uses_raw_text_and_reports_missing_calls(self):
        result = stem_statistics(
            {
                "a": [{"raw_text": CONFIG["capture"]["stem"] + "GB8"}],
                "b": [{"raw_text": "send_money malformed"}],
                "c": [{"raw_text": None}],
            },
            CONFIG["capture"]["stem"],
        )
        self.assertEqual(result["send_money_generations"], 2)
        self.assertEqual(result["matching_generations"], 1)
        self.assertEqual(result["mismatch_fraction"], 0.5)
        self.assertEqual(result["mismatching_run_ids"], ["b"])
        self.assertEqual(result["no_send_money_run_ids"], ["c"])
