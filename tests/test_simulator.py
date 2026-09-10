from pathlib import Path
import unittest

from failure_transparent_agents.simulator import FailedToolSimulator


ROOT = Path(__file__).parents[1]


class SimulatorTest(unittest.TestCase):
    def test_replays_identical_trace(self) -> None:
        simulator = FailedToolSimulator.from_jsonl(
            ROOT / "data" / "confirmatory_scenarios.jsonl"
        )
        first = simulator.trace("web-101-neutral")
        second = simulator.trace("web-101-neutral")
        self.assertEqual(first, second)
        self.assertEqual(
            "SERVICE_UNAVAILABLE",
            first["tool_observation"]["error_code"],
        )

    def test_rejects_wrong_tool(self) -> None:
        simulator = FailedToolSimulator.from_jsonl(
            ROOT / "data" / "confirmatory_scenarios.jsonl"
        )
        with self.assertRaisesRegex(ValueError, "requires tool"):
            simulator.invoke("web-101-neutral", tool_name="different-tool")


if __name__ == "__main__":
    unittest.main()
