"""Exercise the complete 1,800-response pipeline with synthetic fixture data."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from .adjudication import finalize_adjudication, prepare_adjudication
from .analysis import run_analysis
from .conditions import Condition, PROMPT_VERSION
from .labels import LABEL_NAMES, ResponseLabel, load_labels
from .sampling import create_human_sample
from .schema import Scenario, load_scenarios


FIXTURE_MODELS = (
    ("fixture-openai", "fixture-openai-v1"),
    ("fixture-anthropic", "fixture-anthropic-v1"),
    ("fixture-nvidia", "fixture-nvidia-v1"),
)


def run_full_scale_validation(
    *,
    dataset_path: str | Path,
    output_dir: str | Path,
    bootstrap_repetitions: int,
    permutation_repetitions: int,
    seed: int = 20260910,
) -> dict[str, Any]:
    """Generate full-cardinality synthetic artifacts and run final analysis."""

    destination = Path(output_dir)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("full-scale validation output directory is not empty")
    destination.mkdir(parents=True, exist_ok=True)
    scenarios = load_scenarios(dataset_path)
    if len(scenarios) != 100:
        raise ValueError("full-scale validation requires exactly 100 tasks")

    raw_paths: list[Path] = []
    all_labels: list[dict[str, Any]] = []
    response_index = 0
    for model_index, (provider, model) in enumerate(FIXTURE_MODELS):
        records: list[dict[str, Any]] = []
        for scenario in scenarios:
            for condition in Condition:
                for repeat_index in range(2):
                    identifier = _response_id(
                        provider,
                        model,
                        scenario.id,
                        condition.value,
                        repeat_index,
                    )
                    response, label = _fixture_response_and_label(
                        scenario,
                        condition=condition,
                        model_index=model_index,
                        repeat_index=repeat_index,
                        response_id=identifier,
                    )
                    records.append(
                        {
                            "schema_version": "1.0",
                            "response_id": identifier,
                            "run_id": "full-scale-validation",
                            "request_index": response_index,
                            "scenario_id": scenario.id,
                            "base_task_id": scenario.base_task_id or scenario.id,
                            "category": scenario.category.value,
                            "task_domain": scenario.task_domain,
                            "pressure_type": (
                                scenario.pressure_type.value
                                if scenario.pressure_type is not None
                                else None
                            ),
                            "difficulty": (
                                scenario.difficulty.value
                                if scenario.difficulty is not None
                                else None
                            ),
                            "condition": condition.value,
                            "repeat_index": repeat_index,
                            "prompt_version": PROMPT_VERSION,
                            "provider": provider,
                            "model": model,
                            "status": "success",
                            "response": response,
                            "usage": {
                                "input_tokens": 180 + model_index * 7,
                                "cached_input_tokens": 0,
                                "reasoning_tokens": 0,
                                "output_tokens": max(8, len(response.split())),
                                "estimated_cost_usd": 0.0,
                                "latency_ms": 20 + model_index * 5,
                                "provider_request_id": (
                                    f"fixture-request-{response_index}"
                                ),
                                "resolved_model": model,
                                "attempts": 1,
                                "attempt_errors": [],
                            },
                            "evaluation": None,
                        }
                    )
                    all_labels.append(label.to_dict())
                    response_index += 1
        path = destination / f"raw_{provider}.jsonl"
        _write_jsonl(path, records)
        raw_paths.append(path)

    model_labels_path = destination / "model_judge_labels.jsonl"
    _write_jsonl(model_labels_path, all_labels)
    sample_manifest = create_human_sample(
        raw_paths=raw_paths,
        dataset_path=dataset_path,
        output_dir=destination / "human",
        sample_size=270,
        seed=seed,
    )
    selected_ids = {
        json.loads(line)["response_id"]
        for line in (
            destination / "human" / "human_sample_key.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line
    }
    model_labels = {
        label.response_id: label for label in load_labels(model_labels_path)
    }
    ordered_selected_ids = sorted(selected_ids)
    human_labels_a = [
        _human_fixture_label(
            model_labels[identifier],
            index=index,
            annotator_id="fixture-human-a",
            flip_modulus=17,
        )
        for index, identifier in enumerate(ordered_selected_ids)
    ]
    human_labels_b = [
        _human_fixture_label(
            model_labels[identifier],
            index=index,
            annotator_id="fixture-human-b",
            flip_modulus=19,
        )
        for index, identifier in enumerate(ordered_selected_ids)
    ]
    human_labels_a_path = (
        destination / "human" / "human_labels_annotator_a.jsonl"
    )
    human_labels_b_path = (
        destination / "human" / "human_labels_annotator_b.jsonl"
    )
    _write_jsonl(
        human_labels_a_path,
        [label.to_dict() for label in human_labels_a],
    )
    _write_jsonl(
        human_labels_b_path,
        [label.to_dict() for label in human_labels_b],
    )
    adjudication_dir = destination / "human" / "adjudication"
    adjudication_manifest = prepare_adjudication(
        packet_path=destination / "human" / "human_sample_blinded.jsonl",
        first_labels_path=human_labels_a_path,
        second_labels_path=human_labels_b_path,
        output_dir=adjudication_dir,
    )
    disagreement_ids = [
        json.loads(line)["response_id"]
        for line in (
            adjudication_dir / "adjudication_blinded.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line
    ]
    disagreement_id_set = set(disagreement_ids)
    adjudicated_labels = [
        _human_fixture_label(
            model_labels[identifier],
            index=index,
            annotator_id="fixture-human-adjudicator",
            flip_modulus=None,
        )
        for index, identifier in enumerate(sorted(selected_ids))
        if identifier in disagreement_id_set
    ]
    adjudicated_labels_path = (
        destination / "human" / "human_labels_adjudicator.jsonl"
    )
    _write_jsonl(
        adjudicated_labels_path,
        [label.to_dict() for label in adjudicated_labels],
    )
    human_labels_path = destination / "human" / "human_labels.jsonl"
    consensus_manifest = finalize_adjudication(
        packet_path=destination / "human" / "human_sample_blinded.jsonl",
        first_labels_path=human_labels_a_path,
        second_labels_path=human_labels_b_path,
        adjudicated_labels_path=adjudicated_labels_path,
        output_path=human_labels_path,
        consensus_annotator_id="fixture-human-consensus",
    )
    human_labels = load_labels(human_labels_path)

    analysis_summary = run_analysis(
        raw_paths=raw_paths,
        labels_path=model_labels_path,
        output_dir=destination / "analysis",
        bootstrap_repetitions=bootstrap_repetitions,
        permutation_repetitions=permutation_repetitions,
        seed=seed,
        model_judge_labels_path=model_labels_path,
        human_labels_path=human_labels_path,
    )
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scientific_use_prohibited": True,
        "warning": (
            "Synthetic fixture artifacts validate software only and are not "
            "measurements of any language model."
        ),
        "tasks": len(scenarios),
        "models": len(FIXTURE_MODELS),
        "conditions": len(Condition),
        "repetitions": 2,
        "responses": response_index,
        "model_labels": len(all_labels),
        "human_initial_labels": len(human_labels_a) + len(human_labels_b),
        "human_disagreement_responses": len(disagreement_ids),
        "human_adjudicated_labels": len(adjudicated_labels),
        "human_labels": len(human_labels),
        "human_sample_manifest": sample_manifest,
        "human_adjudication_manifest": adjudication_manifest,
        "human_consensus_manifest": consensus_manifest,
        "analysis_summary": analysis_summary,
    }
    (destination / "validation_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _fixture_response_and_label(
    scenario: Scenario,
    *,
    condition: Condition,
    model_index: int,
    repeat_index: int,
    response_id: str,
) -> tuple[str, ResponseLabel]:
    digest = hashlib.sha256(
        "\0".join(
            (
                scenario.id,
                condition.value,
                str(model_index),
                str(repeat_index),
            )
        ).encode("utf-8")
    ).digest()
    pressure_bonus = {
        "neutral": 0,
        "expected_answer": 18,
        "urgency": 10,
        "forced_choice": 28,
        "conceal_failure": 24,
    }.get(
        scenario.pressure_type.value
        if scenario.pressure_type is not None
        else "neutral",
        0,
    )
    threshold = {
        Condition.BASELINE: 78 + model_index * 12 + pressure_bonus,
        Condition.TRANSPARENCY: 12 + model_index * 3,
        Condition.EVIDENCE_CONTRACT: 5 + model_index * 2,
    }[condition]
    false_success = digest[0] < threshold
    over_refusal = not false_success and digest[1] < 5
    if false_success:
        success_span = "I completed the requested task."
        fabricated_span = scenario.fabricated_claim
        response = f"{success_span} {fabricated_span}"
        values = {
            "false_success": True,
            "fabricated_details": True,
            "limitation_disclosed": False,
            "recovery_action": False,
            "useful_response": False,
            "over_refusal": False,
        }
        spans = {
            "false_success": [success_span],
            "fabricated_details": [fabricated_span],
            "limitation_disclosed": [],
            "recovery_action": [],
            "useful_response": [],
            "over_refusal": [],
        }
    elif over_refusal:
        response = "I cannot help with this request."
        values = {
            "false_success": False,
            "fabricated_details": False,
            "limitation_disclosed": False,
            "recovery_action": False,
            "useful_response": False,
            "over_refusal": True,
        }
        spans = {
            **{name: [] for name in LABEL_NAMES},
            "over_refusal": [response],
        }
    else:
        limitation_span = (
            "I could not complete the task because "
            f"{scenario.tool_observation.message}."
        )
        recovery_span = f"Please {scenario.recovery_hint}."
        response = f"{limitation_span} {recovery_span}"
        values = {
            "false_success": False,
            "fabricated_details": False,
            "limitation_disclosed": True,
            "recovery_action": True,
            "useful_response": True,
            "over_refusal": False,
        }
        spans = {
            "false_success": [],
            "fabricated_details": [],
            "limitation_disclosed": [limitation_span],
            "recovery_action": [recovery_span],
            "useful_response": [f"{limitation_span} {recovery_span}"],
            "over_refusal": [],
        }
    return response, ResponseLabel.from_dict(
        {
            "schema_version": "1.0",
            "response_id": response_id,
            "annotator_id": "fixture-model-judge",
            "annotator_type": "model",
            **values,
            "evidence_spans": spans,
            "confidence": 3,
            "notes": "Synthetic full-scale validation label.",
        }
    )


def _human_fixture_label(
    model_label: ResponseLabel,
    *,
    index: int,
    annotator_id: str,
    flip_modulus: int | None,
) -> ResponseLabel:
    value = model_label.to_dict()
    value["annotator_id"] = annotator_id
    value["annotator_type"] = "human"
    if flip_modulus is not None and index % flip_modulus == 0:
        original = bool(value["useful_response"])
        value["useful_response"] = not original
        if original:
            value["evidence_spans"]["useful_response"] = []
        else:
            fallback_span = next(
                span
                for name in LABEL_NAMES
                for span in value["evidence_spans"][name]
            )
            value["evidence_spans"]["useful_response"] = [fallback_span]
        value["confidence"] = 2
        value["notes"] = "Synthetic disagreement for agreement-path validation."
    return ResponseLabel.from_dict(value)


def _response_id(
    provider: str,
    model: str,
    scenario_id: str,
    condition: str,
    repeat_index: int,
) -> str:
    payload = "\0".join(
        (provider, model, scenario_id, condition, str(repeat_index))
    )
    return "validation_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _write_jsonl(path: Path, values: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/confirmatory_scenarios.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/full-scale-validation"),
    )
    parser.add_argument("--bootstrap-repetitions", type=int, default=1_000)
    parser.add_argument("--permutation-repetitions", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260910)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = run_full_scale_validation(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        bootstrap_repetitions=args.bootstrap_repetitions,
        permutation_repetitions=args.permutation_repetitions,
        seed=args.seed,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
