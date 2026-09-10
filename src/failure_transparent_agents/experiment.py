"""Run fixture or gated live failure-transparency experiments."""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import random
from typing import Any, Callable, Iterable, Sequence

from .conditions import Condition, PROMPT_VERSION
from .evaluate import Evaluation, evaluate_response
from .providers import (
    CodexExecProvider,
    FixtureProvider,
    GenerationRequest,
    ModelProvider,
)
from .schema import Scenario, load_scenarios


_METRICS = (
    "false_success",
    "fabricated_details",
    "limitation_disclosed",
    "recovery_action",
    "transparent",
)


def run_experiment(
    scenarios: Sequence[Scenario],
    provider: ModelProvider,
    repeats: int = 2,
    *,
    evaluator: Callable[[Scenario, str], Evaluation] | None = None,
    workers: int = 1,
) -> list[dict[str, Any]]:
    """Generate every combination and safely select fixture-only scoring."""

    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    if workers < 1:
        raise ValueError("workers must be at least 1")
    if evaluator is None and provider.name == "fixture":
        evaluator = evaluate_response
    requests = [
        GenerationRequest(
            scenario=scenario,
            condition=condition,
            repeat_index=repeat_index,
        )
        for scenario in scenarios
        for condition in Condition
        for repeat_index in range(repeats)
    ]

    def generate_record(request: GenerationRequest) -> dict[str, Any]:
        scenario = request.scenario
        response = provider.generate(request)
        evaluation = (
            evaluator(scenario, response.text).to_dict()
            if evaluator is not None
            else None
        )
        return {
            "scenario_id": scenario.id,
            "category": scenario.category.value,
            "condition": request.condition.value,
            "repeat_index": request.repeat_index,
            "prompt_version": PROMPT_VERSION,
            "provider": response.provider,
            "model": response.model,
            "response": response.text,
            "usage": {
                "input_tokens": response.input_tokens,
                        "cached_input_tokens": response.cached_input_tokens,
                        "reasoning_tokens": response.reasoning_tokens,
                        "output_tokens": response.output_tokens,
                        "estimated_cost_usd": response.estimated_cost_usd,
                        "latency_ms": response.latency_ms,
                        "provider_request_id": response.provider_request_id,
                        "attempts": response.attempts,
                        "attempt_errors": list(response.attempt_errors),
                    },
            "evaluation": evaluation,
        }

    if workers == 1:
        return [generate_record(request) for request in requests]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(generate_record, requests))


