"""Offline validation and cost bounds for the confirmatory experiment."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Sequence

from .api_providers import build_api_provider, load_provider_settings
from .conditions import Condition
from .execution import build_request_matrix, file_sha256
from .freeze import (
    validate_collection_approval,
    verify_frozen_config,
    verify_frozen_sources,
)
from .judge import JUDGE_SYSTEM_INSTRUCTION, build_judge_message
from .model_verification import validate_model_verification
from .schema import load_scenarios


def build_preflight_plan(
    *,
    dataset_path: str | Path,
    dataset_manifest_path: str | Path,
    provider_config_paths: Sequence[str | Path],
    judge_config_paths: Sequence[str | Path] = (),
    approval_path: str | Path = "data/confirmatory_approval.json",
    model_verification_path: str | Path = "data/model_verification.json",
    repeats: int = 2,
    judge_parse_retries: int = 1,
    judged_response_character_assumption: int = 1_200,
) -> dict[str, Any]:
    """Validate a complete matrix without reading credentials or making API calls."""

    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    if not provider_config_paths:
        raise ValueError("at least one provider config is required")
    if judge_parse_retries < 0:
        raise ValueError("judge_parse_retries must be nonnegative")
    if judged_response_character_assumption < 1:
        raise ValueError(
            "judged_response_character_assumption must be positive"
        )

    dataset = Path(dataset_path)
    dataset_manifest = Path(dataset_manifest_path)
    manifest = json.loads(dataset_manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("dataset manifest must be an object")
    dataset_sha256 = file_sha256(dataset)
    if manifest.get("dataset_sha256") != dataset_sha256:
        raise ValueError("dataset SHA-256 does not match its manifest")

    scenarios = load_scenarios(dataset)
    if manifest.get("scenario_count") != len(scenarios):
        raise ValueError("dataset scenario count does not match its manifest")
    requests = build_request_matrix(scenarios, repeats=repeats)

    arms: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for raw_path in provider_config_paths:
        config_path = Path(raw_path)
        settings = load_provider_settings(str(config_path))
        identity = (settings.provider_name, settings.model)
        if identity in identities:
            raise ValueError(f"duplicate provider/model arm: {identity!r}")
        identities.add(identity)

        # A placeholder key is supplied only to construct the local adapter. The
        # preflight invokes no transport and never reads the real credential env.
        provider = build_api_provider(settings, api_key="offline-preflight")
        maximum_attempts = len(requests) * (settings.max_retries + 1)
        required_budget = provider.preflight_required_budget(requests)
        max_call_ok = settings.max_calls >= maximum_attempts
        budget_ok = required_budget <= settings.max_budget_usd + 1e-12
        frozen_hash_ok = True
        if manifest.get("frozen"):
            try:
                verify_frozen_config(manifest, config_path=config_path)
            except ValueError:
                frozen_hash_ok = False
        arms.append(
            {
                "provider": settings.provider_name,
                "provider_type": settings.provider_type,
                "model": settings.model,
                "config": str(config_path),
                "config_sha256": file_sha256(config_path),
                "credential_env": settings.api_key_env,
                "primary_requests": len(requests),
                "maximum_attempts": maximum_attempts,
                "max_calls": settings.max_calls,
                "max_calls_ok": max_call_ok,
                "max_retries": settings.max_retries,
                "max_output_tokens": settings.max_output_tokens,
                "preflight_max_cost_usd": round(required_budget, 8),
                "budget_cap_usd": settings.max_budget_usd,
                "budget_ok": budget_ok,
                "frozen_hash_ok": frozen_hash_ok,
                "pricing_usd_per_million_tokens": {
                    "input": settings.pricing.input_per_million,
                    "cached_input": settings.pricing.cached_input_per_million,
                    "output": settings.pricing.output_per_million,
                },
            }
        )

    failures = [
        f"{arm['provider']}/{arm['model']}: max_calls"
        for arm in arms
        if not arm["max_calls_ok"]
    ] + [
        f"{arm['provider']}/{arm['model']}: budget"
        for arm in arms
        if not arm["budget_ok"]
    ] + [
        f"{arm['provider']}/{arm['model']}: frozen config hash"
        for arm in arms
        if not arm["frozen_hash_ok"]
    ]
    judge_arms: list[dict[str, Any]] = []
    synthetic_judge_records = [
        {
            "response_id": (
                f"preflight-{model_index}-{scenario.id}-"
                f"{condition.value}-{repeat_index}"
            ),
            "scenario_id": scenario.id,
            "response": "X" * judged_response_character_assumption,
        }
        for model_index in range(len(arms))
        for scenario in scenarios
        for condition in Condition
        for repeat_index in range(repeats)
    ]
    scenario_by_id = {scenario.id: scenario for scenario in scenarios}
    for raw_path in judge_config_paths:
        config_path = Path(raw_path)
        settings = load_provider_settings(str(config_path))
        provider = build_api_provider(settings, api_key="offline-preflight")
        maximum_calls = (
            len(synthetic_judge_records)
            * (settings.max_retries + 1)
            * (judge_parse_retries + 1)
        )
        required_budget = sum(
            provider.maximum_text_cost(
                JUDGE_SYSTEM_INSTRUCTION,
                build_judge_message(
                    record,
                    scenario_by_id[str(record["scenario_id"])],
                ),
            )
            for record in synthetic_judge_records
        ) * (settings.max_retries + 1) * (judge_parse_retries + 1)
        max_calls_ok = settings.max_calls >= maximum_calls
        budget_ok = required_budget <= settings.max_budget_usd + 1e-12
        frozen_hash_ok = True
        if manifest.get("frozen"):
            try:
                verify_frozen_config(
                    manifest,
                    config_path=config_path,
                    config_group="judge_config_sha256s",
                )
            except ValueError:
                frozen_hash_ok = False
        judge_arms.append(
            {
                "provider": settings.provider_name,
                "model": settings.model,
                "config": str(config_path),
                "config_sha256": file_sha256(config_path),
                "credential_env": settings.api_key_env,
                "responses_to_judge": len(synthetic_judge_records),
                "response_character_assumption": (
                    judged_response_character_assumption
                ),
                "parse_retries": judge_parse_retries,
                "provider_retries": settings.max_retries,
                "maximum_calls": maximum_calls,
                "max_calls": settings.max_calls,
                "max_calls_ok": max_calls_ok,
                "preflight_max_cost_usd": round(required_budget, 8),
                "budget_cap_usd": settings.max_budget_usd,
                "budget_ok": budget_ok,
                "frozen_hash_ok": frozen_hash_ok,
            }
        )
        if not max_calls_ok:
            failures.append(
                f"{settings.provider_name}/{settings.model}: judge max_calls"
            )
        if not budget_ok:
            failures.append(
                f"{settings.provider_name}/{settings.model}: judge budget"
            )
        if not frozen_hash_ok:
            failures.append(
                f"{settings.provider_name}/{settings.model}: frozen judge config hash"
            )
    verification_path = Path(model_verification_path)
    try:
        model_verification = validate_model_verification(
            verification_path,
            provider_config_paths=provider_config_paths,
            judge_config_paths=judge_config_paths,
        )
    except ValueError as error:
        model_verification = {
            "path": str(verification_path),
            "exists": verification_path.is_file(),
            "sha256": (
                file_sha256(verification_path)
                if verification_path.is_file()
                else None
            ),
            "ready": False,
            "error": str(error),
        }
        failures.append(f"model verification invalid: {error}")
    frozen_source_hashes_ok = True
    if manifest.get("frozen"):
        try:
            verify_frozen_sources(manifest)
        except ValueError:
            frozen_source_hashes_ok = False
            failures.append("scientific source changed after author signoff")
    primary_preflight_cost = sum(
        float(arm["preflight_max_cost_usd"]) for arm in arms
    )
    judge_preflight_cost = sum(
        float(arm["preflight_max_cost_usd"]) for arm in judge_arms
    )
    primary_budget_cap = sum(float(arm["budget_cap_usd"]) for arm in arms)
    judge_budget_cap = sum(
        float(arm["budget_cap_usd"]) for arm in judge_arms
    )
    approval_summary, approval_issue, approval_issue_is_gate = (
        _inspect_collection_approval(
            approval_path=approval_path,
            provider_config_paths=provider_config_paths,
            judge_config_paths=judge_config_paths,
        )
    )
    if approval_issue and not approval_issue_is_gate:
        failures.append(approval_issue)
    blocking_checks = list(failures)
    if not manifest.get("frozen"):
        blocking_checks.append("dataset requires author freeze")
    if approval_issue and approval_issue_is_gate:
        blocking_checks.append(approval_issue)
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline_only": True,
        "network_calls_made": 0,
        "dataset": str(dataset),
        "dataset_manifest": str(dataset_manifest),
        "dataset_sha256": dataset_sha256,
        "dataset_frozen": bool(manifest.get("frozen")),
        "base_task_count": manifest.get("base_task_count"),
        "task_instance_count": len(scenarios),
        "conditions": 3,
        "repeats": repeats,
        "model_arms": len(arms),
        "planned_primary_responses": len(requests) * len(arms),
        "maximum_provider_attempts": sum(
            int(arm["maximum_attempts"]) for arm in arms
        ),
        "primary_preflight_max_cost_usd": round(primary_preflight_cost, 8),
        "primary_budget_cap_usd": round(primary_budget_cap, 8),
        "judge_preflight_max_cost_usd": round(judge_preflight_cost, 8),
        "judge_budget_cap_usd": round(judge_budget_cap, 8),
        "aggregate_preflight_max_cost_usd": round(
            primary_preflight_cost + judge_preflight_cost,
            8,
        ),
        "aggregate_budget_cap_usd": round(
            primary_budget_cap + judge_budget_cap,
            8,
        ),
        "arms": arms,
        "judge_arms": judge_arms,
        "model_verification": model_verification,
        "collection_approval": approval_summary,
        "frozen_source_hashes_ok": frozen_source_hashes_ok,
        "ready_for_live_run": (
            not blocking_checks
            and bool(manifest.get("frozen"))
            and bool(approval_summary["ready"])
        ),
        "blocking_checks": blocking_checks,
    }


def _inspect_collection_approval(
    *,
    approval_path: str | Path,
    provider_config_paths: Sequence[str | Path],
    judge_config_paths: Sequence[str | Path],
) -> tuple[dict[str, Any], str | None, bool]:
    path = Path(approval_path)
    summary: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "sha256": file_sha256(path) if path.is_file() else None,
        "status": None,
        "approved_by": None,
        "approved_at": None,
        "data_collection_authorized": False,
        "ready": False,
    }
    if not path.is_file():
        return summary, f"collection approval file missing: {path}", False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return summary, "collection approval contains invalid JSON", False
    if not isinstance(value, dict):
        return summary, "collection approval must be an object", False
    summary.update(
        {
            "status": value.get("status"),
            "approved_by": value.get("approved_by"),
            "approved_at": value.get("approved_at"),
            "data_collection_authorized": (
                value.get("data_collection_authorized") is True
            ),
        }
    )
    if (
        value.get("status") != "approved"
        or value.get("data_collection_authorized") is not True
    ):
        return (
            summary,
            "collection approval requires explicit authorization",
            True,
        )
    signer = value.get("approved_by")
    if not isinstance(signer, str) or not signer.strip():
        return summary, "collection approval approved_by is invalid", False
    try:
        validate_collection_approval(
            path,
            signer=signer,
            provider_config_paths=provider_config_paths,
            judge_config_paths=judge_config_paths,
        )
    except ValueError as error:
        return summary, f"collection approval invalid: {error}", False
    summary["ready"] = True
    return summary, None, False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/confirmatory_scenarios.jsonl"),
    )
    parser.add_argument(
        "--dataset-manifest",
        type=Path,
        default=Path("data/confirmatory_manifest.json"),
    )
    parser.add_argument(
        "--provider-config",
        type=Path,
        action="append",
        dest="provider_configs",
    )
    parser.add_argument(
        "--judge-config",
        type=Path,
        action="append",
        dest="judge_configs",
    )
    parser.add_argument(
        "--approval",
        type=Path,
        default=Path("data/confirmatory_approval.json"),
    )
    parser.add_argument(
        "--model-verification",
        type=Path,
        default=Path("data/model_verification.json"),
    )
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    provider_configs = args.provider_configs or sorted(
        Path("configs/providers").glob("*.json")
    )
    judge_configs = args.judge_configs or sorted(
        Path("configs/judges").glob("*.json")
    )
    plan = build_preflight_plan(
        dataset_path=args.dataset,
        dataset_manifest_path=args.dataset_manifest,
        provider_config_paths=provider_configs,
        judge_config_paths=judge_configs,
        approval_path=args.approval,
        model_verification_path=args.model_verification,
        repeats=args.repeats,
    )
    encoded = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    expected_gates = {
        "dataset requires author freeze",
        "collection approval requires explicit authorization",
    }
    return (
        0
        if all(issue in expected_gates for issue in plan["blocking_checks"])
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
