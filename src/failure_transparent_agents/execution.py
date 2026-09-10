"""Resumable confirmatory execution with append-only progress artifacts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
from typing import Any, Sequence

from .conditions import Condition, PROMPT_VERSION
from .providers import (
    GenerationRequest,
    GenerationResponse,
    ModelProvider,
    ProviderError,
)
from .schema import Scenario


def build_request_matrix(
    scenarios: Sequence[Scenario],
    *,
    repeats: int,
) -> list[GenerationRequest]:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    return [
        GenerationRequest(
            scenario=scenario,
            condition=condition,
            repeat_index=repeat_index,
        )
        for scenario in scenarios
        for condition in Condition
        for repeat_index in range(repeats)
    ]


def response_id(
    *,
    run_id: str,
    provider: str,
    model: str,
    request: GenerationRequest,
) -> str:
    payload = "\0".join(
        (
            run_id,
            provider,
            model,
            request.scenario.id,
            request.condition.value,
            str(request.repeat_index),
        )
    )
    return "resp_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def run_resumable(
    requests: Sequence[GenerationRequest],
    provider: ModelProvider,
    *,
    run_id: str,
    output_dir: str | Path,
    dataset_path: str | Path,
    dataset_sha256: str,
    provider_config_path: str | Path,
    provider_config_sha256: str,
    repeats: int,
    workers: int,
    resume: bool,
    preflight_budget_usd: float | None,
    budget_cap_usd: float | None,
) -> list[dict[str, Any]]:
    if not run_id.strip():
        raise ValueError("run_id must be non-empty")
    if workers < 1:
        raise ValueError("workers must be at least 1")
    destination = Path(output_dir)
    progress_path = destination / "progress.jsonl"
    raw_path = destination / "raw_results.jsonl"
    budget_state_path = destination / "budget_state.json"
    if destination.exists() and any(destination.iterdir()) and not resume:
        raise ValueError("output directory is not empty; pass resume=True")
    destination.mkdir(parents=True, exist_ok=True)

    expected: list[tuple[int, GenerationRequest, str]] = [
        (
            index,
            request,
            response_id(
                run_id=run_id,
                provider=provider.name,
                model=provider.model,
                request=request,
            ),
        )
        for index, request in enumerate(requests)
    ]
    expected_ids = {item[2] for item in expected}
    existing = _load_existing_records(raw_path if raw_path.exists() else progress_path)
    existing_by_id = {str(record["response_id"]): record for record in existing}
    unexpected_ids = set(existing_by_id) - expected_ids
    if unexpected_ids:
        raise ValueError(
            f"resume artifacts contain unexpected response IDs: "
            f"{', '.join(sorted(unexpected_ids)[:3])}"
        )
    restored_spend = 0.0
    restored_calls = 0
    if resume and budget_state_path.is_file():
        budget_state = json.loads(budget_state_path.read_text(encoding="utf-8"))
        if not isinstance(budget_state, dict):
            raise ValueError("budget_state.json must contain an object")
        restored_spend = float(budget_state.get("spent_usd", 0.0))
        restored_calls = int(budget_state.get("calls_started", 0))
        restore_state = getattr(provider, "restore_runtime_state", None)
        if callable(restore_state):
            restore_state(
                spent_usd=restored_spend,
                calls_started=restored_calls,
            )
        else:
            restore = getattr(provider, "restore_spent_usd", None)
            if callable(restore):
                restore(restored_spend)

    manifest = {
        "schema_version": "1.0",
        "run_id": run_id,
        "status": "running",
        "started_at": _utc_now(),
        "provider": provider.name,
        "model": provider.model,
        "prompt_version": PROMPT_VERSION,
        "dataset": str(Path(dataset_path)),
        "dataset_sha256": dataset_sha256,
        "provider_config": str(Path(provider_config_path)),
        "provider_config_sha256": provider_config_sha256,
        "scenario_count": len({request.scenario.id for request in requests}),
        "repeats": repeats,
        "conditions": [condition.value for condition in Condition],
        "planned_responses": len(requests),
        "workers": workers,
        "preflight_budget_usd": preflight_budget_usd,
        "budget_cap_usd": budget_cap_usd,
        "resumed_records": len(existing_by_id),
        "restored_spend_usd": restored_spend,
        "restored_calls_started": restored_calls,
    }
    _atomic_write_json(destination / "manifest.json", manifest)

    pending = [item for item in expected if item[2] not in existing_by_id]
    if pending:
        progress_path.touch(exist_ok=True)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _execute_request,
                    request,
                    provider,
                    run_id,
                    index,
                    identifier,
                ): identifier
                for index, request, identifier in pending
            }
            with progress_path.open("a", encoding="utf-8") as progress:
                for future in as_completed(futures):
                    record = future.result()
                    progress.write(json.dumps(record, sort_keys=True) + "\n")
                    progress.flush()
                    existing_by_id[str(record["response_id"])] = record
                    current_spend = getattr(provider, "spent_usd", None)
                    if current_spend is not None:
                        _atomic_write_json(
                            budget_state_path,
                            {
                                "run_id": run_id,
                                "spent_usd": current_spend,
                                "calls_started": getattr(
                                    provider,
                                    "calls_started",
                                    None,
                                ),
                                "updated_at": _utc_now(),
                            },
                        )

    ordered = [
        existing_by_id[identifier]
        for _, _, identifier in expected
        if identifier in existing_by_id
    ]
    _atomic_write_jsonl(raw_path, ordered)
    summary = summarize_execution(ordered)
    _atomic_write_json(destination / "summary.json", summary)
    manifest.update(
        {
            "status": (
                "complete"
                if summary["provider_errors"] == 0
                else "complete_with_errors"
            ),
            "completed_at": _utc_now(),
            "completed_records": len(ordered),
            "successful_responses": summary["successful_responses"],
            "provider_errors": summary["provider_errors"],
            "spent_usd": getattr(provider, "spent_usd", None),
        }
    )
    _atomic_write_json(destination / "manifest.json", manifest)
    current_spend = getattr(provider, "spent_usd", None)
    if current_spend is not None:
        _atomic_write_json(
            budget_state_path,
            {
                "run_id": run_id,
                "spent_usd": current_spend,
                "calls_started": getattr(provider, "calls_started", None),
                "updated_at": _utc_now(),
            },
        )
    return ordered


def summarize_execution(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    successful = [record for record in records if record["status"] == "success"]
    failures = [record for record in records if record["status"] == "provider_error"]
    by_condition: dict[str, dict[str, int]] = {}
    for condition in Condition:
        condition_records = [
            record for record in records if record["condition"] == condition.value
        ]
        by_condition[condition.value] = {
            "records": len(condition_records),
            "successful": sum(
                record["status"] == "success" for record in condition_records
            ),
            "provider_errors": sum(
                record["status"] == "provider_error" for record in condition_records
            ),
        }
    usage_fields = (
        "input_tokens",
        "cached_input_tokens",
        "reasoning_tokens",
        "output_tokens",
    )
    usage = {
        field: sum(int(record["usage"][field]) for record in successful)
        for field in usage_fields
    }
    known_costs = [
        float(record["usage"]["estimated_cost_usd"])
        for record in successful
        if record["usage"]["estimated_cost_usd"] is not None
    ]
    latencies = sorted(
        int(record["usage"]["latency_ms"]) for record in successful
    )
    return {
        "total_records": len(records),
        "successful_responses": len(successful),
        "provider_errors": len(failures),
        "conditions": by_condition,
        "usage": usage,
        "estimated_cost_usd": (
            round(sum(known_costs), 8)
            if len(known_costs) == len(successful)
            else None
        ),
        "latency_ms": {
            "median": round(statistics.median(latencies), 3) if latencies else None,
            "p95": _percentile(latencies, 0.95) if latencies else None,
        },
        "unscored": True,
    }


def _execute_request(
    request: GenerationRequest,
    provider: ModelProvider,
    run_id: str,
    request_index: int,
    identifier: str,
) -> dict[str, Any]:
    base = {
        "schema_version": "1.0",
        "response_id": identifier,
        "run_id": run_id,
        "request_index": request_index,
        "scenario_id": request.scenario.id,
        "base_task_id": request.scenario.base_task_id or request.scenario.id,
        "category": request.scenario.category.value,
        "task_domain": request.scenario.task_domain,
        "pressure_type": (
            request.scenario.pressure_type.value
            if request.scenario.pressure_type is not None
            else None
        ),
        "difficulty": (
            request.scenario.difficulty.value
            if request.scenario.difficulty is not None
            else None
        ),
        "condition": request.condition.value,
        "repeat_index": request.repeat_index,
        "prompt_version": PROMPT_VERSION,
        "provider": provider.name,
        "model": provider.model,
    }
    try:
        response = provider.generate(request)
    except ProviderError as error:
        return {
            **base,
            "status": "provider_error",
            "response": None,
            "usage": {
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "reasoning_tokens": 0,
                "output_tokens": 0,
                "estimated_cost_usd": None,
                "latency_ms": 0,
                "provider_request_id": None,
                "resolved_model": None,
                "attempts": None,
                "attempt_errors": [str(error)],
            },
            "evaluation": None,
        }
    return {
        **base,
        "status": "success",
        "response": response.text,
        "usage": {
            "input_tokens": response.input_tokens,
            "cached_input_tokens": response.cached_input_tokens,
            "reasoning_tokens": response.reasoning_tokens,
            "output_tokens": response.output_tokens,
            "estimated_cost_usd": response.estimated_cost_usd,
            "latency_ms": response.latency_ms,
            "provider_request_id": response.provider_request_id,
            "resolved_model": response.resolved_model,
            "attempts": response.attempts,
            "attempt_errors": list(response.attempt_errors),
        },
        "evaluation": None,
    }


def _load_existing_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            value = json.loads(raw_line)
            if not isinstance(value, dict) or not isinstance(
                value.get("response_id"),
                str,
            ):
                raise ValueError(f"{path}:{line_number}: invalid progress record")
            identifier = value["response_id"]
            if identifier in seen:
                raise ValueError(f"{path}:{line_number}: duplicate response_id")
            seen.add(identifier)
            records.append(value)
    return records


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_write_jsonl(path: Path, values: Sequence[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True) + "\n")
    temporary.replace(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _percentile(values: Sequence[int], probability: float) -> int:
    if not values:
        raise ValueError("cannot compute percentile of empty values")
    index = min(len(values) - 1, max(0, round((len(values) - 1) * probability)))
    return values[index]
