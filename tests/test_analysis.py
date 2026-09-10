import json
from pathlib import Path
import tempfile
import unittest

from failure_transparent_agents.analysis import run_analysis
from failure_transparent_agents.labels import LABEL_NAMES


def raw_record(
    identifier: str,
    *,
    model: str,
    base: str,
    condition: str,
    repeat: int,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "response_id": identifier,
        "run_id": f"run-{model}",
        "request_index": 0,
        "scenario_id": f"{base}-neutral",
        "base_task_id": base,
        "category": "execution_failed",
        "task_domain": "test",
        "pressure_type": "neutral",
        "difficulty": "low",
        "condition": condition,
        "repeat_index": repeat,
        "prompt_version": "test",
        "provider": model,
        "model": model,
        "status": "success",
        "response": "Synthetic response.",
        "usage": {
            "input_tokens": 10,
            "cached_input_tokens": 0,
            "reasoning_tokens": 0,
            "output_tokens": 5,
            "estimated_cost_usd": 0.001,
            "latency_ms": 20,
            "provider_request_id": identifier,
            "resolved_model": model,
            "attempts": 1,
            "attempt_errors": [],
        },
        "evaluation": None,
    }


def label(identifier: str, *, false_success: bool) -> dict[str, object]:
    labels = {
        "false_success": false_success,
        "fabricated_details": false_success,
        "limitation_disclosed": not false_success,
        "recovery_action": not false_success,
        "useful_response": True,
        "over_refusal": False,
    }
    return {
        "schema_version": "1.0",
        "response_id": identifier,
        "annotator_id": "judge",
        "annotator_type": "model",
        **labels,
        "evidence_spans": {
            name: ["Synthetic response."] if labels[name] else []
            for name in LABEL_NAMES
        },
        "confidence": 3,
        "notes": "",
    }


class AnalysisTest(unittest.TestCase):
    def test_writes_complete_artifact_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "raw.jsonl"
            labels_path = root / "labels.jsonl"
            raw: list[dict[str, object]] = []
            labels: list[dict[str, object]] = []
            index = 0
            for model in ("model-a", "model-b"):
                for base in ("base-1", "base-2"):
                    for repeat in range(2):
                        for condition in (
                            "baseline",
                            "transparency",
                            "evidence_contract",
                        ):
                            identifier = f"resp-{index}"
                            index += 1
                            raw.append(
                                raw_record(
                                    identifier,
                                    model=model,
                                    base=base,
                                    condition=condition,
                                    repeat=repeat,
                                )
                            )
                            labels.append(
                                label(
                                    identifier,
                                    false_success=condition == "baseline",
                                )
                            )
            raw_path.write_text(
                "".join(json.dumps(item) + "\n" for item in raw),
                encoding="utf-8",
            )
            labels_path.write_text(
                "".join(json.dumps(item) + "\n" for item in labels),
                encoding="utf-8",
            )
            output = root / "analysis"
            summary = run_analysis(
                raw_paths=[raw_path],
                labels_path=labels_path,
                output_dir=output,
                bootstrap_repetitions=50,
                permutation_repetitions=50,
                seed=7,
            )

            self.assertEqual(24, summary["labeled_responses"])
            for relative in (
                "analysis_summary.json",
                "labeled_results.jsonl",
                "rates.csv",
                "comparisons.csv",
                "efficiency.csv",
                "figures/figure1_false_success_by_model.svg",
                "figures/figure2_transparency_and_utility.svg",
                "figures/figure3_pressure_ablation.svg",
                "tables/ablation_table.tex",
            ):
                self.assertTrue((output / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
