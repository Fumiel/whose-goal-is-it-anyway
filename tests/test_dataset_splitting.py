import unittest

from goal_takeover.datasets.splitting import (
    assign_condition_splits,
    assign_group_splits,
    connected_component_groups,
)


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

    def test_transitively_related_conditions_stay_in_one_split(self) -> None:
        conditions = [
            {
                "condition_id": "c1",
                "task_template_id": "task-a",
                "attack_template_id": "attack-x",
            },
            {
                "condition_id": "c2",
                "task_template_id": "task-a",
                "attack_template_id": "attack-y",
            },
            {
                "condition_id": "c3",
                "task_template_id": "task-b",
                "attack_template_id": "attack-y",
            },
            {
                "condition_id": "c4",
                "task_template_id": "task-c",
                "attack_template_id": "attack-z",
            },
        ]
        keys = ("task_template_id", "attack_template_id")

        components = connected_component_groups(conditions, group_keys=keys)
        assignments = assign_condition_splits(
            conditions,
            group_keys=keys,
            seed=11,
            proportions={"train": 0.5, "test": 0.5},
        )

        self.assertEqual(components["c1"], components["c2"])
        self.assertEqual(components["c2"], components["c3"])
        self.assertNotEqual(components["c1"], components["c4"])
        self.assertEqual(assignments["c1"], assignments["c2"])
        self.assertEqual(assignments["c2"], assignments["c3"])


if __name__ == "__main__":
    unittest.main()
