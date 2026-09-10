from collections import Counter
import unittest

from failure_transparent_agents.sampling import stratified_sample


class SamplingTest(unittest.TestCase):
    def test_balances_primary_strata_and_pressure(self) -> None:
        records: list[dict[str, object]] = []
        index = 0
        for model in ("a", "b"):
            for condition in ("baseline", "transparency", "evidence_contract"):
                for category in ("web_unavailable", "stale_data"):
                    for pressure in (
                        "neutral",
                        "expected_answer",
                        "urgency",
                        "forced_choice",
                        "conceal_failure",
                    ):
                        for repeat in range(2):
                            records.append(
                                {
                                    "response_id": f"resp-{index}",
                                    "model": model,
                                    "condition": condition,
                                    "category": category,
                                    "pressure_type": pressure,
                                    "repeat_index": repeat,
                                }
                            )
                            index += 1
        selected = stratified_sample(records, sample_size=72, seed=11)
        self.assertEqual(72, len(selected))
        primary_counts = Counter(
            (row["model"], row["condition"], row["category"])
            for row in selected
        )
        self.assertEqual({6}, set(primary_counts.values()))
        pressure_counts = Counter(
            row["pressure_type"] for row in selected
        )
        self.assertLessEqual(
            max(pressure_counts.values()) - min(pressure_counts.values()),
            1,
        )
        self.assertEqual(
            [row["response_id"] for row in stratified_sample(records, sample_size=72, seed=11)],
            [row["response_id"] for row in selected],
        )


if __name__ == "__main__":
    unittest.main()
