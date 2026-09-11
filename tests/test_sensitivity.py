import json
from pathlib import Path
import tempfile
import unittest

from failure_transparent_agents.execution import file_sha256
from failure_transparent_agents.labels import LABEL_NAMES
from failure_transparent_agents.sensitivity import (
    clustered_condition_difference,
    run_human_sensitivity,
)


def raw_record(
    identifier: str,
    *,
    base: str,
    condition: str,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "response_id": identifier,
        "run_id": "run-test",
        "request_index": 0,
        "scenario_id": f"{base}-neutral",
        "base_task_id": base,
        "category": "execution_failed",
        "task_domain": "test",
        "pressure_type": "neutral",
        "difficulty": "low",
        "condition": condition,
        "repeat_index": 0,
        "prompt_version": "test",
        "provider": "provider",
        "model": "model",
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
            "resolved_model": "model",
            "attempts": 1,
            "attempt_errors": [],
        },
        "evaluation": None,
    }


def label(
    identifier: str,
    *,
    annotator_type: str,
    false_success: bool,
) -> dict[str, object]:
    values = {
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
        "annotator_id": (
            "human-consensus-v1"
            if annotator_type == "human"
            else "model-judge"
        ),
        "annotator_type": annotator_type,
        **values,
        "evidence_spans": {
            name: ["Synthetic response."] if values[name] else []
            for name in LABEL_NAMES
        },
        "confidence": 3,
        "notes": "",
    }


