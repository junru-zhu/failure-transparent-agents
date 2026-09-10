"""Deterministic failed-tool simulator for benchmark scenarios."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from .schema import Scenario, ToolObservation, load_scenarios


class FailedToolSimulator:
    """Replay exactly the frozen failed observation attached to each scenario."""

    def __init__(self, scenarios: Sequence[Scenario]) -> None:
        self._scenarios = {scenario.id: scenario for scenario in scenarios}
        if len(self._scenarios) != len(scenarios):
            raise ValueError("simulator scenarios must have unique IDs")

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "FailedToolSimulator":
        return cls(load_scenarios(path))

    def invoke(
        self,
        scenario_id: str,
        *,
        tool_name: str | None = None,
    ) -> ToolObservation:
        try:
            scenario = self._scenarios[scenario_id]
        except KeyError as error:
            raise KeyError(f"unknown scenario_id {scenario_id!r}") from error
        observation = scenario.tool_observation
        if tool_name is not None and tool_name != observation.name:
            raise ValueError(
                f"scenario {scenario_id!r} requires tool {observation.name!r}, "
                f"not {tool_name!r}"
            )
        return observation

    def trace(self, scenario_id: str) -> dict[str, Any]:
        observation = self.invoke(scenario_id)
        value = {
            "scenario_id": scenario_id,
            "tool_observation": {
                "name": observation.name,
                "status": observation.status,
                "error_code": observation.error_code,
                "message": observation.message,
                "metadata": observation.metadata,
            },
        }
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return {
            **value,
            "trace_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/confirmatory_scenarios.jsonl"),
    )
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--tool-name")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    simulator = FailedToolSimulator.from_jsonl(args.dataset)
    simulator.invoke(args.scenario_id, tool_name=args.tool_name)
    print(json.dumps(simulator.trace(args.scenario_id), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
