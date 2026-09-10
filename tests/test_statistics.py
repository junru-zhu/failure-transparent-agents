import unittest

from failure_transparent_agents.statistics import (
    agreement,
    hierarchical_rate_interval,
    holm_adjust,
    paired_condition_effect,
)


def rows() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for base_index in range(4):
        for repeat_index in range(2):
            for condition in ("baseline", "transparency", "evidence_contract"):
                result.append(
                    {
                        "provider": "provider",
                        "model": "model",
                        "base_task_id": f"base-{base_index}",
                        "scenario_id": f"base-{base_index}-neutral",
                        "condition": condition,
                        "repeat_index": repeat_index,
                        "false_success": (
                            condition == "baseline" and base_index < 2
                        ),
                    }
                )
    return result


class StatisticsTest(unittest.TestCase):
    def test_hierarchical_interval_is_deterministic(self) -> None:
        baseline = [
            row for row in rows() if row["condition"] == "baseline"
        ]
        first = hierarchical_rate_interval(
            baseline,
            "false_success",
            repetitions=200,
            seed=17,
        )
        second = hierarchical_rate_interval(
            baseline,
            "false_success",
            repetitions=200,
            seed=17,
        )
        self.assertEqual(first, second)
        self.assertEqual(0.5, first["rate"])
        self.assertEqual(4, first["base_task_clusters"])

    def test_paired_effect_uses_complete_pairs(self) -> None:
        result = paired_condition_effect(
            rows(),
            "false_success",
            baseline="baseline",
            intervention="transparency",
            repetitions=200,
            seed=9,
            permutation_repetitions=500,
        )
        self.assertEqual(8, result["paired_units"])
        self.assertEqual(4, result["base_task_clusters"])
        self.assertEqual(-0.5, result["absolute_difference"])
        self.assertEqual(0.0, result["risk_ratio"])

    def test_holm_adjustment_is_monotone(self) -> None:
        adjusted = holm_adjust({"a": 0.01, "b": 0.03, "c": 0.2})
        self.assertAlmostEqual(0.03, adjusted["a"])
        self.assertAlmostEqual(0.06, adjusted["b"])
        self.assertAlmostEqual(0.2, adjusted["c"])

    def test_agreement_reports_kappa(self) -> None:
        result = agreement(
            [True, True, False, False],
            [True, False, False, False],
        )
        self.assertEqual(0.75, result["raw_agreement"])
        self.assertAlmostEqual(0.5, result["cohen_kappa"])

    def test_agreement_marks_constant_labels_kappa_undefined(self) -> None:
        result = agreement([False, False], [False, False])
        self.assertIsNone(result["cohen_kappa"])


if __name__ == "__main__":
    unittest.main()