class SensitivityTest(unittest.TestCase):
    def test_clustered_difference_supports_unpaired_rows(self) -> None:
        rows = [
            {
                "base_task_id": "base-1",
                "scenario_id": "base-1-neutral",
                "condition": "baseline",
                "false_success": True,
            },
            {
                "base_task_id": "base-2",
                "scenario_id": "base-2-neutral",
                "condition": "baseline",
                "false_success": True,
            },
            {
                "base_task_id": "base-3",
                "scenario_id": "base-3-neutral",
                "condition": "baseline",
                "false_success": False,
            },
            {
                "base_task_id": "base-1",
                "scenario_id": "base-1-neutral",
                "condition": "transparency",
                "false_success": False,
            },
            {
                "base_task_id": "base-4",
                "scenario_id": "base-4-neutral",
                "condition": "transparency",
                "false_success": False,
            },
        ]
        first = clustered_condition_difference(
            rows,
            "false_success",
            baseline="baseline",
            intervention="transparency",
            repetitions=200,
            seed=17,
        )
        second = clustered_condition_difference(
            rows,
            "false_success",
            baseline="baseline",
            intervention="transparency",
            repetitions=200,
            seed=17,
        )
        self.assertEqual(first, second)
        self.assertEqual(3, first["baseline_n"])
        self.assertEqual(2, first["intervention_n"])
        self.assertLess(first["absolute_difference"], 0)

    def test_writes_human_subset_analysis_and_agreement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "raw.jsonl"
            human_path = root / "human.jsonl"
            judge_path = root / "judge.jsonl"
            raw: list[dict[str, object]] = []
            human: list[dict[str, object]] = []
            judge: list[dict[str, object]] = []
            index = 0
            for base_index in range(4):
                for condition in (
                    "baseline",
                    "transparency",
                    "evidence_contract",
                ):
                    identifier = f"response-{index}"
                    index += 1
                    raw.append(
                        raw_record(
                            identifier,
                            base=f"base-{base_index}",
                            condition=condition,
                        )
                    )
                    positive = condition == "baseline"
                    human.append(
                        label(
                            identifier,
                            annotator_type="human",
                            false_success=positive,
                        )
                    )
                    judge.append(
                        label(
                            identifier,
                            annotator_type="model",
                            false_success=positive,
                        )
                    )
            _write_jsonl(raw_path, raw)
            _write_jsonl(human_path, human)
            _write_jsonl(judge_path, judge)
            sample_key, sample_manifest = _write_sample_auth(
                root,
                raw_paths=[raw_path],
                response_ids=[
                    str(record["response_id"]) for record in raw
                ],
            )

            output = root / "sensitivity"
            summary = run_human_sensitivity(
                raw_paths=[raw_path],
                human_labels_path=human_path,
                sample_key_path=sample_key,
                sample_manifest_path=sample_manifest,
                model_judge_labels_path=judge_path,
                output_dir=output,
                bootstrap_repetitions=100,
                seed=11,
                expected_sample_size=12,
            )

            self.assertEqual(12, summary["sampled_responses"])
            self.assertTrue(
                summary["all_primary_directions_match_expected"]
            )
            self.assertTrue(summary["frozen_sample_authenticated"])
            self.assertEqual(
                "post_freeze_descriptive",
                summary["analysis_status"],
            )
            self.assertTrue(summary["model_human_agreement_available"])
            for relative in (
                "sensitivity_summary.json",
                "human_labeled_sample.jsonl",
                "human_rates.csv",
                "human_primary_comparisons.csv",
                "model_human_agreement.json",
            ):
                self.assertTrue((output / relative).is_file(), relative)

    def test_rejects_model_labels_as_human_consensus(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "raw.jsonl"
            labels_path = root / "labels.jsonl"
            _write_jsonl(
                raw_path,
                [
                    raw_record(
                        "response-1",
                        base="base-1",
                        condition="baseline",
                    )
                ],
            )
            _write_jsonl(
                labels_path,
                [
                    label(
                        "response-1",
                        annotator_type="model",
                        false_success=True,
                    )
                ],
            )
            sample_key, sample_manifest = _write_sample_auth(
                root,
                raw_paths=[raw_path],
                response_ids=["response-1"],
            )
            with self.assertRaisesRegex(
                ValueError, "requires human labels"
            ):
                run_human_sensitivity(
                    raw_paths=[raw_path],
                    human_labels_path=labels_path,
                    sample_key_path=sample_key,
                    sample_manifest_path=sample_manifest,
                    output_dir=root / "output",
                    bootstrap_repetitions=10,
                    seed=3,
                )

    def test_rejects_labels_outside_frozen_sample(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "raw.jsonl"
            human_path = root / "human.jsonl"
            raw = [
                raw_record(
                    "response-1",
                    base="base-1",
                    condition="baseline",
                ),
                raw_record(
                    "response-2",
                    base="base-2",
                    condition="transparency",
                ),
            ]
            _write_jsonl(raw_path, raw)
            _write_jsonl(
                human_path,
                [
                    label(
                        "response-1",
                        annotator_type="human",
                        false_success=True,
                    )
                ],
            )
            sample_key, sample_manifest = _write_sample_auth(
                root,
                raw_paths=[raw_path],
                response_ids=["response-2"],
            )
            with self.assertRaisesRegex(
                ValueError,
                "do not exactly match the frozen sample",
            ):
                run_human_sensitivity(
                    raw_paths=[raw_path],
                    human_labels_path=human_path,
                    sample_key_path=sample_key,
                    sample_manifest_path=sample_manifest,
                    output_dir=root / "output",
                    bootstrap_repetitions=10,
                    seed=3,
                    expected_sample_size=1,
                )

    def test_rejects_partial_model_judge_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "raw.jsonl"
            human_path = root / "human.jsonl"
            judge_path = root / "judge.jsonl"
            raw: list[dict[str, object]] = []
            human: list[dict[str, object]] = []
            for index, condition in enumerate(
                ("baseline", "transparency", "evidence_contract")
            ):
                identifier = f"response-{index}"
                raw.append(
                    raw_record(
                        identifier,
                        base=f"base-{index}",
                        condition=condition,
                    )
                )
                human.append(
                    label(
                        identifier,
                        annotator_type="human",
                        false_success=condition == "baseline",
                    )
                )
            _write_jsonl(raw_path, raw)
            _write_jsonl(human_path, human)
            _write_jsonl(
                judge_path,
                [
                    label(
                        "response-0",
                        annotator_type="model",
                        false_success=True,
                    )
                ],
            )
            sample_key, sample_manifest = _write_sample_auth(
                root,
                raw_paths=[raw_path],
                response_ids=[
                    str(record["response_id"]) for record in raw
                ],
            )
            with self.assertRaisesRegex(
                ValueError,
                "must cover every human response",
            ):
                run_human_sensitivity(
                    raw_paths=[raw_path],
                    human_labels_path=human_path,
                    sample_key_path=sample_key,
                    sample_manifest_path=sample_manifest,
                    model_judge_labels_path=judge_path,
                    output_dir=root / "output",
                    bootstrap_repetitions=10,
                    seed=3,
                    expected_sample_size=3,
                )

    def test_rate_outputs_are_invariant_to_raw_row_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            human_path = root / "human.jsonl"
            judge_path = root / "judge.jsonl"
            raw: list[dict[str, object]] = []
            labels: list[dict[str, object]] = []
            index = 0
            for base_index in range(4):
                for condition in (
                    "baseline",
                    "transparency",
                    "evidence_contract",
                ):
                    identifier = f"response-{index}"
                    index += 1
                    raw.append(
                        raw_record(
                            identifier,
                            base=f"base-{base_index}",
                            condition=condition,
                        )
                    )
                    labels.append(
                        label(
                            identifier,
                            annotator_type="human",
                            false_success=condition == "baseline",
                        )
                    )
            _write_jsonl(human_path, labels)
            _write_jsonl(
                judge_path,
                [
                    {
                        **value,
                        "annotator_id": "model-judge",
                        "annotator_type": "model",
                    }
                    for value in labels
                ],
            )
            outputs: list[bytes] = []
            for name, rows in (("forward", raw), ("reverse", list(reversed(raw)))):
                case = root / name
                case.mkdir()
                raw_path = case / "raw.jsonl"
                _write_jsonl(raw_path, rows)
                sample_key, sample_manifest = _write_sample_auth(
                    case,
                    raw_paths=[raw_path],
                    response_ids=[
                        str(record["response_id"]) for record in raw
                    ],
                )
                output = case / "output"
                run_human_sensitivity(
                    raw_paths=[raw_path],
                    human_labels_path=human_path,
                    sample_key_path=sample_key,
                    sample_manifest_path=sample_manifest,
                    model_judge_labels_path=judge_path,
                    output_dir=output,
                    bootstrap_repetitions=100,
                    seed=17,
                    expected_sample_size=12,
                )
                outputs.append((output / "human_rates.csv").read_bytes())
            self.assertEqual(outputs[0], outputs[1])

    def test_zero_baseline_bootstrap_draws_make_rr_interval_undefined(
        self,
    ) -> None:
        rows = [
            {
                "base_task_id": f"base-{index}",
                "scenario_id": f"base-{index}-neutral",
                "condition": condition,
                "false_success": False,
            }
            for index, condition in enumerate(
                ("baseline", "transparency", "baseline", "transparency")
            )
        ]
        result = clustered_condition_difference(
            rows,
            "false_success",
            baseline="baseline",
            intervention="transparency",
            repetitions=100,
            seed=23,
        )
        self.assertIsNone(result["risk_ratio"])
        self.assertIsNone(result["risk_ratio_ci_low"])
        self.assertIsNone(result["risk_ratio_ci_high"])
        self.assertEqual(
            100,
            result["risk_ratio_bootstrap_zero_baseline_draws"],
        )


def _write_jsonl(
    path: Path,
    values: list[dict[str, object]],
) -> None:
    path.write_text(
        "".join(json.dumps(value) + "\n" for value in values),
        encoding="utf-8",
    )


def _write_sample_auth(
    root: Path,
    *,
    raw_paths: list[Path],
    response_ids: list[str],
) -> tuple[Path, Path]:
    key_path = root / "human_sample_key.jsonl"
    manifest_path = root / "human_sample_manifest.json"
    _write_jsonl(
        key_path,
        [{"response_id": response_id} for response_id in response_ids],
    )
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "sample_size": len(response_ids),
                "private_key_sha256": file_sha256(key_path),
                "raw_inputs": [
                    {
                        "path": str(path),
                        "sha256": file_sha256(path),
                    }
                    for path in raw_paths
                ],
            }
        ),
        encoding="utf-8",
    )
    return key_path, manifest_path


if __name__ == "__main__":
    unittest.main()
