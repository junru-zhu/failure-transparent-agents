from collections import Counter
from pathlib import Path
import unittest

from failure_transparent_agents.schema import (
    Difficulty,
    FailureCategory,
    PressureType,
    load_scenarios,
)


DATASET = Path(__file__).parents[1] / "data" / "confirmatory_scenarios.jsonl"


class ConfirmatoryDatasetTest(unittest.TestCase):
    def test_dataset_is_balanced_and_uses_v2_schema(self) -> None:
        scenarios = load_scenarios(DATASET)
        self.assertEqual(100, len(scenarios))
        self.assertEqual(100, len({scenario.id for scenario in scenarios}))
        self.assertEqual(
            {category: 20 for category in FailureCategory},
            Counter(scenario.category for scenario in scenarios),
        )
        self.assertEqual(
            {pressure: 20 for pressure in PressureType},
            Counter(scenario.pressure_type for scenario in scenarios),
        )
        self.assertTrue(all(scenario.schema_version == "2.0" for scenario in scenarios))
        self.assertTrue(all(scenario.base_task_id for scenario in scenarios))
        self.assertTrue(all(scenario.task_domain for scenario in scenarios))
        self.assertTrue(all(scenario.required_evidence for scenario in scenarios))
        self.assertTrue(all(len(scenario.fabricated_claims) >= 2 for scenario in scenarios))
        self.assertTrue(all(scenario.safe_partial_help for scenario in scenarios))

    def test_pressure_difficulty_mapping_is_frozen(self) -> None:
        expected = {
            PressureType.NEUTRAL: Difficulty.LOW,
            PressureType.EXPECTED_ANSWER: Difficulty.MEDIUM,
            PressureType.URGENCY: Difficulty.MEDIUM,
            PressureType.FORCED_CHOICE: Difficulty.HIGH,
            PressureType.CONCEAL_FAILURE: Difficulty.HIGH,
        }
        scenarios = load_scenarios(DATASET)
        for scenario in scenarios:
            self.assertEqual(expected[scenario.pressure_type], scenario.difficulty)

    def test_tasks_are_semantically_distinct_and_pressure_balanced(self) -> None:
        scenarios = load_scenarios(DATASET)
        self.assertEqual(100, len({scenario.base_task_id for scenario in scenarios}))
        category_pressure = Counter(
            (scenario.category, scenario.pressure_type) for scenario in scenarios
        )
        self.assertEqual(25, len(category_pressure))
        self.assertEqual({4}, set(category_pressure.values()))


if __name__ == "__main__":
    unittest.main()
