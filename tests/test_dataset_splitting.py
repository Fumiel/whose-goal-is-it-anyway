import unittest

from goal_takeover.datasets.splitting import assign_group_splits


class DatasetSplittingTest(unittest.TestCase):
    def test_assignment_is_deterministic(self) -> None:
        group_ids = [f"group-{index}" for index in range(20)]
        first = assign_group_splits(group_ids, seed=17)
        second = assign_group_splits(reversed(group_ids), seed=17)
        self.assertEqual(first, second)

    def test_duplicate_group_never_receives_two_splits(self) -> None:
        assignments = assign_group_splits(["pair-1", "pair-1", "pair-2"], seed=4)
        self.assertEqual(set(assignments), {"pair-1", "pair-2"})

    def test_invalid_proportions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            assign_group_splits(
                ["group-1"],
                seed=1,
                proportions={"train": 0.8, "test": 0.3},
            )


if __name__ == "__main__":
    unittest.main()