def summarize(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate metrics by condition with deterministic bootstrap intervals."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["condition"])].append(record)
    conditions: dict[str, Any] = {}
    for condition, condition_records in sorted(grouped.items()):
        scored_records = [
            record for record in condition_records if isinstance(record["evaluation"], dict)
        ]
        metrics: dict[str, Any] = {}
        if scored_records:
            for metric in _METRICS:
                values = [bool(record["evaluation"][metric]) for record in scored_records]
                rate = sum(values) / len(values)
                low, high = bootstrap_proportion_interval(
                    values,
                    seed=f"{condition}:{metric}",
                )
                metrics[metric] = {
                    "count": sum(values),
                    "rate": round(rate, 6),
                    "ci95": [round(low, 6), round(high, 6)],
                }
        cost_values = [
            record["usage"]["estimated_cost_usd"] for record in condition_records
        ]
        estimated_cost = (
            round(sum(float(value) for value in cost_values), 6)
            if all(value is not None for value in cost_values)
            else None
        )
        conditions[condition] = {
            "responses": len(condition_records),
            "scored_responses": len(scored_records),
            "metrics": metrics,
            "estimated_cost_usd": estimated_cost,
        }
    scored_count = sum(
        isinstance(record["evaluation"], dict) for record in records
    )
    fixture_only = bool(records) and all(
        record["provider"] == "fixture" for record in records
    )
    if fixture_only:
        warning = "Fixture outputs validate the pipeline and are not empirical model results."
    elif scored_count == 0:
        warning = (
            "Live model outputs are unscored. The fixture heuristic must not be "
            "used as a scientific judge."
        )
    elif scored_count == len(records):
        warning = "Model outputs were scored by the configured external evaluator."
    else:
        warning = "Only a subset of responses was scored; review the raw records."
    return {
        "pilot_only": True,
        "warning": warning,
        "total_responses": len(records),
        "scored_responses": scored_count,
        "conditions": conditions,
    }


def bootstrap_proportion_interval(
    values: Sequence[bool],
    *,
    seed: str,
    samples: int = 2_000,
) -> tuple[float, float]:
    """Return a deterministic percentile-bootstrap interval for a binary rate."""

    if not values:
        raise ValueError("cannot bootstrap an empty sequence")
    if samples < 100:
        raise ValueError("samples must be at least 100")
    generator = random.Random(seed)
    size = len(values)
    rates = sorted(
        sum(values[generator.randrange(size)] for _ in range(size)) / size
        for _ in range(samples)
    )
    return rates[int(samples * 0.025)], rates[int(samples * 0.975) - 1]


def write_outputs(
    output_dir: str | Path,
    records: Sequence[dict[str, Any]],
    *,
    dataset_path: str | Path,
    repeats: int,
    workers: int = 1,
) -> None:
    """Write raw results, summary, and an explicit pilot manifest."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    _write_jsonl(destination / "raw_results.jsonl", records)
    (destination / "summary.json").write_text(
        json.dumps(summarize(records), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = summarize(records)
    providers = sorted({str(record["provider"]) for record in records})
    models = sorted({str(record["model"]) for record in records})
    manifest = {
        "pilot_only": True,
        "dataset": str(Path(dataset_path)),
        "scenario_count": len({str(record["scenario_id"]) for record in records}),
        "repeats": repeats,
        "workers": workers,
        "provider": providers[0] if len(providers) == 1 else providers,
        "model": models[0] if len(models) == 1 else models,
        "prompt_version": PROMPT_VERSION,
        "scoring": (
            "fixture-heuristic-v1"
            if summary["scored_responses"] == len(records)
            else "unscored"
        ),
        "warning": summary["warning"],
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--scenario-limit", type=int)
    parser.add_argument(
        "--provider",
        choices=("fixture", "codex"),
        default="fixture",
    )
    parser.add_argument("--model")
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--codex-command", default="codex")
    parser.add_argument("--codex-working-directory", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    scenarios = load_scenarios(args.dataset)
    if args.scenario_limit is not None:
        if args.scenario_limit < 1:
            parser.error("--scenario-limit must be at least 1")
        scenarios = scenarios[: args.scenario_limit]
    planned_calls = len(scenarios) * len(Condition) * args.repeats
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if args.provider == "codex":
        if not args.allow_live:
            parser.error("Codex runs require the explicit --allow-live flag")
        if not args.model:
            parser.error("Codex runs require an exact --model identifier")
        if args.max_calls is None:
            parser.error("Codex runs require an explicit --max-calls cap")
        if args.max_calls < planned_calls:
            parser.error(
                f"--max-calls must be at least {planned_calls} for this run matrix"
            )
        if args.output_dir.exists():
            if not args.output_dir.is_dir():
                parser.error("live output path exists and is not a directory")
            if any(args.output_dir.iterdir()):
                parser.error("live output directory must be absent or empty")
        provider: ModelProvider = CodexExecProvider(
            model=args.model,
            max_calls=args.max_calls,
            codex_command=args.codex_command,
            timeout_seconds=args.timeout_seconds,
            working_directory=args.codex_working_directory,
        )
        evaluator = None
    else:
        provider = FixtureProvider()
        evaluator = evaluate_response
    records = run_experiment(
        scenarios,
        provider,
        repeats=args.repeats,
        evaluator=evaluator,
        workers=args.workers,
    )
    write_outputs(
        args.output_dir,
        records,
        dataset_path=args.dataset,
        repeats=args.repeats,
        workers=args.workers,
    )
    summary = summarize(records)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
