"""Local text spans and grouped held-out fits, using synthetic conditions only."""

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_activation_patching import SETTINGS, rows_and_labels
from test_position_sweep_positions import ACCOUNTS

from goal_takeover.phase2 import local_wording_baseline as local
from goal_takeover.phase2.argument_recipient_672_selection_pointer import pair_index

NUMERICAL = importlib.util.find_spec("numpy") and importlib.util.find_spec("sklearn")


class WindowsTest(unittest.TestCase):
    def test_exact_character_windows_clip_at_start_and_exclude_account(self):
        rows, _ = rows_and_labels()
        for row in rows:
            row["source_role"] = "user_instruction"
            row["user_instruction"] = "payee: GB8XXX reference: GB4YYY"
        for position, account in (("A1", "GB8XXX"), ("A2", "GB4YYY")):
            for length in (3, 32, 64, 128):
                texts, ranges = local.local_windows(rows, ACCOUNTS, position, length)
                end = rows[0]["user_instruction"].index(account)
                self.assertEqual(texts[0], rows[0]["user_instruction"][max(0, end - length) : end])
                self.assertNotIn(account, texts[0])
                self.assertEqual(ranges[0]["character_end"], end)
        with self.assertRaises(ValueError):
            local.local_windows([{**rows[0], "split_candidate": "validation"}], ACCOUNTS, "A1", 32)

    def test_existing_output_rejected_before_plan_or_fitting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "artifacts/processed" / SETTINGS["local_wording"]["output_id"]
            target.mkdir(parents=True)
            with (
                patch.object(local, "read_config", return_value=(root, SETTINGS)),
                patch.object(local, "load_plan") as load,
                self.assertRaises(FileExistsError),
            ):
                local.run(Path("unused.json"))
            load.assert_not_called()


@unittest.skipUnless(NUMERICAL, "numerical extras unavailable")
class FitTest(unittest.TestCase):
    def test_local_only_signal_and_grouped_folds(self):
        rows, labels = rows_and_labels()
        for row, label in zip(rows, labels, strict=True):
            row["source_role"] = "user_instruction"
            first, second = ("RECIPIENT", "REFERENCE") if label else ("REFERENCE", "RECIPIENT")
            row["user_instruction"] = f"{first} GB8XXX {second} GB4YYY"
        settings = copy.deepcopy(SETTINGS["local_wording"])
        settings["window_characters"] = [10]
        result = local.evaluate_local(rows, ACCOUNTS, labels, pair_index(rows, labels), settings)
        for cell in result.values():
            for level, folds in (("family", 6), ("series", 12)):
                self.assertEqual(cell["evaluations"][level]["paired_accuracy"], 1.0)
                self.assertEqual(len(cell["evaluations"][level]["folds"]), folds)
        self.assertEqual(
            result, local.evaluate_local(rows, ACCOUNTS, labels, pair_index(rows, labels), settings)
        )


if __name__ == "__main__":
    unittest.main()
