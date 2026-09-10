"""Run one resumable provider arm of the confirmatory experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .api_providers import build_api_provider, load_provider_settings
from .execution import (
    build_request_matrix,
    file_sha256,
    run_resumable,
)
from .freeze import verify_frozen_config, verify_frozen_sources
from .schema import load_scenarios


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--provider-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--allow-unfrozen", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.allow_live:
        parser.error("confirmatory API runs require --allow-live")
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    manifest = json.loads(args.dataset_manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        parser.error("dataset manifest must be an object")
    actual_dataset_hash = file_sha256(args.dataset)
    if manifest.get("dataset_sha256") != actual_dataset_hash:
        parser.error("dataset SHA-256 does not match the manifest")
    if not manifest.get("frozen") and not args.allow_unfrozen:
        parser.error("dataset is not frozen; author signoff is required")

    scenarios = load_scenarios(args.dataset)
    requests = build_request_matrix(scenarios, repeats=args.repeats)
    settings = load_provider_settings(str(args.provider_config))
    if manifest.get("frozen"):
        try:
            verify_frozen_sources(manifest)
            verify_frozen_config(
                manifest,
                config_path=args.provider_config,
            )
        except ValueError as error:
            parser.error(str(error))
    required_attempts = len(requests) * (settings.max_retries + 1)
    if settings.max_calls < required_attempts:
        parser.error(
            f"provider max_calls must be at least {required_attempts} "
            "to cover the matrix and configured retries"
        )
    provider = build_api_provider(settings)
    preflight_budget = provider.preflight_required_budget(requests)
    if preflight_budget > settings.max_budget_usd + 1e-12:
        parser.error(
            "provider budget cannot cover the conservative matrix bound: "
            f"${preflight_budget:.6f} > ${settings.max_budget_usd:.6f}"
        )

    records = run_resumable(
        requests,
        provider,
        run_id=args.run_id,
        output_dir=args.output_dir,
        dataset_path=args.dataset,
        dataset_sha256=actual_dataset_hash,
        provider_config_path=args.provider_config,
        provider_config_sha256=file_sha256(args.provider_config),
        repeats=args.repeats,
        workers=args.workers,
        resume=args.resume,
        preflight_budget_usd=preflight_budget,
        budget_cap_usd=settings.max_budget_usd,
    )
    print(
        json.dumps(
            {
                "records": len(records),
                "output_dir": str(args.output_dir),
                "spent_usd": provider.spent_usd,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
