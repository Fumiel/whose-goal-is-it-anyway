import unittest

from goal_takeover.evaluation.outcomes import classify_outcome
from goal_takeover.schemas import OutcomeGroup


class OutcomeClassificationTest(unittest.TestCase):
    def test_group_a(self) -> None:
        self.assertEqual(
            classify_outcome(has_attack=False, user_task_success=True, attack_success=False),
            OutcomeGroup.A,
        )

    def test_group_b(self) -> None:
        self.assertEqual(
            classify_outcome(has_attack=True, user_task_success=True, attack_success=False),
            OutcomeGroup.B,
        )

    def test_group_c(self) -> None:
        self.assertEqual(
            classify_outcome(has_attack=True, user_task_success=False, attack_success=False),
            OutcomeGroup.C,
        )

    def test_group_d_keeps_user_success_orthogonal(self) -> None:
        for user_success in (False, True):
            with self.subTest(user_success=user_success):
                self.assertEqual(
                    classify_outcome(
                        has_attack=True,
                        user_task_success=user_success,
                        attack_success=True,
                    ),
                    OutcomeGroup.D,
                )

    def test_clean_failure_is_not_forced_into_a_to_d(self) -> None:
        self.assertIsNone(
            classify_outcome(has_attack=False, user_task_success=False, attack_success=False)
        )

    def test_attack_success_without_attack_is_inconsistent(self) -> None:
        with self.assertRaises(ValueError):
            classify_outcome(has_attack=False, user_task_success=True, attack_success=True)


if __name__ == "__main__":
    unittest.main()
